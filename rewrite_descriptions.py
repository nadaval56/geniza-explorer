#!/usr/bin/env python3
"""
Geniza Explorer — Hebrew Description Rewrite (Opus 4.7)

Re-writes the Hebrew description for documents that have the largest
gap between the English `description` and the (Haiku-generated) Hebrew
summary, using Claude Opus 4.7 via the Batch API.

Strategy:
    1. Scan data/docs/, score each doc by gap (same metric as
       find_translation_gaps.py: (en_len - he_len) * (1 - ratio)).
    2. Take the top N (default 5,000), skipping any IDs already
       rewritten in a previous run.
    3. Submit to the Batch API in chunks of <10,000 requests.
    4. As each batch completes, overwrite the entries in
       data/translations_he.json and append the IDs to
       .cache/rewrites_done.json so the next run resumes cleanly.
    5. Run `python build.py` afterwards to propagate the new HE
       descriptions into data/docs/*.json and the search index.

Usage:
    python rewrite_descriptions.py                 # top 5,000
    python rewrite_descriptions.py --top 1000      # smaller run
    python rewrite_descriptions.py --dry-run       # show plan + cost only
    python rewrite_descriptions.py --batch-id ...  # resume an in-flight batch
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

DOCS_DIR        = Path("data/docs")
TRANSLATIONS    = Path("data/translations_he.json")
REWRITES_DONE   = Path(".cache/rewrites_done.json")
BATCH_CHUNK     = 9_000
MODEL           = "claude-opus-4-7"
MAX_TOKENS      = 4096

SYSTEM_PROMPT = """אתה כותב תיאורים בעברית למסמכים מגניזת קהיר, על בסיס תיאור באנגלית מקטלוג Princeton Geniza Project.

הנחיות:
- שמור על היקף דומה לתיאור המקורי באנגלית. אל תקצר באופן משמעותי.
- אינך חייב לתרגם מילה במילה — נסח מחדש בעברית טבעית, זורמת וקריאה.
- שמור על כל המידע התוכני: תאריכים מדויקים, שמות אנשים ומקומות, פרטי האירוע, ציטוטים מהמקור, פרטים משפטיים/מסחריים/אישיים, והקשרים היסטוריים.
- דלג על מידע מידעני טכני שלא תורם לתוכן: מספרי שמורה (shelfmarks) ומיקום פיזי, שמות ספריות וקטלוגים, ראשי תיבות של מקטלגים (כגון "EMS", "MR", "AA"), והפניות ביבליוגרפיות פנימיות מפורטות (כגון "Goitein, Mediterranean Society, 3:113, 449"). אזכור כללי של חוקר ("לפי גויטיין", "לפי גיל") — מותר ורצוי כשהוא חיוני להקשר.
- שמות אנשים ומקומות: תעתיק עברי מקובל (אברהם, פוסטאט, קהיר, ירושלים, אלכסנדריה וכד').
- מונחים טכניים מהעולם הערבי-יהודי: השאר במקור או בתעתיק עברי מקובל (כתובה, גט, ת'מאם, גבלה וכד').
- כתוב אך ורק את התיאור בעברית — ללא הקדמה, ללא הערות, ללא כותרת, ללא מירכאות עוטפות."""


# ── Gap scoring (kept in sync with find_translation_gaps.py) ──────────────────
def gap_score(en_len, he_len):
    if not en_len:
        return 0.0
    ratio = he_len / en_len
    return (en_len - he_len) * (1 - min(ratio, 1.0))


def load_json(path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    tmp.replace(path)


def select_targets(top_n, min_en, already_done):
    """Return list of {id, desc} for the top-N by gap score, skipping done IDs."""
    candidates = []
    for path in DOCS_DIR.glob("*.json"):
        try:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        doc_id = doc.get("id")
        desc_en = (doc.get("description") or "").strip()
        desc_he = (doc.get("description_he") or "").strip()
        if not doc_id or not desc_en or len(desc_en) < min_en:
            continue
        if doc_id in already_done:
            continue
        candidates.append({
            "id": doc_id,
            "desc": desc_en,
            "score": gap_score(len(desc_en), len(desc_he)),
        })
    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:top_n]


# ── Cost estimate ──────────────────────────────────────────────────────────────
# Opus 4.x pricing (list): $15/MTok input, $75/MTok output. Batch API: 50% off.
PRICE_IN_BATCH  = 7.50  / 1_000_000
PRICE_OUT_BATCH = 37.50 / 1_000_000


def estimate_cost(targets):
    chars_in = sum(len(t["desc"]) + len(SYSTEM_PROMPT) for t in targets)
    # Assume HE output ~ same length as EN input (we ask for similar scope).
    chars_out = sum(len(t["desc"]) for t in targets)
    tokens_in  = chars_in  / 4
    tokens_out = chars_out / 4
    return tokens_in * PRICE_IN_BATCH + tokens_out * PRICE_OUT_BATCH


# ── Batch API ──────────────────────────────────────────────────────────────────
def submit_batch(client, targets):
    requests = [
        {
            "custom_id": t["id"],
            "params": {
                "model": MODEL,
                "max_tokens": MAX_TOKENS,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": t["desc"]}],
            },
        }
        for t in targets
    ]
    batch = client.messages.batches.create(requests=requests)
    return batch.id


def poll_until_done(client, batch_id, poll_interval=30):
    print(f"  Batch ID: {batch_id}")
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        c = batch.request_counts
        done  = c.succeeded + c.errored + c.canceled
        total = done + c.processing
        print(f"  {batch.processing_status} — {done}/{total} done "
              f"({c.errored} errors)", end="\r", flush=True)
        if batch.processing_status == "ended":
            print()
            return batch
        time.sleep(poll_interval)


def collect_results(client, batch_id, translations, done_set):
    new_count = 0
    errors = 0
    for result in client.messages.batches.results(batch_id):
        if result.result.type == "succeeded":
            text = result.result.message.content[0].text.strip()
            translations[result.custom_id] = text
            done_set.add(result.custom_id)
            new_count += 1
        else:
            errors += 1
    return new_count, errors


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Rewrite Hebrew descriptions with Opus 4.7 for biggest gaps")
    parser.add_argument("--top",      type=int, default=5000,
                        help="How many of the worst-gap docs to rewrite (default 5000)")
    parser.add_argument("--min-en",   type=int, default=200,
                        help="Skip docs with EN shorter than this (default 200)")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Show plan + cost estimate only; no API calls")
    parser.add_argument("--batch-id", type=str, default=None,
                        help="Resume an existing batch by ID")
    parser.add_argument("--poll",     type=int, default=30,
                        help="Poll interval in seconds (default 30)")
    args = parser.parse_args()

    translations = load_json(TRANSLATIONS, {})
    done_set = set(load_json(REWRITES_DONE, []))
    print(f"Existing translations cached: {len(translations):,}")
    print(f"Already rewritten with Opus:  {len(done_set):,}")

    # ── Resume mode ───────────────────────────────────────────────────────────
    if args.batch_id:
        try:
            import anthropic
        except ImportError:
            sys.exit("ERROR: pip install anthropic")
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            sys.exit("ERROR: Set ANTHROPIC_API_KEY")
        client = anthropic.Anthropic(api_key=api_key)
        print(f"Resuming batch {args.batch_id}…")
        poll_until_done(client, args.batch_id, args.poll)
        n, errs = collect_results(client, args.batch_id, translations, done_set)
        save_json(TRANSLATIONS, translations)
        save_json(REWRITES_DONE, sorted(done_set))
        print(f"Saved {n:,} rewrites ({errs} errors). Total rewritten: {len(done_set):,}")
        _next_steps()
        return

    # ── Plan ──────────────────────────────────────────────────────────────────
    print(f"\nSelecting top {args.top:,} by gap score (min EN ≥ {args.min_en} chars)…")
    targets = select_targets(args.top, args.min_en, done_set)
    if not targets:
        print("Nothing to do — all top-gap docs have already been rewritten.")
        return
    print(f"  → {len(targets):,} docs queued for rewrite")
    print(f"  EN length:  min={min(len(t['desc']) for t in targets):,}  "
          f"max={max(len(t['desc']) for t in targets):,}  "
          f"mean={sum(len(t['desc']) for t in targets)//len(targets):,}")
    cost = estimate_cost(targets)
    print(f"  Estimated cost (Opus 4.7 Batch API): ${cost:,.2f}")
    print(f"    (rough estimate: HE output assumed similar length to EN input)")

    if args.dry_run:
        print("\n[dry-run] no API calls made.")
        sample = targets[:5]
        print(f"\nSample of top {len(sample)}:")
        for t in sample:
            print(f"  id={t['id']:>6}  en_len={len(t['desc']):>5}  "
                  f"score={t['score']:>7.0f}")
        return

    # ── Real run ──────────────────────────────────────────────────────────────
    try:
        import anthropic
    except ImportError:
        sys.exit("ERROR: pip install anthropic")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ERROR: Set ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    for chunk_start in range(0, len(targets), BATCH_CHUNK):
        chunk = targets[chunk_start : chunk_start + BATCH_CHUNK]
        chunk_num = chunk_start // BATCH_CHUNK + 1
        total_chunks = (len(targets) - 1) // BATCH_CHUNK + 1
        print(f"\nChunk {chunk_num}/{total_chunks}: submitting {len(chunk):,} requests…")
        batch_id = submit_batch(client, chunk)
        poll_until_done(client, batch_id, args.poll)
        n, errs = collect_results(client, batch_id, translations, done_set)
        save_json(TRANSLATIONS, translations)
        save_json(REWRITES_DONE, sorted(done_set))
        print(f"  Saved {n:,} rewrites ({errs} errors). "
              f"Total rewritten: {len(done_set):,}")

    print(f"\nDone. {len(done_set):,} documents rewritten in total.")
    _next_steps()


def _next_steps():
    print()
    print("Next steps:")
    print("  python build.py          # propagate new HE into data/docs/*.json")
    print("  git add data/translations_he.json .cache/rewrites_done.json")
    print("  git commit -m 'Rewrite Hebrew descriptions with Opus 4.7'")
    print("  git push")


if __name__ == "__main__":
    main()
