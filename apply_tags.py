#!/usr/bin/env python3
"""
Assign Hebrew tags to every document and write data/tags_he.json.

Sources:
  1. doc type_he field  → TYPE_MAP tags
  2. doc lang_he field  → LANG_MAP tags
  3. Hebrew translation text → TEXT_TAGS substring search
"""
import json
import glob
from pathlib import Path
from collections import Counter

from tags_config import TEXT_TAGS, TYPE_MAP, LANG_MAP

DOCS_DIR     = Path("data/docs")
TRANS_FILE   = Path("data/translations_he.json")
OUTPUT_FILE  = Path("data/tags_he.json")

# Load translations
with open(TRANS_FILE, encoding="utf-8") as f:
    translations = json.load(f)

all_tags: dict[str, list[str]] = {}
tag_counter = Counter()

for doc_path in sorted(DOCS_DIR.glob("*.json")):
    doc = json.load(open(doc_path, encoding="utf-8"))
    pgpid = doc["id"]
    tags: list[str] = []

    # 1. Type tag from metadata
    type_he = (doc.get("type_he") or "").strip()
    if type_he in TYPE_MAP and TYPE_MAP[type_he]:
        tags.append(TYPE_MAP[type_he])

    # 2. Language tag from metadata (primary language, first segment)
    lang_he = (doc.get("lang_he") or "").split("؛")[0].strip()
    for prefix, tag in LANG_MAP.items():
        if lang_he.startswith(prefix):
            tags.append(tag)
            break

    # 3. Text-search tags from Hebrew translation
    text = translations.get(pgpid, "")
    if text:
        for tag, patterns in TEXT_TAGS.items():
            if any(p in text for p in patterns):
                tags.append(tag)

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            deduped.append(t)

    if deduped:
        all_tags[pgpid] = deduped
        for t in deduped:
            tag_counter[t] += 1

# Write output
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(all_tags, f, ensure_ascii=False, indent=2)

print(f"Tagged {len(all_tags):,} documents → {OUTPUT_FILE}")
print(f"\nTag frequencies:")
for tag, count in tag_counter.most_common():
    print(f"  {count:6,}  {tag}")
