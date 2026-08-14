#!/usr/bin/env python3
"""Build a corpus JSONL from plain-text novels plus a metadata CSV.

The metadata CSV drives the build: one row per novel, with the columns
novel_id, title, author, year, filename. Each filename is resolved against
--texts-dir and read as UTF-8.

With --split-chars, novels longer than the threshold are cut into several
records. Cuts are placed on the most meaningful boundary available inside the
window: a chapter heading first, then a paragraph break, then a sentence end.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Tuple

REQUIRED_COLUMNS = ["novel_id", "title", "author", "year", "filename"]
# Kept in the record when the metadata provides them; absent metadata is not an error.
OPTIONAL_COLUMNS = ["orientation"]

# A heading is a short line, preceded by a blank line, that is either a keyword
# ("CHAPITRE II", "Deuxieme partie") or a bare roman/arabic numeral. Group 1 is
# the heading itself: the cut goes there, so the heading opens the next chunk.
DEFAULT_CHAPTER_REGEX = (
    r"\n[ \t]*\n\s*"
    r"((?i:chapitre|livre|partie|tome|section|prologue|épilogue|epilogue"
    r"|chapter|book|part)\b[^\n]{0,80}"
    r"|[IVXLCDM]{1,7}[.)]?"
    r"|\d{1,3}[.)]?)"
    r"[ \t]*(?=\n)"
)
PARAGRAPH_RE = re.compile(r"\n[ \t]*\n\s*")
SENTENCE_RE = re.compile(r"(?<=[.!?…])[»”\"')\]]*\s+")


class Boundary(NamedTuple):
    """A cut candidate: where to look, and how full the chunk must already be."""

    name: str
    pattern: re.Pattern[str]
    min_fill: float  # never cut before this fraction of the window is used
    group: int  # cut at the start of this group, or at the match end when -1


def read_metadata(path: str | Path) -> List[Dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path}: missing column(s): {', '.join(missing)}")
        return [row for row in reader if any((v or "").strip() for v in row.values())]


def parse_year(raw: str) -> int | str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return raw


def build_record(row: Dict[str, str], texts_dir: Path) -> Dict[str, Any]:
    novel_id = (row.get("novel_id") or "").strip()
    if not novel_id:
        raise ValueError("row with an empty novel_id")
    filename = (row.get("filename") or "").strip()
    if not filename:
        raise ValueError(f"{novel_id}: empty filename")

    text_path = texts_dir / filename
    if not text_path.is_file():
        raise FileNotFoundError(f"{novel_id}: text file not found: {text_path}")
    text = text_path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"{novel_id}: text file is empty: {text_path}")

    record = {
        "novel_id": novel_id,
        "title": (row.get("title") or "").strip(),
        "author": (row.get("author") or "").strip(),
        "year": parse_year(row.get("year", "")),
        "text": text,
    }
    # Optional grouping columns are carried through when the metadata has them,
    # so downstream analysis can split the corpus without re-reading the CSV.
    for column in OPTIONAL_COLUMNS:
        value = (row.get(column) or "").strip()
        if value:
            record[column] = value
    return record


def compile_boundaries(chapter_regex: str) -> List[Boundary]:
    try:
        chapter = re.compile(chapter_regex)
    except re.error as exc:
        raise ValueError(f"invalid --chapter-regex: {exc}") from exc
    return [
        Boundary("chapter", chapter, 0.25, 1 if chapter.groups else 0),
        Boundary("paragraph", PARAGRAPH_RE, 0.50, -1),
        Boundary("sentence", SENTENCE_RE, 0.75, -1),
    ]


def find_cut(text: str, start: int, limit: int, boundaries: List[Boundary]) -> int:
    """Offset where the chunk opened at `start` should end, never past `limit`."""
    window = limit - start
    for boundary in boundaries:
        floor = start + int(window * boundary.min_fill)
        last = None
        for match in boundary.pattern.finditer(text, floor, limit):
            last = match
        if last is None:
            continue
        cut = last.end() if boundary.group < 0 else last.start(boundary.group)
        if start < cut <= limit:
            return cut
    return limit  # no boundary found: hard cut rather than exceed the threshold


def split_spans(text: str, max_chars: int, boundaries: List[Boundary]) -> List[Tuple[int, int]]:
    """Cut `text` into (start, end) spans of at most `max_chars` characters."""
    spans: List[Tuple[int, int]] = []
    start = 0
    while len(text) - start > max_chars:
        cut = find_cut(text, start, start + max_chars, boundaries)
        spans.append((start, cut))
        start = cut
    spans.append((start, len(text)))

    trimmed: List[Tuple[int, int]] = []
    for span_start, span_end in spans:
        chunk = text[span_start:span_end]
        lead = len(chunk) - len(chunk.lstrip())
        span_start, span_end = span_start + lead, span_end - (len(chunk) - len(chunk.rstrip()))
        if span_start < span_end:
            trimmed.append((span_start, span_end))
    return trimmed


def chunk_record(record: Dict[str, Any], max_chars: int, boundaries: List[Boundary]) -> List[Dict[str, Any]]:
    """Expand one novel record into its chunk records, keeping the metadata."""
    text = record["text"]
    spans = split_spans(text, max_chars, boundaries)
    width = len(str(len(spans)))
    chunks: List[Dict[str, Any]] = []
    for index, (start, end) in enumerate(spans, start=1):
        chunk = dict(record)
        # A single chunk keeps the plain novel_id; grouping still works through
        # source_novel_id, which every record carries once splitting is on.
        if len(spans) > 1:
            chunk["novel_id"] = f"{record['novel_id']}__p{index:0{width}d}"
        chunk["source_novel_id"] = record["novel_id"]
        chunk["chunk_index"] = index
        chunk["chunk_count"] = len(spans)
        chunk["char_start"] = start
        chunk["char_end"] = end
        chunk["text"] = text[start:end]
        chunks.append(chunk)
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata", required=True, help="Metadata CSV, one row per novel")
    parser.add_argument("--texts-dir", required=True, help="Directory holding the .txt files")
    parser.add_argument("--output", required=True, help="Corpus JSONL to write")
    parser.add_argument(
        "--split-chars",
        type=int,
        help="Split novels longer than this many characters into several records",
    )
    parser.add_argument(
        "--chapter-regex",
        default=DEFAULT_CHAPTER_REGEX,
        help="Preferred cut boundary; group 1, when present, marks the heading start",
    )
    args = parser.parse_args()

    boundaries: List[Boundary] = []
    if args.split_chars is not None:
        if args.split_chars < 1000:
            print("--split-chars must be at least 1000", file=sys.stderr)
            sys.exit(1)
        try:
            boundaries = compile_boundaries(args.chapter_regex)
        except ValueError as exc:
            print(f"ERROR {exc}", file=sys.stderr)
            sys.exit(1)

    texts_dir = Path(args.texts_dir)
    rows = read_metadata(args.metadata)
    if not rows:
        print(f"No rows in {args.metadata}", file=sys.stderr)
        sys.exit(1)

    records: List[Dict[str, Any]] = []
    summaries: List[str] = []
    errors: List[str] = []
    seen: set[str] = set()
    for row in rows:
        try:
            record = build_record(row, texts_dir)
        except (ValueError, FileNotFoundError) as exc:
            errors.append(str(exc))
            continue
        if record["novel_id"] in seen:
            errors.append(f"{record['novel_id']}: duplicate novel_id")
            continue
        seen.add(record["novel_id"])

        size = len(record["text"])
        if args.split_chars is None:
            records.append(record)
            summaries.append(f"{record['novel_id']}: {size} chars")
            continue
        chunks = chunk_record(record, args.split_chars, boundaries)
        records.extend(chunks)
        longest_chunk = max(len(c["text"]) for c in chunks)
        summaries.append(
            f"{record['novel_id']}: {size} chars -> {len(chunks)} chunk(s), "
            f"longest {longest_chunk}"
        )

    for message in errors:
        print(f"ERROR {message}", file=sys.stderr)
    if errors:
        print(f"{len(errors)} row(s) failed; nothing written.", file=sys.stderr)
        sys.exit(1)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    longest = max(len(r["text"]) for r in records)
    for summary in summaries:
        print(summary)
    unit = "record(s)" if args.split_chars is not None else "novel(s)"
    print(f"\nWrote {len(records)} {unit} to {output}")
    print(f"Longest text: {longest} chars -> run with --max-chars {longest + 1000} or more")


if __name__ == "__main__":
    main()
