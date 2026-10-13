"""
expand_spices.py — Find additional spice/ingredient candidates inside
documents already tagged with ≥1 spice tag, using a specificity score:

    specificity = (freq_in_spice_docs / spice_docs_count)
                / (freq_in_all_docs   / all_docs_count)

A score >> 1 means the term is far more common in spice docs than the
general corpus, flagging genuine ingredient / recipe vocabulary.

Usage:
    python expand_spices.py            # top candidates, min_score=3
    python expand_spices.py --min 5    # stricter threshold
    python expand_spices.py --raw      # raw freq table (no specificity)
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

TAGS_FILE    = Path("data/tags_he.json")
TRANSLATIONS = Path("data/translations_he.json")

MIN_SCORE  = float(next((sys.argv[i+1] for i, a in enumerate(sys.argv)
                          if a == '--min'), 3))
RAW_MODE   = '--raw' in sys.argv
MIN_SPICE_FREQ = 2   # must appear in ≥2 spice docs to be a candidate

SPICE_TAGS = {
    'פלפל','זעפרן','קינמון','זנגביל','כמון','כרכום','כוסברה','דבש','סוכר',
}

KNOWN_TERMS = SPICE_TAGS | {
    'גמל','חמור','כבש','דג','עוף','תרנגול','כלב','חתול','עכבר',
    'פשתן','כותנה','חיטה','שעורה','אורז','זית','לימון','שקד','אגוז',
    'רימון','תמר','תאנה','ענב','גפן','שמן','מסחר','רפואה',
}

# broad stop-words: function words + generic doc-description boilerplate
STOP = {
    # function words
    'של','על','את','עם','אל','כי','לא','הוא','היא','הם','הן','זה','זו',
    'אני','אתה','אנחנו','אבל','גם','כן','כך','כבר','עוד','רק','מאוד',
    'בין','אחד','שני','כל','יש','אין','או','אם','אחרי','לפני','עד',
    'לו','לה','לנו','להם','בו','בה','בהם','מהם','מהן','מה','ממנו',
    'ב','ל','מ','כ','ו','ה','אשר','שם','כן','זאת',
    # doc-description boilerplate
    'מכתב','מסמך','בית','דין','כתב','ערבית','עברית','יהודית','כתובה',
    'חשבון','חשבונות','רשימה','נזכר','מוזכר','מוזכרים','עוסק','מתאר',
    'קטע','שבר','נראה','ייתכן','גב','פנים','שורה','שורות','ורסו','רקטו',
    'מאה','שנת','לספירה','בערך','תיאור','בגב','ראשון','ראשונה',
    'ערבי','ביהודית','בכתב','מזכיר','המכתב','המאה','ככל','הנראה',
    'ככל הנראה','בכתב ערבי','ביהודית ערבית','בערבית יהודית',
    'אבו','אבן','בן','יוסף','כגון','סחורות','לפי','לפני','אחרי',
    'ראשית','שניים','שלוש','ארבע','חמש','שלש','שלשה','ספירה',
    'לערך','תיארוך','ראשיתה','מחצית','שנייה','שניה','גויטיין',
    'נכתב','נכתבה','בצד','הצד','הימני','השמאלי','שורות','עמוד',
    'תחתון','עליון','ימין','שמאל','ידו','ידה','חתום','חתומה',
}


def tokens(text):
    words = re.findall(r"[א-ת'\"]+", text)
    for w in words:
        if len(w) >= 2 and w not in STOP:
            yield w
    for i in range(len(words) - 1):
        bg = words[i] + ' ' + words[i+1]
        if words[i] not in STOP and words[i+1] not in STOP:
            yield bg


def count_docs(doc_ids, trans):
    freq = Counter()
    for doc_id in doc_ids:
        text = trans.get(doc_id, '')
        if not text:
            continue
        seen = set()
        for t in tokens(text):
            if t not in seen:
                freq[t] += 1
                seen.add(t)
    return freq


def snippets(doc_ids, trans, candidates, n=3):
    examples = {t: [] for t in candidates}
    for doc_id in doc_ids:
        text = trans.get(doc_id, '')
        if not text:
            continue
        for term in candidates:
            if len(examples[term]) >= n:
                continue
            m = re.search(re.escape(term), text)
            if m:
                s = max(0, m.start() - 30)
                e = min(len(text), m.end() + 60)
                snip = ('…' if s > 0 else '') + text[s:e] + ('…' if e < len(text) else '')
                examples[term].append(f'[{doc_id}] {snip}')
    return examples


def main():
    tags  = json.loads(TAGS_FILE.read_text(encoding='utf-8'))
    trans = json.loads(TRANSLATIONS.read_text(encoding='utf-8'))
    all_ids   = set(trans.keys())
    spice_ids = {did for did, dtags in tags.items() if SPICE_TAGS & set(dtags)}

    N_all   = len(all_ids)
    N_spice = len(spice_ids)
    print(f"מסמכי-תבלינים: {N_spice} | סה\"כ מסמכים: {N_all}\n")

    spice_freq = count_docs(spice_ids, trans)
    all_freq   = count_docs(all_ids,   trans)

    results = []
    for term, sf in spice_freq.items():
        if sf < MIN_SPICE_FREQ:
            continue
        if term in KNOWN_TERMS or term in STOP:
            continue
        af = all_freq.get(term, sf)
        score = (sf / N_spice) / (af / N_all)
        results.append((score, sf, term))

    if RAW_MODE:
        results.sort(key=lambda x: -x[1])
    else:
        results = [(s, f, t) for s, f, t in results if s >= MIN_SCORE]
        results.sort(reverse=True)

    top_terms = [t for _, _, t in results[:60]]
    exs = snippets(spice_ids, trans, top_terms)

    print(f"{'ציון':>7}  {'#':>4}  מועמד")
    print('─' * 90)
    for score, sf, term in results[:60]:
        print(f"{score:>7.1f}  {sf:>4}  {term}")
        for ex in exs.get(term, [])[:2]:
            print(f"              {ex}")
        print()

    print(f"\nסה\"כ מועמדים (score≥{MIN_SCORE}): {len(results)}")


if __name__ == '__main__':
    main()
