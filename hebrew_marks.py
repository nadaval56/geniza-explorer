#!/usr/bin/env python3
"""
Geniza Explorer — Arabic vowel signs on Hebrew letters, turned into Hebrew points.

Judaeo-Arabic is Arabic written in Hebrew letters, and scholars who vocalise it
often borrow the Arabic signs: "אבן עמّה", "תסלימאً". 344 Hebrew descriptions,
14 machine translations and 77 PGP transcriptions carry such a cluster — a
Hebrew letter with an Arabic shadda (U+0651), fatha or tanwin on it.

No font on the site holds both. The browser then looks for one font that
covers the whole cluster, finds none, and draws empty boxes: on a phone,
"(וְאִ◻◻◻ אלמסלמין תע◻◻בּו מעה)" in d/3125.html. A desktop with many system
fonts hides the problem.

So on a Hebrew letter each Arabic sign becomes the Hebrew point that does the
same job — shadda is gemination, which is exactly what a dagesh marks — and
tanwin, which has no Hebrew counterpart, is dropped. Arabic words in Arabic
letters are left alone: the whole cluster is Arabic and renders in an Arabic
font. The source files are not rewritten; this runs at display time, in
build.py, in prerender.py (clean and render_he_text), and in the same form in
assets/doc-text.js for the PGP transcriptions. A change here needs both.
"""

import re

DAGESH = "ּ"

# Arabic sign → Hebrew point ("" = drop)
MAP = {
    "ّ": DAGESH,     # shadda → dagesh (gemination)
    "َ": "ַ",   # fatha  → patah
    "ِ": "ִ",   # kasra  → hiriq
    "ُ": "ֻ",   # damma  → qubuts
    "ْ": "ְ",   # sukun  → sheva
    "ً": "",         # fathatan (tanwin)
    "ٌ": "",         # dammatan
    "ٍ": "",         # kasratan
}

# A Hebrew letter and every point or Arabic sign stacked on it.
CLUSTER = re.compile("[א-ת][֑-ׇً-ْ]+")
ARABIC_SIGN = re.compile("[ً-ْ]")


def _fix(m):
    cluster = m.group(0)
    if not ARABIC_SIGN.search(cluster):
        return cluster
    base, marks = cluster[0], cluster[1:]
    out = []
    for ch in marks:
        ch = MAP.get(ch, ch)
        if ch and ch not in out:     # no second dagesh when the letter had one
            out.append(ch)
    return base + "".join(out)


def hebraize(text):
    """Replace Arabic vowel signs that sit on Hebrew letters."""
    if not text or not ARABIC_SIGN.search(text):
        return text
    return CLUSTER.sub(_fix, text)


if __name__ == "__main__":
    for s in ["וְאִנַّ אלמסלמין תעצّבּו מעה", "רַגַ'עַ גַ'דַّדַ עליהִ אלאסלאם",
              "תסלימאً", "פَلا إكراه في الدين", "בּّ"]:
        print(s, "→", hebraize(s))
