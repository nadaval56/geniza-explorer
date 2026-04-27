#!/usr/bin/env python3
"""Insert four pre-translated Hebrew descriptions into data/translations_he.json."""
import json
from pathlib import Path

TRANSLATIONS_FILE = Path("data/translations_he.json")

new_entries = {
    "24687": "מכתב בעל תוכן משפטי, אפשר מאת שופט לרשות עליונה. השולח מדווח על מחלוקת בין שני גברים. אחד אומר \"אין לי בן ואין לי אח... בארצות אלה...\". מוזכרת צו ממשלתי (תַּוְקִיעַ כָּרִים). אחד הצדדים מכונה אל-ראיס, ואחר אל-שריף. מוצגת גם אישה הנראית תובעת את תשלום כתובתה. אך הראיס לא שילם לה עד שניתן הצו הממשלתי. דורש בדיקה נוספת.",
    "24690": "מסמך; פילוסופיה/אתיקה; הטקסט הראשי, בעברית ובערבית, אפשר שהוא דיון בשכר ועונש; גב המסמך מכיל גם חשבונות ערביים.",
    "24691": "ראשיתה של כתובת אברהם בן יוסף וחוסן. שמור חלק מרשימת הנדוניה.",
    "24692": "מכתב ביהודית-ערבית. על קלף. כתוב בכתב יד יפה, ברמה סגנונית מעט מוגבהת. תאריך: ככל הנראה המאה ה-11 או ה-12. השולח מדווח שהצליח למכור משהו בשם הנמען לר' נתן תמורת 9 ¾ דינרים לאחר מאמץ רב. פנה לאברהם בן דאוד בעניין הכרוך בשער חליפין. אבו אל-פרג' עשה משהו בשם הנמען בקשר לקשת יפה (טאק חסן). לגבי האבן הטובה, לא הגיעה לשולח \"בגלל מזלי האומלל\". הוא מבקש מהנמען לשלוח את שהבטיח. מוזכרות ברכות לר' יוסף (עם ברכת המתים) ולתלמידים/חכמים (אל-תלמידים).",
}

translations = {}
if TRANSLATIONS_FILE.exists():
    with open(TRANSLATIONS_FILE, encoding="utf-8") as f:
        translations = json.load(f)

before = len(translations)
translations.update(new_entries)
after = len(translations)

TRANSLATIONS_FILE.parent.mkdir(exist_ok=True)
with open(TRANSLATIONS_FILE, "w", encoding="utf-8") as f:
    json.dump(translations, f, ensure_ascii=False, separators=(",", ":"))

print(f"שמור: {after - before} חדשים → סה\"כ {after:,}")
