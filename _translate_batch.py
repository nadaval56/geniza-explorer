#!/usr/bin/env python3
"""Helper: prints next untranslated batch for Claude to translate."""
import csv, json, sys
from pathlib import Path

TRANSLATIONS_FILE = Path("data/translations_he.json")
CSV_FILE = Path(".cache/documents.csv")
BATCH_SIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 80
OFFSET     = int(sys.argv[2]) if len(sys.argv) > 2 else 0

translations = {}
if TRANSLATIONS_FILE.exists():
    with open(TRANSLATIONS_FILE, encoding="utf-8") as f:
        translations = json.load(f)

docs = []
with open(CSV_FILE, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        pgpid = row.get("pgpid","").strip()
        desc  = row.get("description","").strip()
        if pgpid and desc and pgpid not in translations:
            docs.append((pgpid, desc))

remaining = len(docs)
batch = docs[OFFSET:OFFSET+BATCH_SIZE]

print(f"# מתורגם: {len(translations):,} | נשאר: {remaining:,} | batch: {len(batch)}")
print()
for pgpid, desc in batch:
    # Print as: ===ID===\nDescription
    print(f"==={pgpid}===")
    print(desc)
    print()
