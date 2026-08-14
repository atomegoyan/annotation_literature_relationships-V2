#!/usr/bin/env python3
"""Build the metadata CSV for a corpus tree, one row per text file.

The tree is expected to hold one subdirectory per group, the directory name
carrying the author's sexual orientation as recorded by the corpus:

    data/corpus_chr/corpus_lesbiennes/colette_vagabonde.txt

Files whose name ends with `_lemmatized.txt` are companion files, not novels,
and are skipped.

Title, author and year are read from the header block most files carry. Three
shapes occur in this corpus: the Wikisource export,

    Le Moulin du Frau                            <- title
    Eugene Le Roy                                <- author
    Bibliotheque-Charpentier, 1914 (p. i-TdM).   <- imprint

the Gallica / BnF catalogue block ("Titre :", "Auteur :", "Date d'edition :"),
and the Project Gutenberg header.

The Wikisource shape is only trusted when the author line can be matched against
the filename prefix, which is what keeps a first line of narrative from being
read as a title. Files that fail that check fall back to the filename and are
marked `filename` in the metadata_source column, so they can be reviewed and
completed by hand; their author is still filled in when another file by the same
author carries a header. A year printed in parentheses next to the title wins
over the imprint year: the imprint is often a later reprint.

Re-running is safe: values already present in the output CSV are kept, and only
empty cells are filled. Hand corrections therefore survive a rebuild.
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, NamedTuple

COLUMNS = ["novel_id", "title", "author", "year", "filename", "orientation", "metadata_source"]

LEMMATIZED_SUFFIX = "_lemmatized"
# Wide enough for the whole corpus (19th-20th century) while excluding the
# four-digit numbers that turn up in running text.
YEAR_MIN, YEAR_MAX = 1600, 1960

YEAR_RE = re.compile(r"\b(1[6-9]\d{2}|19[0-5]\d|1960)\b")
PARENTHESISED_YEAR_RE = re.compile(r"\((?:[^()]*?\b)?(1[6-9]\d{2})\b[^()]*\)")
# Parentheticals that are volume/edition apparatus rather than part of a title.
TITLE_NOISE_RE = re.compile(
    r"\((?:[^()]*\d{4}[^()]*"
    r"|(?i:premi[eè]re|deuxi[eè]me|seconde|troisi[eè]me|quatri[eè]me)\s+partie"
    r"|(?i:texte\s+entier|[^()]*\bp\.\s*[^()]*))\)"
)
GUTENBERG_FIELD_RE = re.compile(r"^(Title|Author)\s*:\s*(.+)$", re.IGNORECASE)
GUTENBERG_BANNER_RE = re.compile(
    r"Project Gutenberg e-?book of (?P<title>.+?),?\s+by\s+(?P<author>.+?)\s*$", re.IGNORECASE
)

# "Gallimard, Paris, 1924" is an imprint; "Les Heures longues 1914-1917" is a
# title that happens to end on a year, so the comma is what separates them.
IMPRINT_RE = re.compile(r",[^,]*\b(?:1[6-9]\d{2}|20[0-2]\d)\b[\s.)\]]*$")
ASSET_RE = re.compile(r"^\S+\.(?:gif|jpe?g|png|svg)$", re.IGNORECASE)
# Reprint sets state the collection before the work: "Oeuvres completes ..., tome 4".
COLLECTION_RE = re.compile(r"^(?i:[cœoe]uvres\s+compl[eè]tes)\b.*$")
MAX_TITLE_CHARS = 120  # beyond this the line is prose, not a title

# Gallica / BnF digitisations open on a catalogue block:
#   Titre : Sous la hache / Elemir Bourges
#   Auteur : Bourges, Elemir (1852-1925). Auteur du texte
#   Date d'edition : 1885
BNF_FIELD_RE = re.compile(
    r"^(Titre|Auteur|Date d['’]\s*[ée]dition)\s*:\s*(.+)$", re.IGNORECASE
)
BNF_AUTHOR_NOISE_RE = re.compile(r"\.?\s*Auteur du texte.*$|\((?:[^()]*\d{4}[^()]*)\)", re.IGNORECASE)
# "1874-1945" next to a name is a lifespan, not a publication date; "1921-1922"
# next to a title is the span over which the work came out.
LIFESPAN_MAX_SPAN = 15
YEAR_RANGE_RE = re.compile(r"\b(1[6-9]\d{2}|20[0-2]\d)\s*[-–—]\s*(1[6-9]\d{2}|20[0-2]\d)\b")

# How far into the file a header can reach, and how much of it we read.
HEADER_CHARS = 4000
HEADER_LINES = 8
AUTHOR_SEARCH_LINES = 4  # an author line this deep or deeper is not a header
MAX_AUTHOR_LINE_CHARS = 40  # "Jacques d'Adelswaerd-Fersen" fits; a sentence does not


class Entry(NamedTuple):
    novel_id: str
    title: str
    author: str
    year: str
    filename: str
    orientation: str
    metadata_source: str


def fold(text: str) -> str:
    """Reduce to bare lowercase letters, so 'Andre Gide' matches 'gide'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed.lower() if c.isalpha() and ord(c) < 128)


def clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace("\xa0", " ")).strip()


def header_lines(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        head = f.read(HEADER_CHARS)
    lines = [clean_line(line) for line in head.splitlines()]
    return [line for line in lines if line][:HEADER_LINES]


def clean_title(raw: str) -> str:
    title = raw.lstrip("<").strip()
    title = title.split("/Texte entier")[0]
    # Dropping the apparatus can leave two halves of a title touching, as in
    # "A la recherche... (1913) Du cote de chez Swann"; keep them apart.
    segments = [
        re.sub(r"\s+", " ", segment).strip(" ,;:.-")
        for segment in TITLE_NOISE_RE.split(title)
    ]
    segments = [segment for segment in segments if segment]
    # Keep the collection only when it is all there is to go on.
    named = [segment for segment in segments if not COLLECTION_RE.match(segment)]
    return " - ".join(named or segments)


def drop_lifespans(line: str) -> str:
    """Remove year ranges too wide to be a publication span."""
    return YEAR_RANGE_RE.sub(
        lambda m: "" if int(m.group(2)) - int(m.group(1)) > LIFESPAN_MAX_SPAN else m.group(0),
        line,
    )


def is_title_like(candidate: str) -> bool:
    """Whether a cleaned header line can be read as the work's title.

    Rules out the three things that sit next to an author line without being a
    title: the imprint, a stray asset name, and a run of narrative or blurb.
    """
    if not candidate or len(candidate) > MAX_TITLE_CHARS:
        return False
    if ASSET_RE.match(candidate) or IMPRINT_RE.search(candidate):
        return False
    return candidate[:1].isupper() or candidate[:1].isdigit()


def find_year(lines: List[str]) -> str:
    """Publication year: the one printed with the title, else the imprint's."""
    lines = [drop_lifespans(line) for line in lines[:6]]
    for line in lines[:3]:
        match = PARENTHESISED_YEAR_RE.search(line)
        if match and YEAR_MIN <= int(match.group(1)) <= YEAR_MAX:
            return match.group(1)
    # The imprint below the title is read first. A bare range on the title line
    # is the period the book covers ("Les Heures longues 1914-1917"); the same
    # range in an imprint is when it came out ("... 1887-1888 (p. 1-16).").
    for line in lines[1:] + lines[:1]:
        for candidate in YEAR_RE.findall(line):
            if YEAR_MIN <= int(candidate) <= YEAR_MAX:
                return candidate
    return ""


def parse_gutenberg(lines: List[str]) -> Dict[str, str] | None:
    """Project Gutenberg headers state the fields outright."""
    fields: Dict[str, str] = {}
    for line in lines:
        match = GUTENBERG_FIELD_RE.match(line)
        if match:
            fields[match.group(1).lower()] = match.group(2).strip()
    if "title" in fields and "author" in fields:
        return {
            "title": clean_title(fields["title"]),
            "author": fields["author"],
            "year": find_year(lines),
        }
    # Older releases only carry the banner: "The Project Gutenberg EBook of
    # La Marquise de Sade, by Rachilde".
    for line in lines:
        match = GUTENBERG_BANNER_RE.search(line)
        if match:
            return {
                "title": clean_title(match.group("title")),
                "author": match.group("author").strip(" .,"),
                "year": find_year(lines),
            }
    return None


def parse_bnf(lines: List[str]) -> Dict[str, str] | None:
    """Read the catalogue block of a Gallica / BnF digitisation."""
    fields: Dict[str, str] = {}
    for line in lines:
        match = BNF_FIELD_RE.match(line)
        if not match:
            continue
        key = "date" if match.group(1).lower().startswith("date") else match.group(1).lower()
        fields.setdefault(key, match.group(2).strip())
    if "titre" not in fields or "auteur" not in fields:
        return None

    # "Sous la hache / Elemir Bourges": everything after the slash restates the
    # author. Brackets and trailing ellipses are catalogue apparatus.
    title = fields["titre"].split(" / ")[0]
    title = re.sub(r"\[[^\]]*\]", " ", title)
    title = clean_title(title).rstrip(". ")

    # "Delarue-Mardrus, Lucie (1874-1945). Auteur du texte" -> "Lucie Delarue-Mardrus"
    author = BNF_AUTHOR_NOISE_RE.sub("", fields["auteur"]).strip(" .,")
    if "," in author:
        surname, given = author.split(",", 1)
        author = f"{given.strip()} {surname.strip()}".strip()

    year = ""
    if "date" in fields:
        match = YEAR_RE.search(drop_lifespans(fields["date"]))
        if match and YEAR_MIN <= int(match.group(0)) <= YEAR_MAX:
            year = match.group(0)
    if not title or not author:
        return None
    return {"title": title, "author": author, "year": year}


def parse_header(lines: List[str], author_token: str) -> Dict[str, str] | None:
    """Read title/author/year from the header, or None if it is not a header.

    The anchor is the author line: a short line, near the top, whose folded form
    contains the filename's author token. Without it the file opens on its text
    and there is nothing to read.
    """
    for parse_catalogue in (parse_bnf, parse_gutenberg):
        parsed = parse_catalogue(lines)
        if parsed:
            return parsed

    author_index = None
    for index, line in enumerate(lines[:AUTHOR_SEARCH_LINES]):
        if len(line) > MAX_AUTHOR_LINE_CHARS or author_token not in fold(line):
            continue
        # A credit line opens on the name. "/ par Jules Claretie" and lowercase
        # openings are wrapped fragments of the line above, not the credit.
        if not line[:1].isupper():
            continue
        author_index = index
        break
    if author_index is None:
        return None

    # The title sits on the line above the author, or on the one below when the
    # author is credited first.
    title = ""
    for index in (author_index - 1, author_index + 1):
        if 0 <= index < len(lines):
            candidate = clean_title(lines[index])
            if is_title_like(candidate):
                title = candidate
                break
    if not title:
        return None
    return {"title": title, "author": lines[author_index], "year": find_year(lines)}


def titlecase_from_slug(slug: str) -> str:
    return slug[:1].upper() + slug[1:] if slug else ""


def build_entry(path: Path, texts_dir: Path) -> Entry:
    stem = path.stem
    author_token = stem.split("_", 1)[0]
    relative = path.relative_to(texts_dir)
    orientation = relative.parts[0] if len(relative.parts) > 1 else ""
    orientation = re.sub(r"^corpus_", "", orientation)

    parsed = parse_header(header_lines(path), author_token)
    if parsed:
        return Entry(
            novel_id=stem,
            title=parsed["title"],
            author=parsed["author"],
            year=parsed["year"],
            filename=relative.as_posix(),
            orientation=orientation,
            metadata_source="header",
        )
    title_token = stem.split("_", 1)[1] if "_" in stem else stem
    return Entry(
        novel_id=stem,
        title=titlecase_from_slug(title_token),
        author=titlecase_from_slug(author_token),
        year="",
        filename=relative.as_posix(),
        orientation=orientation,
        metadata_source="filename",
    )


def borrow_authors(entries: List[Entry]) -> List[Entry]:
    """Give filename-derived rows the full author name a sibling file spells out.

    A fallback row only knows the surname slug ("Zola"); another file by the same
    author usually carries a header naming them in full ("Emile Zola"). The token
    is the filename prefix, so the two are the same author by construction.
    """
    named: Dict[str, Counter] = {}
    for entry in entries:
        if entry.metadata_source == "header":
            token = entry.novel_id.split("_", 1)[0]
            named.setdefault(token, Counter())[entry.author] += 1

    resolved: List[Entry] = []
    for entry in entries:
        token = entry.novel_id.split("_", 1)[0]
        if entry.metadata_source != "header" and named.get(token):
            entry = entry._replace(author=named[token].most_common(1)[0][0])
        resolved.append(entry)
    return resolved


def group_by_subdir(files: List[Path], texts_dir: Path) -> Dict[str, List[Path]]:
    groups: Dict[str, List[Path]] = {}
    for path in files:
        relative = path.relative_to(texts_dir)
        group = relative.parts[0] if len(relative.parts) > 1 else ""
        groups.setdefault(group, []).append(path)
    return groups


def sample_by_group(files: List[Path], texts_dir: Path, percent: float, seed: int) -> List[Path]:
    """Randomly keep `percent`% of the files in each top-level subdirectory.

    Sampling within each group, rather than across the whole tree, keeps the
    groups' relative sizes intact instead of letting the sample skew towards
    whichever group happens to be largest.
    """
    rng = random.Random(seed)
    sampled: List[Path] = []
    for group_files in group_by_subdir(files, texts_dir).values():
        k = min(len(group_files), max(1, round(len(group_files) * percent / 100)))
        sampled.extend(rng.sample(group_files, k))
    return sorted(sampled)


def sample_n_by_group(files: List[Path], texts_dir: Path, count: int, seed: int) -> List[Path]:
    """Randomly keep up to `count` files from each top-level subdirectory.

    A group with fewer than `count` files contributes all of its files.
    """
    rng = random.Random(seed)
    sampled: List[Path] = []
    for group_files in group_by_subdir(files, texts_dir).values():
        sampled.extend(rng.sample(group_files, min(len(group_files), count)))
    return sorted(sampled)


def read_existing(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return {(row.get("filename") or "").strip(): row for row in rows if row.get("filename")}


def merge(entry: Entry, existing: Dict[str, str]) -> Dict[str, str]:
    """Keep whatever is already in the CSV; only fill the cells left empty."""
    row = entry._asdict()
    for column in COLUMNS:
        current = (existing.get(column) or "").strip()
        if current:
            row[column] = current
    if any((existing.get(c) or "").strip() for c in ("title", "author", "year")):
        row["metadata_source"] = existing.get("metadata_source") or entry.metadata_source
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--texts-dir", required=True, help="Corpus root, holding one subdirectory per group")
    parser.add_argument("--output", required=True, help="Metadata CSV to write")
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Overwrite the output instead of keeping the values it already holds",
    )
    parser.add_argument(
        "--sample-percent",
        type=float,
        default=None,
        help="Randomly keep only this percent of files in each subdirectory (0-100)",
    )
    parser.add_argument(
        "--sample-count",
        type=int,
        default=None,
        help="Randomly keep at most this many files from each subdirectory (all of them if fewer are available)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed used with --sample-percent/--sample-count, for a reproducible sample (default: 42)",
    )
    args = parser.parse_args()

    if args.sample_percent is not None and args.sample_count is not None:
        print("ERROR --sample-percent and --sample-count are mutually exclusive", file=sys.stderr)
        sys.exit(1)

    texts_dir = Path(args.texts_dir)
    if not texts_dir.is_dir():
        print(f"ERROR not a directory: {texts_dir}", file=sys.stderr)
        sys.exit(1)

    files = sorted(
        p for p in texts_dir.rglob("*.txt") if not p.stem.endswith(LEMMATIZED_SUFFIX)
    )
    if not files:
        print(f"ERROR no .txt files under {texts_dir}", file=sys.stderr)
        sys.exit(1)

    if args.sample_percent is not None:
        if not 0 < args.sample_percent <= 100:
            print("ERROR --sample-percent must be between 0 (exclusive) and 100", file=sys.stderr)
            sys.exit(1)
        files = sample_by_group(files, texts_dir, args.sample_percent, args.seed)
        print(
            f"Sampled {len(files)} file(s) (~{args.sample_percent}% per subdirectory, seed={args.seed})"
        )
    elif args.sample_count is not None:
        if args.sample_count <= 0:
            print("ERROR --sample-count must be a positive integer", file=sys.stderr)
            sys.exit(1)
        files = sample_n_by_group(files, texts_dir, args.sample_count, args.seed)
        print(
            f"Sampled {len(files)} file(s) (up to {args.sample_count} per subdirectory, seed={args.seed})"
        )

    output = Path(args.output)
    existing = {} if args.no_merge else read_existing(output)

    seen: Dict[str, Path] = {}
    entries: List[Entry] = []
    errors: List[str] = []
    for path in files:
        entry = build_entry(path, texts_dir)
        if entry.novel_id in seen:
            errors.append(f"{entry.novel_id}: duplicate novel_id ({seen[entry.novel_id]} and {path})")
            continue
        seen[entry.novel_id] = path
        entries.append(entry)

    entries = borrow_authors(entries)
    rows: List[Dict[str, Any]] = [
        merge(entry, existing.get(entry.filename, {})) for entry in entries
    ]

    for message in errors:
        print(f"ERROR {message}", file=sys.stderr)
    if errors:
        print(f"{len(errors)} file(s) failed; nothing written.", file=sys.stderr)
        sys.exit(1)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    by_orientation: Dict[str, int] = {}
    for row in rows:
        by_orientation[row["orientation"]] = by_orientation.get(row["orientation"], 0) + 1
    from_filename = [r for r in rows if r["metadata_source"] == "filename"]
    missing_year = [r for r in rows if not (r.get("year") or "").strip()]

    print(f"Wrote {len(rows)} row(s) to {output}")
    for orientation, count in sorted(by_orientation.items()):
        print(f"  {orientation}: {count}")
    print(f"\n{len(rows) - len(from_filename)} row(s) read from a file header, {len(from_filename)} from the filename.")
    if from_filename:
        print("Review title/author for these (metadata_source=filename):")
        for row in from_filename:
            print(f"  {row['novel_id']}")
    if missing_year:
        print(f"\n{len(missing_year)} row(s) have no year; fill them by hand if the year matters:")
        for row in missing_year:
            print(f"  {row['novel_id']}")


if __name__ == "__main__":
    main()
