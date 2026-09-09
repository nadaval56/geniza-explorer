"""
Exploratory script: find plant and animal mentions in translations_he.json.
Outputs a frequency table with context examples to help spot false positives.
"""

import json
import re
from collections import defaultdict

TRANSLATIONS = "data/translations_he.json"
EXAMPLES_PER_TERM = 3

# ── Candidate list ─────────────────────────────────────────────────────────────
# Format: (display_name, category, [search_patterns])
# Patterns are Hebrew substrings (or regex with (?:) notation)
CANDIDATES = [
    # ── Animals ───────────────────────────────────────────────────────────────
    ("גמל",   "בעל חיים", [r"גמל\b", "גמלים", "גמלי"]),
    ("חמור",  "בעל חיים", ["חמור", "חמורים", "חמורי"]),
    ("סוס",   "בעל חיים", [r"סוס\b", "סוסים", "סוסי"]),
    ("פרד",   "בעל חיים", [r"פרד\b", "פרדים", "פרדי"]),
    ("שור",   "בעל חיים", [r"שור\b", "שוורים", r"שוורי\b"]),
    ("כבש",   "בעל חיים", [r"כבש\b", "כבשים", "כבשי"]),
    ("עז",    "בעל חיים", [r"(?<![א-ת])עז(?![א-ת\"])"]),
    ("כלב",   "בעל חיים", [r"כלב\b", "כלבים"]),
    ("חתול",  "בעל חיים", [r"חתול\b", "חתולים"]),
    ("דג",    "בעל חיים", [r"דג\b", "דגים", r"דגי\b"]),
    ("עוף",   "בעל חיים", [r"עוף\b", "עופות", r"עופי\b"]),
    ("תרנגול","בעל חיים", ["תרנגול", "תרנגולת"]),
    ("יונה",  "בעל חיים", [r"יונה\b", "יונים"]),
    ("פיל",   "בעל חיים", [r"פיל\b", "פילים"]),
    ("ארי",   "בעל חיים", [r"ארי\b", r"אריה\b", "אריות"]),
    ("קוף",   "בעל חיים", [r"קוף\b", "קופים"]),
    ("עכבר",  "בעל חיים", [r"עכבר\b", "עכברים"]),
    ("דבורה", "בעל חיים", [r"דבורה\b", "דבורים", "דבש"]),
    ("משי",   "בעל חיים", ["משי", "תולעת המשי"]),  # silkworm product
    ("אווז",  "בעל חיים", [r"אווז\b", "אוזים"]),

    # ── Plants / Crops ─────────────────────────────────────────────────────────
    ("חיטה",  "צמח", ["חיטה", "חיטים", "קמח"]),
    ("שעורה", "צמח", ["שעורה", "שעורים"]),
    ("אורז",  "צמח", [r"אורז\b"]),
    ("פשתן",  "צמח", ["פשתן"]),
    ("כותנה", "צמח", ["כותנה", "כותנת"]),
    ("תמר",   "צמח", [r"תמרים\b", r"תמרי\b", "עצי תמר"]),  # avoid name "תמר"
    ("תאנה",  "צמח", ["תאנה", "תאנים"]),
    ("ענב",   "צמח", ["ענבים", r"ענב\b", "גפן", "גפנים"]),
    ("זית",   "צמח", ["זית", "זיתים", "שמן זית"]),
    ("שמן",   "צמח", [r"שמן\b"]),  # generic oil — will have noise
    ("רימון", "צמח", [r"רימון\b", "רימונים"]),
    ("אתרוג", "צמח", [r"אתרוג\b", "אתרוגים"]),
    ("לימון", "צמח", [r"לימון\b", "לימונים"]),
    ("שקד",   "צמח", [r"שקד\b", "שקדים"]),
    ("אגוז",  "צמח", [r"אגוז\b", "אגוזים"]),

    # ── Spices / Trade goods ───────────────────────────────────────────────────
    ("פלפל",  "תבלין", ["פלפל"]),
    ("זעפרן", "תבלין", ["זעפרן"]),
    ("כרכום", "תבלין", ["כרכום"]),
    ("קינמון","תבלין", ["קינמון"]),
    ("זנגביל","תבלין", ["זנגביל", "ג'ינג'ר"]),
    ("הל",    "תבלין", [r"(?<![א-ת])הל(?![א-ת])"]),
    ("כמון",  "תבלין", [r"כמון\b"]),
    ("כוסברה","תבלין", ["כוסברה"]),
    ("חינה",  "תבלין", ["חינה"]),
    ("שום",   "תבלין", [r"שום\b"]),
    ("בצל",   "תבלין", [r"בצל\b", "בצלים"]),
    ("סוכר",  "תבלין", ["סוכר", "קנה סוכר"]),
    ("דבש",   "תבלין", [r"דבש\b"]),
]


def matches(text: str, patterns: list[str]) -> bool:
    for p in patterns:
        if re.search(p, text):
            return True
    return False


def main():
    with open(TRANSLATIONS, encoding="utf-8") as f:
        trans: dict[str, str] = json.load(f)

    # doc_id → text
    rows: list[tuple[str, str]] = list(trans.items())

    results = []
    for name, category, patterns in CANDIDATES:
        hits = [(doc_id, txt) for doc_id, txt in rows if matches(txt, patterns)]
        count = len(hits)
        examples = []
        for doc_id, txt in hits[:EXAMPLES_PER_TERM]:
            # find matching snippet (up to 80 chars around match)
            for p in patterns:
                m = re.search(p, txt)
                if m:
                    start = max(0, m.start() - 30)
                    end = min(len(txt), m.end() + 50)
                    snippet = ("…" if start > 0 else "") + txt[start:end] + ("…" if end < len(txt) else "")
                    examples.append(f"[{doc_id}] {snippet}")
                    break
        results.append((count, name, category, examples))

    results.sort(reverse=True)

    print(f"{'#':>5}  {'שם':15} {'קטגוריה':10}  דוגמאות")
    print("─" * 100)
    for count, name, category, examples in results:
        if count == 0:
            continue
        print(f"{count:>5}  {name:15} {category:10}")
        for ex in examples:
            print(f"        {ex}")
        print()

    print(f"\nסה\"כ מועמדים עם hits: {sum(1 for c,*_ in results if c > 0)}")


if __name__ == "__main__":
    main()
