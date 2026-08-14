#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

import jsonschema
import requests
import yaml
from dotenv import load_dotenv
from tqdm import tqdm

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
REPO_ROOT = Path(__file__).resolve().parent.parent


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def read_json(path: str | Path) -> Dict[str, Any]:
    return json.loads(read_text(path))


def read_jsonl(path: str | Path) -> Iterable[Dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_number}: {exc}") from exc


def append_jsonl(path: str | Path, record: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def resume_state(path: str | Path, retry_failed: bool) -> set[tuple[str, str]]:
    """Report the (novel_id, model) pairs already recorded, and repair a killed run.

    A run is one request per novel per model, and each is appended as soon as it
    returns, so the output file is its own progress log. A run interrupted at
    request 1800 of 2000 can be restarted without paying for the first 1800.

    Killing a run can leave a half-written final line. That line is truncated away
    here rather than merely skipped: left in place it is not valid JSONL, and every
    reader of the file downstream would fail on it. The request it belonged to is
    simply made again.
    """
    path = Path(path)
    if not path.is_file():
        return set()

    done: set[tuple[str, str]] = set()
    complete_bytes = 0
    unreadable = 0
    with path.open("rb") as f:
        for raw in f:
            if not raw.endswith(b"\n"):
                break  # a partial final write; nothing complete follows it
            complete_bytes += len(raw)
            line = raw.strip()
            if not line:
                continue
            try:
                record = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                unreadable += 1
                continue
            novel_id, model = record.get("novel_id"), record.get("model")
            if novel_id is None or model is None:
                continue
            if retry_failed and not record.get("ok"):
                continue
            done.add((str(novel_id), str(model)))

    trailing = path.stat().st_size - complete_bytes
    if trailing:
        with path.open("r+b") as f:
            f.truncate(complete_bytes)
        print(f"{path}: dropped {trailing} byte(s) of a partly written final record")
    if unreadable:
        print(
            f"{path}: {unreadable} line(s) are not readable JSON and were left in place; "
            "the file will not parse as JSONL until they are removed",
            file=sys.stderr,
        )
    return done


# Repository bookkeeping that is not JSON Schema vocabulary. Providers validate the
# schema they are handed and reject unknown keywords ("property 'version' is not
# supported"), so these are dropped from the request.
SCHEMA_METADATA_KEYS = ("$schema", "$id", "version")

# Structured-output validators accept types, enums and required/additionalProperties,
# but reject cardinality and range constraints ("For 'array' type, property 'maxItems'
# is not supported"). They are removed from the request only: the schema file keeps
# them, every response is still validated locally against the full file, and the
# bounds are also stated in prose in the codebook and in the field descriptions.
UNSUPPORTED_CONSTRAINTS = (
    "minItems", "maxItems", "uniqueItems",
    "minLength", "maxLength", "pattern",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    "minProperties", "maxProperties",
)


def _prune(node: Any, inside_property_map: bool = False) -> Any:
    """Drop unsupported constraints, without touching keys that are property names."""
    if isinstance(node, dict):
        pruned: Dict[str, Any] = {}
        for key, value in node.items():
            if not inside_property_map and key in UNSUPPORTED_CONSTRAINTS:
                continue
            is_property_map = not inside_property_map and key in ("properties", "$defs")
            pruned[key] = _prune(value, inside_property_map=is_property_map)
        return pruned
    if isinstance(node, list):
        return [_prune(item) for item in node]
    return node


def _require_all_properties(node: Any) -> Any:
    """Put every property in "required", the way OpenAI's strict mode demands.

    Strict structured outputs reject an object schema whose "required" array
    does not list every key in "properties" ("'required' is required to be
    supplied ... including every key in properties. Missing 'quote'."). Fields
    the codebook lets a model skip (e.g. evidence.quote, evidence.locator) stay
    effectively optional by becoming nullable instead: null is added to their
    type/enum so the model can write null rather than omitting the key.
    """
    if isinstance(node, dict):
        node = {key: _require_all_properties(value) for key, value in node.items()}
        if isinstance(node.get("properties"), dict):
            properties = node["properties"]
            required = set(node.get("required", []))
            for key, prop in properties.items():
                if key in required or not isinstance(prop, dict):
                    continue
                if "type" in prop:
                    types = prop["type"] if isinstance(prop["type"], list) else [prop["type"]]
                    if "null" not in types:
                        prop["type"] = types + ["null"]
                if "enum" in prop and None not in prop["enum"]:
                    prop["enum"] = prop["enum"] + [None]
            node["required"] = list(properties.keys())
        return node
    if isinstance(node, list):
        return [_require_all_properties(item) for item in node]
    return node


def schema_for_request(schema: Dict[str, Any]) -> Dict[str, Any]:
    pruned = {
        key: _prune(value)
        for key, value in schema.items()
        if key not in SCHEMA_METADATA_KEYS
    }
    return _require_all_properties(pruned)


# The text is the one corpus field not copied across as metadata: it is identified
# by input_sha256 and input_num_chars. The prompt built from it is still recorded
# in full under "request", so a run file stays roughly the size of its corpus.
TEXT_KEY = "text"

# Always present, even when the corpus omits them, so every prediction line has
# the same leading columns.
CANONICAL_METADATA = ("novel_id", "title", "author", "year")


def novel_metadata(novel: Dict[str, Any]) -> Dict[str, Any]:
    """Every corpus field except the text, so nothing the corpus knows is lost.

    Copying whatever the corpus carries, rather than a fixed list, keeps grouping
    columns such as `orientation` and the chunk provenance written by
    build_corpus.py (`source_novel_id`, `chunk_index`, `char_start`, ...) attached
    to the annotation they belong to.
    """
    metadata: Dict[str, Any] = {key: novel.get(key) for key in CANONICAL_METADATA}
    metadata.update({key: value for key, value in novel.items() if key != TEXT_KEY})
    return metadata


def build_system_context(system_prompt: str, codebook: str) -> str:
    return (
        system_prompt.strip()
        + "\n\nBEGIN CODEBOOK\n"
        + codebook.strip()
        + "\nEND CODEBOOK\n"
    )


def format_prompt(template: str, novel: Dict[str, Any], max_chars: int, allow_truncate: bool) -> tuple[str, bool]:
    text = novel.get("text", "")
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"Novel {novel.get('novel_id')} has empty or missing text")
    truncated = False
    if len(text) > max_chars:
        if not allow_truncate:
            raise ValueError(
                f"Novel {novel.get('novel_id')} has {len(text)} characters, above --max-chars={max_chars}. "
                "Use --allow-truncate only when fixed truncation is intended and documented."
            )
        text = text[:max_chars]
        truncated = True
    return template.format(
        novel_id=novel.get("novel_id", ""),
        title=novel.get("title", ""),
        author=novel.get("author", ""),
        year=novel.get("year", ""),
        text=text,
    ), truncated


def build_request(
    model: str,
    system_context: str,
    user_prompt: str,
    schema: Dict[str, Any],
    params: Dict[str, Any],
    use_json_schema: bool,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_context},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "max_tokens": params.get("max_tokens", 4096),
    }
    # Sampling parameters are only sent when the config sets them. Recent reasoning
    # models reject temperature / top_p / top_k outright, so an omitted key must mean
    # "do not send", not "send the old default".
    for key in ("temperature", "top_p", "top_k", "seed", "frequency_penalty", "presence_penalty"):
        if params.get(key) is not None:
            body[key] = params[key]
    if use_json_schema:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "novel_relationship_annotation",
                "strict": True,
                "schema": schema,
            },
        }
    else:
        body["response_format"] = {"type": "json_object"}
    return body


def call_openrouter(api_key: str, body: Dict[str, Any], app_cfg: Dict[str, Any], timeout: int, retries: int) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if app_cfg.get("http_referer"):
        headers["HTTP-Referer"] = app_cfg["http_referer"]
    if app_cfg.get("title"):
        headers["X-OpenRouter-Title"] = app_cfg["title"]

    last_error: str | None = None
    for attempt in range(retries + 1):
        try:
            response = requests.post(OPENROUTER_URL, headers=headers, json=body, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            # The status line alone does not say why a request was rejected; the
            # reason is in the response body, so keep it.
            status = exc.response.status_code if exc.response is not None else None
            detail = exc.response.text[:2000] if exc.response is not None else ""
            last_error = f"HTTP {status}: {detail}"
            # A 4xx other than rate limiting is a bad request: retrying cannot help.
            if status is not None and 400 <= status < 500 and status != 429:
                break
            if attempt >= retries:
                break
            time.sleep(2**attempt)
        except Exception as exc:  # noqa: BLE001
            last_error = repr(exc)
            if attempt >= retries:
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"OpenRouter request failed: {last_error}")


def extract_content(response: Dict[str, Any]) -> str:
    return response["choices"][0]["message"]["content"]


def parse_model_json(content: str) -> tuple[Dict[str, Any] | None, str | None]:
    try:
        return json.loads(content), None
    except json.JSONDecodeError as exc:
        return None, str(exc)


def validate_annotation(annotation: Dict[str, Any] | None, schema: Dict[str, Any]) -> str | None:
    if annotation is None:
        return "no parsed annotation"
    try:
        jsonschema.validate(annotation, schema)
        return None
    except jsonschema.ValidationError as exc:
        return exc.message


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--models-config", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--codebook", default="codebook/annotation_grid.md")
    parser.add_argument("--system-prompt", default="prompts/system_prompt.md")
    parser.add_argument("--user-template", default="prompts/user_prompt_template.md")
    parser.add_argument("--max-chars", type=int, default=120000)
    parser.add_argument("--allow-truncate", action="store_true")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--no-json-schema", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip novel/model pairs already recorded in --output, and append the rest",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="With --resume, also re-request pairs whose recorded attempt failed",
    )
    args = parser.parse_args()

    if args.retry_failed and not args.resume:
        print("--retry-failed only has an effect with --resume", file=sys.stderr)
        sys.exit(1)

    # Read the key from the repository .env, so it does not have to be exported in
    # every shell. An already-exported environment variable takes precedence.
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print(
            f"Missing OPENROUTER_API_KEY. Set it in {REPO_ROOT / '.env'} "
            "(see .env.example) or export it in the shell.",
            file=sys.stderr,
        )
        sys.exit(1)

    config = yaml.safe_load(read_text(args.models_config))
    models: List[str] = config.get("models", [])
    params: Dict[str, Any] = config.get("parameters", {})
    app_cfg: Dict[str, Any] = config.get("openrouter", {})
    if not models:
        raise ValueError("No models found in config")

    schema = read_json(args.schema)
    request_schema = schema_for_request(schema)
    system_prompt = read_text(args.system_prompt)
    codebook = read_text(args.codebook)
    user_template = read_text(args.user_template)
    system_context = build_system_context(system_prompt, codebook)
    novels = list(read_jsonl(args.input))
    if args.limit is not None:
        novels = novels[: args.limit]

    schema_sha256 = sha256_text(json.dumps(schema, ensure_ascii=False, sort_keys=True))
    codebook_sha256 = sha256_text(codebook)
    system_prompt_sha256 = sha256_text(system_prompt)
    user_template_sha256 = sha256_text(user_template)

    done = resume_state(args.output, args.retry_failed) if args.resume else set()
    if args.resume:
        total = len(novels) * len(models)
        pending = sum(1 for n in novels for m in models if (str(n.get("novel_id")), m) not in done)
        print(f"Resuming {args.output}: {total - pending} of {total} request(s) already recorded, {pending} to run")
        if args.retry_failed:
            print(
                "Failed attempts are re-requested and appended; keep the last record "
                "per novel/model pair when reading this file."
            )

    for novel in tqdm(novels, desc="novels"):
        novel_id = str(novel.get("novel_id"))
        pending_models = [model for model in models if (novel_id, model) not in done]
        if not pending_models:
            continue

        try:
            user_prompt, truncated = format_prompt(user_template, novel, args.max_chars, args.allow_truncate)
        except ValueError as exc:
            # One unusable novel must not abandon the rest of the corpus. Record the
            # failure so it is visible in the run file and retriable with
            # --resume --retry-failed.
            for model in pending_models:
                append_jsonl(args.output, {
                    **novel_metadata(novel),
                    "model": model,
                    "started_at_utc": dt.datetime.utcnow().isoformat() + "Z",
                    "finished_at_utc": dt.datetime.utcnow().isoformat() + "Z",
                    "ok": False,
                    "runtime_error": repr(exc),
                })
                tqdm.write(f"FAIL {novel_id} | {model} | {exc}")
            continue

        for model in pending_models:
            request_body = build_request(
                model=model,
                system_context=system_context,
                user_prompt=user_prompt,
                schema=request_schema,
                params=params,
                use_json_schema=not args.no_json_schema,
            )
            record: Dict[str, Any] = {
                # Corpus fields first; run bookkeeping wins on any name collision.
                **novel_metadata(novel),
                "model": model,
                "started_at_utc": dt.datetime.utcnow().isoformat() + "Z",
                "input_sha256": sha256_text(novel.get("text", "")),
                "input_num_chars": len(novel.get("text", "")),
                "truncated": truncated,
                "parameters": params,
                "schema_path": args.schema,
                "schema_sha256": schema_sha256,
                "codebook_path": args.codebook,
                "codebook_sha256": codebook_sha256,
                "system_prompt_path": args.system_prompt,
                "system_prompt_sha256": system_prompt_sha256,
                "user_template_path": args.user_template,
                "user_template_sha256": user_template_sha256,
                "request": request_body,
            }
            try:
                raw_response = call_openrouter(api_key, request_body, app_cfg, args.timeout, args.retries)
                content = extract_content(raw_response)
                annotation, parse_error = parse_model_json(content)
                validation_error = validate_annotation(annotation, schema)
                record.update(
                    {
                        "raw_response": raw_response,
                        "raw_content": content,
                        "annotation": annotation,
                        "parse_error": parse_error,
                        "validation_error": validation_error,
                        "ok": parse_error is None and validation_error is None,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                record.update({"ok": False, "runtime_error": repr(exc)})
            record["finished_at_utc"] = dt.datetime.utcnow().isoformat() + "Z"
            append_jsonl(args.output, record)

            # Report per request: a failure is otherwise only visible by opening the
            # output file, which makes a broken run look like a fast successful one.
            label = f"{novel.get('novel_id')} | {model}"
            if record.get("ok"):
                n_relations = len((record.get("annotation") or {}).get("relations") or [])
                tqdm.write(f"OK   {label} | {n_relations} relations")
            else:
                reason = (
                    record.get("runtime_error")
                    or record.get("parse_error")
                    or record.get("validation_error")
                    or "unknown error"
                )
                tqdm.write(f"FAIL {label} | {str(reason)[:600]}")


if __name__ == "__main__":
    main()
