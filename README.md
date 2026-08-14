# LLM Annotation: relationships between characters

Framework for LLM-assisted annotation of romantic, erotic, conjugal, desirous and queer-coded relationships in late nineteenth- and early twentieth-century novels.

The repository is designed for a reproducible workflow on a corpus of about 400 novels:

1. create a small human ground truth, for instance 10 novels;
2. run the same annotation prompt through several OpenRouter models;
3. benchmark relation detection and closed-category annotation;
4. inspect disagreements and refine the codebook before scaling up.

## What is annotated?

The unit of annotation is **one relationship**: a romantic, sexual, conjugal, desirous, or strongly ambiguous relation between two characters or groups of characters. Ordinary friendship is not annotated unless the text strongly eroticizes, romanticizes, scandalizes, or codes the relation.

Each relation receives eleven closed variables, in three families:

- **Participants and shape**: `relation_type`, `structure`
- **Nature and rules of the bond**: `status`, `reciprocity`, `exclusivity`, `adultery`
- **Representation and narrative role**: `explicitness`, `explicitness_in_plot`, `centrality`, `framing`, `outcome`

It also receives structured evidence, a confidence level, and a brief comment.

`relation_type` describes the gender configuration of the participants (`female_male`, `female_female`, `male_male`, `mixed_gender`, `unknown_gender`, `queer`, `unclear`). It does not encode whether the relation is certainly romantic or sexual.

Evidence is a list of 1 to 10 items, each with an optional verbatim `quote` from the novel, an optional `locator`, and a required `description`. Quotes are reproduced exactly, so they can be checked against the source text.

## Schema versions

`schemas/novel_annotation_v2.schema.json` is the current schema. It followed a first manual annotation round on Delarue-Mardrus, *L'Ange et les pervers* (1930), which showed two gaps: `relation_type` could not describe a gender non-conforming protagonist without wrongly implying the text was uninformative, and the grid recorded how a relation is represented but nothing about what the relation is. Version 2 therefore adds `queer` and splits the old `mixed_or_multi` into `mixed_gender` (gender pattern) and the new `structure` field (number and shape of participants), adds the four bond-structure fields, adds `explicitness_in_plot`, and replaces plain-string evidence with quotable evidence objects.

`schemas/novel_annotation.schema.json` is version 1, kept unchanged so the first benchmark round stays reproducible. Use it only to re-run that round.

## Prompt architecture

The codebook is the single source of truth for label definitions. The runner reads `codebook/annotation_grid.md` and injects it into the model context at runtime, after the stable system prompt and before the user prompt.

This keeps the prompts short and avoids maintaining duplicate definitions in several files:

- `prompts/system_prompt.md` gives the general annotation role and decision principles;
- `codebook/annotation_grid.md` defines the annotation unit and all labels;
- `prompts/user_prompt_template.md` supplies the novel metadata and text.

For reproducibility, each output record logs the path and SHA-256 hash of the schema, codebook, system prompt, and user template used for the request.

## Repository layout

```text
codebook/annotation_grid.md              Human-readable annotation grid
schemas/novel_annotation_v2.schema.json  JSON Schema used for structured output (current)
schemas/novel_annotation.schema.json     Version 1 schema, kept for reproducibility
prompts/system_prompt.md                 Stable system prompt
prompts/user_prompt_template.md          User prompt template for a novel
src/build_metadata.py                    Build the metadata CSV by walking a corpus tree
src/build_corpus.py                      Build the corpus JSONL from .txt files + metadata CSV
src/annotate_openrouter.py               OpenRouter annotation runner
src/evaluate.py                          Benchmark predictions against gold data
src/validate_jsonl.py                    Pre-flight checks for corpus/gold/predictions
config/models.example.yaml               Example benchmark configuration
data/corpus_sample.jsonl                 Example input corpus format
data/ground_truth_sample.jsonl           Example ground truth format
```

## Installation

```bash
git clone https://github.com/floriancafiero/annotation_literature_relationships.git
cd annotation_literature_relationships
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set your OpenRouter API key:

```bash
export OPENROUTER_API_KEY="sk-or-..."
```

## Input format

The corpus is a JSONL file, one novel per line:

```json
{"novel_id":"vivien_1904_femme","title":"Une femme m'apparut","author":"Renée Vivien","year":1904,"text":"Full text or benchmark excerpt..."}
```

## Build the metadata CSV

Writing the metadata CSV by hand does not scale past a handful of novels.
`src/build_metadata.py` walks a corpus tree and writes one row per text file:

```bash
python src/build_metadata.py \
  --texts-dir data/corpus_chr \
  --output data/corpus_chr_metadata.csv
```

Each subdirectory is one group, and its name is recorded in an `orientation` column
(`corpus_lesbiennes/` -> `lesbiennes`). Files ending in `_lemmatized.txt` are skipped.

Title, author and year are read from the header block most files carry — Wikisource export,
Gallica/BnF catalogue block, or Project Gutenberg header. A file that opens straight on its
text has no header to read: those rows fall back to the filename, are marked `filename` in the
`metadata_source` column, and are listed at the end of the run so they can be completed by
hand. The year is left empty rather than guessed; rows missing one are listed too.

Re-running the script keeps every value already in the CSV and only fills empty cells, so hand
corrections survive a rebuild. Pass `--no-merge` to discard them and re-extract from scratch.

## Build the corpus

`src/build_corpus.py` turns plain-text novels into the JSONL above. The build is driven by a
metadata CSV with the columns `novel_id`, `title`, `author`, `year`, `filename`, one row per
novel; each `filename` is resolved against `--texts-dir` and read as UTF-8, so a `filename`
of `corpus_lesbiennes/colette_vagabonde.txt` works with `--texts-dir data/corpus_chr`. An
`orientation` column, when present, is carried into each record.

```bash
python src/build_corpus.py \
  --metadata data/corpus_metadata.csv \
  --texts-dir data/corpus \
  --output data/corpus.jsonl
```

The build is all-or-nothing: every faulty row is reported and nothing is written, so a
half-built corpus is never annotated. The final line reports the longest text and the
`--max-chars` value the annotation run needs.

### Splitting long novels

A full novel often exceeds what a model can take in one request. `--split-chars` cuts each
novel into records of at most that many characters:

```bash
python src/build_corpus.py \
  --metadata data/corpus_metadata.csv \
  --texts-dir data/corpus \
  --output data/corpus.jsonl \
  --split-chars 60000
```

Cuts are not blind. Inside each window the script takes the most meaningful boundary
available, preferring the latest one that fits:

1. a **chapter heading** — a short line after a blank line, either a keyword (`CHAPITRE II`,
   `Deuxième partie`, `Prologue`) or a bare roman/arabic numeral;
2. a **paragraph break**, if no heading falls in the last 75% of the window;
3. a **sentence end**, if no paragraph break falls in the last 50%;
4. a hard cut at the threshold, only if the text offers no boundary at all.

Each chunk gains `source_novel_id`, `chunk_index`, `chunk_count`, `char_start`, and
`char_end`, so chunks can be grouped back into the novel and any quote can be located in the
source file. When a novel is split, its chunks get suffixed ids (`gide_1925__p01`); a novel
that fits in one chunk keeps its plain `novel_id`.

Predictions are then keyed by chunk id, so a ground truth used with `src/evaluate.py` has to
be annotated at the same granularity.

Use `--chapter-regex` when a corpus numbers its divisions differently. If the pattern has a
capture group, the cut is placed at the start of group 1, so the heading opens the next chunk:

```bash
python src/build_corpus.py ... --split-chars 60000 --chapter-regex '\n[ \t]*\n\s*(LETTRE [IVXLC]+)'
```

## Configure models

Do not edit the example file directly. Copy it and record the exact model slugs used for the benchmark:

```bash
cp config/models.example.yaml config/models.local.yaml
```

Then edit `config/models.local.yaml`. Keep the same generation parameters across models for the main comparison.

## Pre-flight checks

Before running a paid benchmark, validate the corpus and the gold file:

```bash
python src/validate_jsonl.py \
  --corpus data/corpus_sample.jsonl \
  --gold data/ground_truth_sample.jsonl \
  --schema schemas/novel_annotation_v2.schema.json
```

This catches invalid JSONL, missing `novel_id` / `text`, duplicate novel ids in the corpus, and gold annotations that do not match the schema.

## Run annotation

```bash
python src/annotate_openrouter.py \
  --input data/corpus_sample.jsonl \
  --output runs/predictions.jsonl \
  --models-config config/models.local.yaml \
  --schema schemas/novel_annotation_v2.schema.json \
  --codebook codebook/annotation_grid.md \
  --max-chars 120000
```

By default, the script refuses to silently truncate texts longer than `--max-chars`. Use `--allow-truncate` only for documented experiments where the same fixed truncation is intended for all models.

Each record carries every field of its corpus record except the text itself, which is identified
by `input_sha256` and `input_num_chars`. Grouping columns such as `orientation`, and the chunk
provenance written by `--split-chars` (`source_novel_id`, `chunk_index`, `char_start`, ...), stay
attached to the annotation they belong to.

### Resuming a run

One request is made per novel per model, and each is appended to `--output` as soon as it
returns, so the output file is its own progress log. `--resume` reads it and skips the
novel/model pairs already recorded:

```bash
python src/annotate_openrouter.py \
  --input data/corpus_chr.jsonl \
  --output runs/predictions_chr.jsonl \
  --models-config config/models.local.yaml \
  --schema schemas/novel_annotation_v2.schema.json \
  --max-chars 120000 --allow-truncate \
  --resume
```

A run interrupted at request 1800 of 2000 therefore costs 200 requests to finish, not 2000.
Resuming also truncates away a half-written final record left by a killed run, which would
otherwise stop the file parsing as JSONL.

Pairs whose recorded attempt failed are skipped like any other, on the assumption that a
failure already seen is not worth paying for again. Add `--retry-failed` to request them once
more; the new attempt is appended next to the old one, so keep the last record per novel/model
pair when reading the file.

The script records, for each novel and model: model slug, generation parameters, SHA-256 hash of the input text, schema/codebook/prompt hashes, request body, raw response, parsed JSON annotation, and JSON-schema validation status.

## Reproducibility settings

The default configuration is conservative:

```yaml
temperature: 0
top_p: 1
seed: 42
top_k: 1
```

OpenRouter documents `temperature`, `top_p`, `top_k`, and `seed` as request parameters, but also notes that unsupported parameters may be ignored by some providers or models, for instance `top_k` for OpenAI models. Therefore the repository logs the full request and raw response for every run. Do not rely on a single parameter as a guarantee of bitwise determinism.

## Evaluate against ground truth

```bash
python src/evaluate.py \
  --predictions runs/predictions.jsonl \
  --gold data/ground_truth_sample.jsonl \
  --output runs/evaluation_summary.json
```

The evaluator performs approximate relation matching by normalized character-name overlap, then reports relation detection precision/recall/F1 and per-field accuracy among matched relations.
