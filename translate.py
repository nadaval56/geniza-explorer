#!/usr/bin/env python3
"""
Geniza Explorer — Hebrew Translation Script
Translates document descriptions to Hebrew using Claude Haiku Batch API.

Usage:
    python translate.py                         # uses ANTHROPIC_API_KEY env var
    python translate.py --limit 100             # translate only 100 (for testing)
    python translate.py --batch-id msgbatch_... # resume existing batch

Translations are cached in data/translations_he.json and committed to the repo.
Future runs skip already-translated documents — you only pay for new ones.

After running:
    git add data/translations_he.json
    git commit -m "Add Hebrew translations"
    git push ...
"""

import csv
import json
import os
import sys
import time
from pathlib import Path

TRANSLATIONS_FILE = Path("data/translations_he.json")
CSV_FILE = Path(".cache/documents.csv")
BATCH_CHUNK = 9_000   # Batch API limit is 10,000; stay slightly under
MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = (
    "אתה מתרגם תיאורים אקדמיים של מסמכים מגניזת קהיר. "
    "תרגם לעברית תקינה וטבעית. "
    "שמות אנשים ומקומות — שמור בתעתיק עברי מקובל (אברהם, פוסטאט, קהיר וכד'). "
    "תרגם בלבד, ללא הסברים או הערות."
)


def load_translations():
    if TRANSLATIONS_FILE.exists():
        with open(TRANSLATIONS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_translations(translations):
    TRANSLATIONS_FILE.parent.mkdir(exist_ok=True)
    with open(TRANSLATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(translations, f, ensure_ascii=False, separators=(",", ":"))


def load_docs_needing_translation(translations):
    if not CSV_FILE.exists():
        print("ERROR: .cache/documents.csv not found. Run: python build.py first.")
        sys.exit(1)
    docs = []
    with open(CSV_FILE, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            pgpid = row.get("pgpid", "").strip()
            desc  = row.get("description", "").strip()
            if pgpid and desc and pgpid not in translations:
                docs.append({"id": pgpid, "desc": desc})
    return docs


def submit_batch(client, docs):
    requests = [
        {
            "custom_id": doc["id"],
            "params": {
                "model": MODEL,
                "max_tokens": 600,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": doc["desc"]}],
            },
        }
        for doc in docs
    ]
    batch = client.messages.batches.create(requests=requests)
    return batch.id


def poll_until_done(client, batch_id, poll_interval=30):
    print(f"  Batch ID: {batch_id}")
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        counts = batch.request_counts
        done   = counts.succeeded + counts.errored + counts.canceled
        total  = done + counts.processing
        print(f"  {batch.processing_status} — {done}/{total} done "
              f"({counts.errored} errors)", end="\r", flush=True)
        if batch.processing_status == "ended":
            print()
            return batch
        time.sleep(poll_interval)


def collect_results(client, batch_id, translations):
    new_count = 0
    for result in client.messages.batches.results(batch_id):
        if result.result.type == "succeeded":
            text = result.result.message.content[0].text.strip()
            translations[result.custom_id] = text
            new_count += 1
    return new_count


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Translate Geniza descriptions to Hebrew")
    parser.add_argument("--limit",    type=int,  default=None,  help="Translate only N docs (testing)")
    parser.add_argument("--batch-id", type=str,  default=None,  help="Resume an existing batch")
    parser.add_argument("--poll",     type=int,  default=30,    help="Poll interval in seconds")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: Set ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)

    try:
        import anthropic
    except ImportError:
        print("ERROR: Install the Anthropic SDK:  pip install anthropic")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    translations = load_translations()
    print(f"Cached translations: {len(translations):,}")

    # ── Resume mode ───────────────────────────────────────────────────────────
    if args.batch_id:
        print(f"Resuming batch {args.batch_id}…")
        poll_until_done(client, args.batch_id, args.poll)
        n = collect_results(client, args.batch_id, translations)
        save_translations(translations)
        print(f"Saved {n:,} new translations → {len(translations):,} total")
        _print_next_steps()
        return

    # ── Fresh run ─────────────────────────────────────────────────────────────
    docs = load_docs_needing_translation(translations)
    if args.limit:
        docs = docs[:args.limit]

    if not docs:
        print("Nothing to translate — all documents already have Hebrew descriptions!")
        return

    print(f"Docs to translate: {len(docs):,}")

    # Cost estimate
    chars = sum(len(d["desc"]) for d in docs)
    tokens_in  = (chars + len(docs) * 80) / 4
    tokens_out = chars * 0.9 / 4
    cost = (tokens_in * 0.40 + tokens_out * 2.00) / 1_000_000
    print(f"Estimated cost:    ${cost:.2f} (Haiku batch API)")
    print()

    # Process in chunks
    for chunk_start in range(0, len(docs), BATCH_CHUNK):
        chunk = docs[chunk_start : chunk_start + BATCH_CHUNK]
        chunk_num = chunk_start // BATCH_CHUNK + 1
        total_chunks = (len(docs) - 1) // BATCH_CHUNK + 1
        print(f"Submitting chunk {chunk_num}/{total_chunks} ({len(chunk):,} docs)…")

        batch_id = submit_batch(client, chunk)
        poll_until_done(client, batch_id, args.poll)
        n = collect_results(client, batch_id, translations)
        save_translations(translations)
        print(f"  Saved {n:,} new translations → {len(translations):,} total\n")

    print(f"Done! {len(translations):,} total Hebrew translations.")
    _print_next_steps()


def _print_next_steps():
    print()
    print("Next steps:")
    print("  git add data/translations_he.json")
    print("  git commit -m 'Add Hebrew translations'")
    print("  git push ... (to trigger rebuild)")


if __name__ == "__main__":
    main()
