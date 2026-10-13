#!/usr/bin/env python3
"""
Geniza Explorer — Translation Gap Detector

Scans every document in data/docs/ and ranks them by how much information
appears to have been lost between the English `description` and the Hebrew
`description_he` (which was produced by Haiku as a short summary, not a
full translation).

Outputs:
    .cache/translation_gaps.csv   — full ranked table for review
    stdout                        — summary stats + top-N preview

Usage:
    python find_translation_gaps.py                  # default: top 200
    python find_translation_gaps.py --top 500
    python find_translation_gaps.py --min-en 300     # only consider EN >= 300 chars
    python find_translation_gaps.py --metric ratio   # rank by length ratio instead

Gap signals (per document):
    en_len           — characters in English description
    he_len           — characters in Hebrew description
    ratio            — he_len / en_len  (lower = more compression)
    dropped_years    — 3-4 digit numbers present in EN but missing from HE
                       (good proxy for lost dates / shelfmark numbers)
    dropped_quotes   — count of "double-quoted" or 'single-quoted' spans in
                       EN that have no quoted analogue in HE
    score            — composite: (en_len - he_len) * (1 - min(ratio, 1))
                       favors long EN that got compressed hard
"""

import argparse
import csv
import json
import re
from pathlib import Path

DOCS_DIR = Path("data/docs")
OUT_CSV  = Path(".cache/translation_gaps.csv")

# 3-4 digit numbers — captures years (1105, 1417) and shelfmark fragments.
NUM_RE = re.compile(r"\b\d{3,4}\b")
# Quoted spans: "...", '...', “...”, ‘...’ — captures cited source text.
QUOTE_RE = re.compile(r'"[^"]{2,}"|\'[^\']{2,}\'|“[^”]{2,}”|‘[^’]{2,}’')


def extract_numbers(text):
    return set(NUM_RE.findall(text or ""))


def count_quotes(text):
    return len(QUOTE_RE.findall(text or ""))


def compute_gap(doc_id, desc_en, desc_he):
    en_len = len(desc_en)
    he_len = len(desc_he)
    ratio  = he_len / en_len if en_len else 1.0

    en_nums = extract_numbers(desc_en)
    he_nums = extract_numbers(desc_he)
    dropped_years = len(en_nums - he_nums)

    en_quotes = count_quotes(desc_en)
    he_quotes = count_quotes(desc_he)
    dropped_quotes = max(0, en_quotes - he_quotes)

    score = (en_len - he_len) * (1 - min(ratio, 1.0))

    return {
        "id": doc_id,
        "en_len": en_len,
        "he_len": he_len,
        "ratio": round(ratio, 3),
        "dropped_years": dropped_years,
        "dropped_quotes": dropped_quotes,
        "score": round(score, 1),
        "desc_en": desc_en,
        "desc_he": desc_he,
    }


def iter_docs():
    for path in DOCS_DIR.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        yield doc


def main():
    parser = argparse.ArgumentParser(
        description="Find documents with the largest EN/HE description gaps")
    parser.add_argument("--top",     type=int,   default=200,
                        help="How many to print + write to CSV (default: 200)")
    parser.add_argument("--min-en",  type=int,   default=200,
                        help="Skip docs whose EN description is shorter than this "
                             "(default: 200 chars — short EN can't have a big gap)")
    parser.add_argument("--metric",  choices=["score", "ratio", "diff", "years"],
                        default="score",
                        help="Ranking metric (default: score)")
    parser.add_argument("--out",     type=Path,  default=OUT_CSV,
                        help=f"Output CSV path (default: {OUT_CSV})")
    args = parser.parse_args()

    if not DOCS_DIR.exists():
        raise SystemExit(f"ERROR: {DOCS_DIR} not found. Run build.py first.")

    rows = []
    skipped_short = 0
    skipped_no_he = 0
    total = 0
    for doc in iter_docs():
        total += 1
        desc_en = (doc.get("description") or "").strip()
        desc_he = (doc.get("description_he") or "").strip()
        if not desc_en or len(desc_en) < args.min_en:
            skipped_short += 1
            continue
        if not desc_he:
            skipped_no_he += 1
            continue
        rows.append(compute_gap(doc["id"], desc_en, desc_he))

    if args.metric == "score":
        rows.sort(key=lambda r: r["score"], reverse=True)
    elif args.metric == "ratio":
        rows.sort(key=lambda r: r["ratio"])           # lowest ratio first
    elif args.metric == "diff":
        rows.sort(key=lambda r: r["en_len"] - r["he_len"], reverse=True)
    elif args.metric == "years":
        rows.sort(key=lambda r: (r["dropped_years"], r["score"]), reverse=True)

    top = rows[: args.top]

    # ── Write CSV ────────────────────────────────────────────────────────────
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "en_len", "he_len", "ratio",
                        "dropped_years", "dropped_quotes", "score",
                        "desc_en", "desc_he"],
        )
        writer.writeheader()
        for r in top:
            writer.writerow(r)

    # ── Summary ──────────────────────────────────────────────────────────────
    n = len(rows)
    print(f"Scanned {total:,} docs")
    print(f"  skipped (EN < {args.min_en} chars): {skipped_short:,}")
    print(f"  skipped (no HE description):       {skipped_no_he:,}")
    print(f"  considered:                        {n:,}")
    if not n:
        return

    avg_ratio = sum(r["ratio"] for r in rows) / n
    median_ratio = sorted(r["ratio"] for r in rows)[n // 2]
    under_15 = sum(1 for r in rows if r["ratio"] < 0.15)
    under_25 = sum(1 for r in rows if r["ratio"] < 0.25)
    print()
    print(f"Length ratio (HE/EN):  avg={avg_ratio:.2f}  median={median_ratio:.2f}")
    print(f"  ratio < 0.15: {under_15:,}  ({100*under_15/n:.1f}%)")
    print(f"  ratio < 0.25: {under_25:,}  ({100*under_25/n:.1f}%)")
    print()
    print(f"Wrote top {len(top):,} → {args.out}")
    print()
    print(f"── Top 10 by {args.metric} ──")
    for r in top[:10]:
        print(f"  id={r['id']:>6}  en={r['en_len']:>4}  he={r['he_len']:>4}  "
              f"ratio={r['ratio']:.2f}  score={r['score']:>7.0f}  "
              f"yrs_lost={r['dropped_years']}")
        # Truncated previews for quick eyeballing
        en_preview = r["desc_en"][:140].replace("\n", " ")
        he_preview = r["desc_he"][:140].replace("\n", " ")
        print(f"    EN: {en_preview}{'…' if len(r['desc_en']) > 140 else ''}")
        print(f"    HE: {he_preview}{'…' if len(r['desc_he']) > 140 else ''}")


if __name__ == "__main__":
    main()
