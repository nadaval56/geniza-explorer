#!/usr/bin/env python3
"""
בדיקת שפיות לדפי הנושא.

נכתב אחרי באג אמיתי: אחת עשרה תגיות — ובהן משי (862 מסמכים), זהב (329)
וכסף (246) — לא קיבלו דף נושא במשך זמן מה, ואיש לא ידע. הסיבה הייתה
ש-data/docs/*.json לא היה מסונכרן עם data/tags_he.json, ורשימת התגיות
"החסרות" נגזרה מהמקור המיושן. כשל שקט: האתר נבנה, נפרס והכול נראה תקין.

הבדיקה הזאת הופכת אותו לכשל רועש.

    python3 scripts/check_tag_pages.py

יוצאת בקוד 1 אם:
  · תגית עם MIN_DOCS מסמכים ומעלה אין לה ערך ב-tag_pages.py
  · data/docs לא מסונכרן עם data/tags_he.json
  · ערך ב-TAG_PAGES חסר שדה, נושא סלאג לא תקין או סלאג כפול
  · פסקת מבוא חורגת מ-80–200 מילים
  · ערך מפנה לקבוצה שאינה קיימת ב-GROUPS

תגית עם פחות מ-MIN_DOCS מסמכים מדווחת כהערה ולא ככשל: דף רכזת לשני
מסמכים הוא בדיוק הדף הדל שהמפרט מזהיר מפניו.
"""
import json
import pathlib
import re
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tag_pages  # noqa: E402

MIN_DOCS = 3
INTRO_MIN, INTRO_MAX = 80, 200
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FIELDS = {"slug", "h1", "group", "intro"}

errors, notes = [], []


def load_tag_counts():
    """ספירה משני המקורות, ואימות שהם מסכימים."""
    tags_he_path = ROOT / "data" / "tags_he.json"
    if not tags_he_path.exists():
        errors.append("data/tags_he.json חסר — הרץ apply_tags.py")
        return Counter()

    canonical = json.loads(tags_he_path.read_text(encoding="utf-8"))
    counts = Counter(t.strip() for tl in canonical.values() for t in tl if t.strip())

    docs_dir = ROOT / "data" / "docs"
    if not docs_dir.exists():
        notes.append("data/docs/ חסר — דילוג על בדיקת הסנכרון")
        return counts

    drift = 0
    for path in docs_dir.glob("*.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if (doc.get("tags_he") or []) != canonical.get(str(doc["id"]), []):
            drift += 1
    if drift:
        errors.append(
            f"{drift:,} קבצים ב-data/docs/ אינם מסונכרנים עם data/tags_he.json. "
            "זו בדיוק הסחיפה שהסתירה את משי, זהב וכסף. "
            "הרץ build.py, או סנכרן את שדה tags_he מ-tags_he.json."
        )
    return counts


def check_entries():
    seen_slugs = {}
    for tag, page in tag_pages.TAG_PAGES.items():
        missing = FIELDS - set(page)
        extra = set(page) - FIELDS
        if missing:
            errors.append(f"'{tag}': חסרים שדות {sorted(missing)}")
        if extra:
            errors.append(f"'{tag}': שדות לא מוכרים {sorted(extra)}")
        if missing:
            continue

        slug = page["slug"]
        if not SLUG_RE.match(slug):
            errors.append(f"'{tag}': סלאג '{slug}' אינו [a-z0-9] מופרד במקפים")
        if slug in seen_slugs:
            errors.append(f"סלאג כפול '{slug}' — '{tag}' ו-'{seen_slugs[slug]}'")
        seen_slugs[slug] = tag

        if page["group"] not in tag_pages.GROUPS:
            errors.append(f"'{tag}': קבוצה '{page['group']}' אינה ב-GROUPS")

        words = len(page["intro"].split())
        if not INTRO_MIN <= words <= INTRO_MAX:
            errors.append(
                f"'{tag}': מבוא באורך {words} מילים, מחוץ לטווח "
                f"{INTRO_MIN}–{INTRO_MAX}"
            )


def check_coverage(counts):
    missing = sorted(
        ((t, n) for t, n in counts.items()
         if n >= MIN_DOCS and t not in tag_pages.TAG_PAGES),
        key=lambda pair: -pair[1],
    )
    for tag, n in missing:
        errors.append(f"'{tag}' נושא {n:,} מסמכים ואין לו ערך ב-tag_pages.py")

    thin = sorted(t for t, n in counts.items()
                  if n < MIN_DOCS and t in tag_pages.TAG_PAGES)
    for tag in thin:
        notes.append(f"'{tag}' נושא פחות מ-{MIN_DOCS} מסמכים — לא ייבנה לו דף")

    unused = sorted(t for t in tag_pages.TAG_PAGES if t not in counts)
    for tag in unused:
        notes.append(f"'{tag}' יש לו ערך אבל אף מסמך לא נושא אותו כרגע")


def main():
    counts = load_tag_counts()
    check_entries()
    if counts:
        check_coverage(counts)

    covered = sum(1 for t in counts if t in tag_pages.TAG_PAGES and counts[t] >= MIN_DOCS)
    print(f"  {len(tag_pages.TAG_PAGES)} ערכים ב-tag_pages.py")
    print(f"  {len(counts)} תגיות בנתונים, {covered} מהן עם דף")

    for note in notes:
        print(f"  · {note}")

    if errors:
        print()
        for err in errors:
            print(f"::error::{err}")
        print(f"\n  ✗ {len(errors)} בעיות")
        return 1

    print("  ✓ כל תגית עם 3 מסמכים ומעלה מכוסה, וכל הערכים תקינים")
    return 0


if __name__ == "__main__":
    sys.exit(main())
