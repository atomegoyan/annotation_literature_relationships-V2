"""Export an LLM predictions JSONL into a compact Excel workbook for human review.

Full texts, requests and raw responses are dropped. Sheets:
  Novels    one row per novel (metadata, status, corpus notes)
  Relations one row per annotated relation, evidence quotes inline, review columns on the right
  Evidence  one row per evidence quote, review columns on the right

Usage:
  python src/export_review.py runs/predictions_chr_sample25.jsonl review_sample25.xlsx
"""
import argparse
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

REL_FIELDS = [
    "relation_type", "structure", "status", "reciprocity", "exclusivity", "adultery",
    "explicitness", "explicitness_in_plot", "centrality", "framing", "outcome", "confidence",
]
REVIEW_HEADERS = ["REVIEW: correct? (yes / partial / no)", "REVIEW: comments"]
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
REVIEW_FILL = PatternFill("solid", fgColor="C55A11")


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def fmt_evidence(ev):
    return "\n\n".join(
        f"[{e.get('locator') or '?'}] « {e.get('quote', '')} »\n  → {e.get('description', '')}"
        for e in ev
    )


def write_sheet(wb, title, headers, rows, widths, review_cols=0):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for r in rows:
        ws.append(r)
    first_review = len(headers) - review_cols
    for i, cell in enumerate(ws[1], start=1):
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = REVIEW_FILL if i > first_review else HEADER_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    return ws


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("predictions")
    ap.add_argument("output", help="output .xlsx path")
    ap.add_argument("--only-ok", action="store_true", help="skip novels whose run failed validation")
    args = ap.parse_args()

    novels, relations, evidence = [], [], []
    for p in load(args.predictions):
        ann = p.get("annotation") or {}
        if args.only_ok and not p.get("ok"):
            continue
        rels = ann.get("relations") or []
        meta = [p["novel_id"], p.get("title"), p.get("author"), p.get("year"), p.get("orientation"), p.get("model")]
        novels.append(meta + [
            "ok" if p.get("ok") else "FAILED",
            p.get("parse_error") or p.get("validation_error") or "",
            len(rels), ann.get("corpus_notes", ""),
        ])
        for r in rels:
            ev = r.get("evidence") or []
            relations.append(
                meta[:5] + [r.get("relation_id"), " ↔ ".join(r.get("characters") or [])]
                + [r.get(k) for k in REL_FIELDS]
                + [r.get("comment", ""), len(ev), fmt_evidence(ev)] + [""] * len(REVIEW_HEADERS)
            )
            for e in ev:
                evidence.append(
                    meta[:2] + [p.get("orientation"), r.get("relation_id"), " ↔ ".join(r.get("characters") or []),
                                r.get("relation_type"), r.get("status"), e.get("locator"),
                                e.get("quote"), e.get("description")] + [""] * len(REVIEW_HEADERS)
                )

    wb = Workbook()
    wb.remove(wb.active)
    write_sheet(
        wb, "Novels",
        ["novel_id", "title", "author", "year", "orientation", "model", "status", "error", "n_relations", "corpus_notes"],
        novels, [26, 24, 18, 8, 14, 24, 9, 30, 11, 90],
    )
    write_sheet(
        wb, "Relations",
        ["novel_id", "title", "author", "year", "orientation", "relation_id", "characters"]
        + REL_FIELDS + ["LLM comment", "n_evidence", "evidence (locator, quote, LLM justification)"] + REVIEW_HEADERS,
        relations,
        [24, 22, 16, 7, 12, 8, 30] + [14] * len(REL_FIELDS) + [60, 8, 100, 20, 40],
        review_cols=len(REVIEW_HEADERS),
    )
    write_sheet(
        wb, "Evidence",
        ["novel_id", "title", "orientation", "relation_id", "characters", "relation_type", "status",
         "locator", "quote", "LLM justification"] + REVIEW_HEADERS,
        evidence, [24, 22, 12, 8, 30, 14, 14, 12, 70, 60, 20, 40],
        review_cols=len(REVIEW_HEADERS),
    )
    wb.save(args.output)
    print(f"{len(novels)} novels, {len(relations)} relations, {len(evidence)} evidence quotes -> {args.output}")


if __name__ == "__main__":
    main()
