#!/usr/bin/env python3
"""
Extract word/bigram frequency statistics from Hebrew translations.
Outputs candidates for tags (>= MIN_COUNT occurrences).
"""
import json
import re
from collections import Counter

MIN_COUNT = 20

# Hebrew stop words to filter out
STOP_WORDS = {
    # Prepositions / conjunctions / articles
    "של", "את", "אל", "עם", "על", "אל", "כי", "אם", "או", "גם", "אך",
    "רק", "כן", "לא", "כל", "יש", "אין", "זה", "זו", "זאת", "הוא", "היא",
    "הם", "הן", "אנו", "אנחנו", "הי", "כך", "כן",
    # Preposition prefixes that survive tokenization
    "בו", "בה", "בם", "לו", "לה", "לם", "מו", "מה", "שם",
    # Common verbs / connectors
    "נכתב", "כתוב", "כתב", "נכתבה", "נשמר", "נשמרת", "שכתב", "שכתבה",
    "שנכתב", "מכיל", "מכילה", "כולל", "כוללת", "עוסק", "עוסקת",
    "מוזכר", "מוזכרת", "מוזכרים", "מזכיר", "מזכירה", "מזכירים",
    "מתייחס", "מתייחסת", "מתאר", "מתארת",
    "נראה", "נראית", "ניתן", "יכול", "יכולה", "צריך",
    "קיים", "קיימת", "קיימים", "שמור", "שמורה", "שמורים",
    "ידוע", "ידועה", "ידועים", "נוסף", "נוספת", "נוספים",
    "כנראה", "אולי", "ייתכן", "כנראה",
    "מסוים", "מסוימת", "מסוימים", "מסוימות",
    "נוגע", "נוגעת", "נוגעים", "קשור", "קשורה", "קשורים",
    "דורש", "דורשת", "בחינה", "נוספת",
    "כולם", "כולן", "רובם", "חלקם",
    "ראשון", "ראשונה", "שני", "שנייה", "שלישי", "אחרון", "אחרונה",
    "גדול", "גדולה", "גדולים", "קטן", "קטנה", "קטנים",
    "עליו", "עליה", "עליהם", "אליו", "אליה", "אליהם",
    "ממנו", "ממנה", "מהם", "אצלו", "אצלה",
    "לפני", "אחרי", "בין", "אצל", "תחת", "מעל", "מתחת",
    "יותר", "פחות", "מאוד", "מאד", "כמו", "לפי",
    "שהוא", "שהיא", "שהם", "שהן",
    "בשם", "לשם", "משם",
    "דף", "דפים", "עמוד", "עמודים", "שורה", "שורות",
    "חלק", "חלקים", "סעיף", "סעיפים",
    "אחד", "אחת", "שניים", "שתיים", "שלושה", "שלוש",
    "אותו", "אותה", "אותם", "אותן",
    "רבים", "רבות", "מעט", "כמה",
    # Fragments of document descriptions
    "שבר", "שברים", "קטן", "קטנה", "קטנים", "זעיר", "זעירים",
    "חלקי", "חלקית",
    "ראוי", "ראויה", "נוסף", "נוספת",
    "ברור", "ברורה", "ברורים", "לא", "אינו", "אינה",
    "ייתכן", "לדוגמה", "למשל",
}

with open("data/translations_he.json", encoding="utf-8") as f:
    translations = json.load(f)

def tokenize(text):
    """Split on whitespace/punctuation, strip leading ה/ו/ב/ל/מ/כ/ש prefixes."""
    raw = re.findall(r'[א-תװ-״"\']+', text)
    tokens = []
    for w in raw:
        # strip trailing punctuation artifacts
        w = w.strip("'\"")
        if len(w) >= 2:
            tokens.append(w)
    return tokens

unigrams = Counter()
bigrams  = Counter()

for text in translations.values():
    tokens = tokenize(text)
    for t in tokens:
        unigrams[t] += 1
    for a, b in zip(tokens, tokens[1:]):
        bigrams[(a, b)] += 1

# Filter
filtered_uni = {w: c for w, c in unigrams.items()
                if c >= MIN_COUNT and w not in STOP_WORDS and len(w) >= 3}
filtered_bi  = {(a, b): c for (a, b), c in bigrams.items()
                if c >= MIN_COUNT
                and a not in STOP_WORDS and b not in STOP_WORDS
                and len(a) >= 2 and len(b) >= 2}

print(f"=== UNIGRAMS (>= {MIN_COUNT}) ===")
for w, c in sorted(filtered_uni.items(), key=lambda x: -x[1]):
    print(f"  {c:5d}  {w}")

print(f"\n=== BIGRAMS (>= {MIN_COUNT}) ===")
for (a, b), c in sorted(filtered_bi.items(), key=lambda x: -x[1]):
    print(f"  {c:5d}  {a} {b}")
