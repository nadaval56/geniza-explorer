#!/usr/bin/env python3
"""
Replace historical 'Palestine/פלסטין' terminology with 'Land of Israel/ארץ ישראל'
in the Hebrew translations cache.

Skipped PGPIDs (modern context, require manual review):
  34851 - Forward newspaper, refers to a Palestinian Arab individual
  34937 - 'הלירה הפלסטינית' = official name of British Mandate currency
"""
import json
from collections import defaultdict

INPUT_FILE = "data/translations_he.json"

# --- Replacements (ordered: most specific / longest match first) ---
REPLACEMENTS = [
    # Institutional phrases
    ("ראש הישיבה הפלסטינית",    "ראש ישיבת ארץ ישראל"),
    ("הישיבה הפלסטינאית",       "ישיבת ארץ ישראל"),
    ("הישיבה הפלסטינית",        "ישיבת ארץ ישראל"),
    ("ישיבת פלסטין",             "ישיבת ארץ ישראל"),
    ("גאוני פלסטינה",            "גאוני ישיבת ארץ ישראל"),
    ("גאוני פלסטין",             "גאוני ישיבת ארץ ישראל"),
    ("גאון פלסטינה",             "גאון ישיבת ארץ ישראל"),
    ("גאון פלסטין",              "גאון ישיבת ארץ ישראל"),
    ("בית הכנסת הפלסטינאי",     "בית הכנסת הארץ ישראלי"),
    ("בית הכנסת הפלסטיני",      "בית הכנסת הארץ ישראלי"),
    ("הכנסת הפלסטינאי",         "הכנסת הארץ ישראלי"),   # catch trailing variants
    ("הכנסת הפלסטיני",          "הכנסת הארץ ישראלי"),

    # Adjectives – definite, feminine
    ("הפלסטינאית",   "הארץ ישראלית"),
    ("הפלסטינית",    "הארץ ישראלית"),
    # Adjectives – definite, masculine
    ("הפלסטינאי",    "הארץ ישראלי"),
    ("הפלסטיני",     "הארץ ישראלי"),

    # Plural forms
    ("הפלסטינאים",   "ארץ ישראלים"),
    ("הפלסטינים",    "ארץ ישראלים"),
    ("פלסטינאים",    "ארץ ישראלים"),
    ("פלסטיניים",    "ארץ ישראלים"),
    ("פלסטינים",     "ארץ ישראלים"),

    # Feminine plural
    ("פלסטיניות",    "ארץ ישראליות"),

    # Adjectives – indefinite, feminine
    ("פלסטינאית",    "ארץ ישראלית"),
    ("פלסטינית",     "ארץ ישראלית"),
    # Adjectives – indefinite, masculine
    ("פלסטינאי",     "ארץ ישראלי"),
    ("פלסטיני",      "ארץ ישראלי"),

    # Nouns with prepositions (longer prefixes first to avoid double-match)
    ("שבפלסטינה",   "שבארץ ישראל"),
    ("שבפלסטין",    "שבארץ ישראל"),
    ("ובפלסטינה",   "ובארץ ישראל"),
    ("ובפלסטין",    "ובארץ ישראל"),
    ("בפלסטינה",    "בארץ ישראל"),
    ("בפלסטין",     "בארץ ישראל"),
    ("מפלסטינה",    "מארץ ישראל"),
    ("מפלסטין",     "מארץ ישראל"),
    ("לפלסטינה",    "לארץ ישראל"),
    ("לפלסטין",     "לארץ ישראל"),
    ("ופלסטין",     "וארץ ישראל"),

    # Compound geographic term (Roman province Syria Palaestina)
    ("סוריה-פלסטינה",   "סוריה-ארץ ישראל"),
    ("סוריה-פלסטין",    "סוריה-ארץ ישראל"),
    ("סורי-פלסטיני",    "סורי-ארץ ישראלי"),

    # Bare nouns (catch-all, must come last)
    ("פלסטינה",     "ארץ ישראל"),
    ("פלסטין",      "ארץ ישראל"),
]

# PGPIDs whose text should NOT be touched (modern / ambiguous contexts)
SKIP_PGPIDS = {
    "34851",   # Forward newspaper article – refers to a Palestinian Arab individual
    "34937",   # 'הלירה הפלסטינית' = official name of British Mandate currency
}

# ---------------------------------------------------------------------------

with open(INPUT_FILE, encoding="utf-8") as f:
    translations = json.load(f)

changes_by_pgpid = {}   # pgpid -> list of (old, new, count)
total_replacements = 0

for pgpid, text in translations.items():
    if pgpid in SKIP_PGPIDS:
        continue

    new_text = text
    entry_changes = []
    for old, new in REPLACEMENTS:
        if old in new_text:
            count = new_text.count(old)
            new_text = new_text.replace(old, new)
            entry_changes.append((old, new, count))

    if entry_changes:
        translations[pgpid] = new_text
        changes_by_pgpid[pgpid] = entry_changes
        total_replacements += sum(c for _, _, c in entry_changes)

# Save updated translations
with open(INPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(translations, f, ensure_ascii=False, indent=2)

# --- Report ---
print(f"Replacements made: {total_replacements} across {len(changes_by_pgpid)} documents\n")

# Tally by replacement pair
tally = defaultdict(int)
for chgs in changes_by_pgpid.values():
    for old, new, count in chgs:
        tally[(old, new)] += count

print("Breakdown by replacement:")
for (old, new), count in sorted(tally.items(), key=lambda x: -x[1]):
    print(f"  {count:4d}x  '{old}' → '{new}'")

print(f"\nSkipped PGPIDs (manual review):")
for pgpid in SKIP_PGPIDS:
    if pgpid in translations:
        print(f"  PGPID {pgpid}: {translations[pgpid][:140]}")
