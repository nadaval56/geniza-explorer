#!/usr/bin/env python3
"""Merges a JSON batch file into the main translations file."""
import json, sys
from pathlib import Path

TRANSLATIONS_FILE = Path("data/translations_he.json")
BATCH_FILE        = Path("_batch_result.json")

if not BATCH_FILE.exists():
    print("ERROR: _batch_result.json not found"); sys.exit(1)

with open(BATCH_FILE, encoding="utf-8") as f:
    new_entries = json.load(f)

translations = {}
if TRANSLATIONS_FILE.exists():
    with open(TRANSLATIONS_FILE, encoding="utf-8") as f:
        translations = json.load(f)

before = len(translations)
translations.update(new_entries)
after  = len(translations)

TRANSLATIONS_FILE.parent.mkdir(exist_ok=True)
with open(TRANSLATIONS_FILE, "w", encoding="utf-8") as f:
    json.dump(translations, f, ensure_ascii=False, separators=(",",":"))

print(f"שמור: {after - before} חדשים → סה״כ {after:,}")
BATCH_FILE.unlink()
