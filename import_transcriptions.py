#!/usr/bin/env python3
"""
ייבוא התעתיקים של Princeton Geniza Project אל data/transcriptions/.

    git clone --depth 1 https://github.com/princetongenizalab/pgp-text.git /tmp/pgp-text
    python3 import_transcriptions.py --source /tmp/pgp-text

מה יש שם: המאגר princetongenizalab/pgp-text הוא גיבוי אוטומטי של תוכן התעתיקים
מ-geniza.princeton.edu. הקבצים יושבים תחת <אלף><PGPID>/<PGPID>/, וכל אחד נקרא
PGPID<id>_s<n>_<עורך>_<transcription|translation>.html. הרישיון זהה לזה של
המטא־נתונים שהאתר כבר מתבסס עליהם: CC BY-NC 4.0, כלומר ייחוס ולא מסחרי.

למה הפלט מחויב לגיט ולא נמשך בבנייה: build.py מסומן continue-on-error בדיוק
משום שהורדה מפרינסטון עלולה להיכשל, וחבל שתקלת רשת תמחק את התעתיקים מן האתר
החי. 35MB אינם מכבידים על מאגר שכבר נושא 191MB של data/docs.

הפלט: data/transcriptions/<pgpid>.json, ובו רשימת גרסאות. כל גרסה נושאת את
שם העורך ואת הציטוט הביבליוגרפי שהקובץ פותח בו — זה הייחוס שהרישיון דורש —
ואת גוף התעתיק כ-HTML מסונן.

הסינון: הקבצים מגיעים ממקור מהימן, אבל הם עדיין HTML שנשתל בעמוד. המסנן כאן
עובר על העץ ומשאיר רק את מה שהתעתיק צריך — פסקאות, שורות, הדגשות, וסימון
הצד (recto/verso) שבמאפיין data-canvas. תגית או מאפיין שאינם ברשימה נמחקים,
ובכללם script, style, on* וכל href שאינו http.
"""
import argparse
import json
import pathlib
import re
import sys
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).parent
OUT_DIR = ROOT / "data" / "transcriptions"
DOCS_DIR = ROOT / "data" / "docs"

FILENAME = re.compile(
    r"^PGPID(?P<id>\d+)_s(?P<seq>\d+)_(?P<editor>.+)_(?P<kind>transcription|translation)\.html$")

ALLOWED_TAGS = {
    "section", "div", "p", "span", "br", "b", "i", "em", "strong", "sup", "sub",
    "ul", "ol", "li", "h2", "h3", "blockquote",
}
ALLOWED_ATTRS = {"dir", "lang", "data-canvas", "class"}

KIND_HE = {"transcription": "תעתיק", "translation": "תרגום לאנגלית"}


class Sanitiser(HTMLParser):
    """Keep the transcription's structure, drop everything else."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.citation = []
        self.depth = 0          # 0 = before <section>, >0 = inside the body
        self.skip = 0           # inside a tag whose content is dropped
        self._open = []

    # ── helpers ───────────────────────────────────────────────────────────────
    def _attrs(self, attrs):
        keep = []
        for name, value in attrs:
            if name not in ALLOWED_ATTRS or value is None:
                continue
            keep.append(f' {name}="{value.replace(chr(34), "&quot;")}"')
        return "".join(keep)

    # ── parser hooks ──────────────────────────────────────────────────────────
    def handle_starttag(self, tag, attrs):
        # h1 מכיל את הכותרת "Transcription of Letter: T-S 10J15.8", שהיא כפולה
        # של מה שכבר בראש עמוד המסמך, והייתה נדבקת לתחילת הציטוט.
        if tag in ("script", "style", "head", "title", "h1"):
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "section":
            self.depth += 1
        if self.depth == 0:
            return                      # the citation paragraph, taken as text
        if tag in ALLOWED_TAGS:
            self.out.append(f"<{tag}{self._attrs(attrs)}>")
            if tag != "br":
                self._open.append(tag)

    def handle_endtag(self, tag):
        # h1 מכיל את הכותרת "Transcription of Letter: T-S 10J15.8", שהיא כפולה
        # של מה שכבר בראש עמוד המסמך, והייתה נדבקת לתחילת הציטוט.
        if tag in ("script", "style", "head", "title", "h1"):
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or self.depth == 0:
            return
        if tag in ALLOWED_TAGS and tag != "br":
            if self._open and self._open[-1] == tag:
                self._open.pop()
                self.out.append(f"</{tag}>")
        if tag == "section":
            self.depth = max(0, self.depth - 1)

    def handle_data(self, data):
        if self.skip:
            return
        text = data.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if self.depth == 0:
            self.citation.append(data)
        else:
            self.out.append(text)

    # ── result ────────────────────────────────────────────────────────────────
    def result(self):
        while self._open:
            self.out.append(f"</{self._open.pop()}>")
        body = "".join(self.out).strip()
        # הקבצים מגיעים בהזחה עמוקה, ורצף רווחים אינו נראה בדפדפן ממילא. איחוד
        # לרווח אחד ולא מחיקה: מחיקה בין תגיות תדביק מילים בתוך span סמוכים.
        body = re.sub(r"\s{2,}", " ", body)
        citation = re.sub(r"\s+", " ", "".join(self.citation)).strip()
        return citation, body


def convert(path):
    parser = Sanitiser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    parser.close()
    return parser.result()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True,
                    help="clone of princetongenizalab/pgp-text")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    source = pathlib.Path(args.source)
    if not source.is_dir():
        sys.exit(f"  ✗  {source} אינו קיים. שכפל את princetongenizalab/pgp-text.")

    live = {p.stem for p in DOCS_DIR.glob("*.json")} if DOCS_DIR.exists() else set()
    if not live:
        sys.exit("  ✗  data/docs ריק — הרץ build.py קודם.")

    by_doc, skipped, empty = {}, 0, 0
    files = sorted(source.glob("*/*/PGPID*.html"))
    for path in files:
        m = FILENAME.match(path.name)
        if not m:
            continue
        doc_id = str(int(m.group("id")))
        if doc_id not in live:
            skipped += 1        # מסמך שפרינסטון מחקה או מיזגה, ואינו באוסף
            continue
        citation, body = convert(path)
        if not body:
            empty += 1
            continue
        by_doc.setdefault(doc_id, []).append({
            "kind": m.group("kind"),
            "label": KIND_HE[m.group("kind")],
            "editor": m.group("editor"),
            "citation": citation,
            "html": body,
            "seq": int(m.group("seq")),
        })
        if args.limit and len(by_doc) >= args.limit:
            break

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale in OUT_DIR.glob("*.json"):
        if stale.stem not in by_doc:
            stale.unlink()

    total = 0
    for doc_id, texts in by_doc.items():
        # תעתיק לפני תרגום, ובתוך כל סוג לפי מספר הגרסה.
        texts.sort(key=lambda t: (t["kind"] != "transcription", t["seq"]))
        for t in texts:
            t.pop("seq")
        (OUT_DIR / f"{doc_id}.json").write_text(
            json.dumps({"id": doc_id, "texts": texts}, ensure_ascii=False,
                       separators=(",", ":")),
            encoding="utf-8")
        total += len(texts)

    size = sum(p.stat().st_size for p in OUT_DIR.glob("*.json"))
    print(f"  ✓  data/transcriptions/  ({len(by_doc):,} מסמכים, {total:,} גרסאות, "
          f"{size / 2**20:.0f} MB)")
    if skipped:
        print(f"  ·  {skipped:,} קבצים למסמכים שאינם באוסף — דילוג")
    if empty:
        print(f"  ·  {empty:,} קבצים ריקים אחרי הסינון — דילוג")


if __name__ == "__main__":
    main()
