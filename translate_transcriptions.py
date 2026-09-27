#!/usr/bin/env python3
"""
translate_transcriptions.py — Hebrew translations of the PGP transcriptions.

A Judaeo-Arabic letter in data/transcriptions/ is Arabic in Hebrew letters: a
Hebrew reader can sound it out and still not understand it. This script gives
it a Hebrew translation, line for line, for every document that carries both a
transcription and a scholar's English translation.

It translates from the original, not from the English. Geniza letters are full
of Hebrew and Aramaic to begin with — verses, blessings, legal formulae — and a
round trip through English turns "שריר ובריר" into "valid and firm" and back
into something nobody wrote. The English goes in alongside as the expert's
ruling on every number, term and identification, which is what the first
draft of the prompt got wrong: left as a mere aid, the model ignored it and
invented "civet butter" where the scholar had written "civet".

Two passes per document, both Opus 4.7 through `claude --print`:
  1. translate  — source + English → numbered Hebrew lines
  2. review     — source + English + draft → list of fixes + corrected text
On a 10-document sample the first pass fixed six of eight errors once the
English was made binding, and the review caught two that pass 1 cannot see,
among them a date of "33 days of Marheshvan".

Output: data/transcriptions_he/<pgpid>.json, one per document. Resumable: a
document with an output file is skipped. Documents whose transcription is
already Hebrew are skipped too — there is nothing to translate.

    python3 translate_transcriptions.py --dry-run
    python3 translate_transcriptions.py --limit 300 --workers 12
"""

import argparse
import html
import json
import re
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SRC_DIR  = Path("data/transcriptions")
OUT_DIR  = Path("data/transcriptions_he")
ERRORS   = Path(".cache/transcriptions_he_errors.log")
MODEL    = "claude-opus-4-7"
TIMEOUT  = 400
# מחוץ לריפו, כמו ב-rewrite_descriptions.py: מתוכו CLAUDE.md נטען לכל קריאה.
NEUTRAL_CWD = tempfile.gettempdir()
SKIP_LANGS = {"he", "en"}

TRANSLATE_PROMPT = """אתה מתרגם מסמכים מגניזת קהיר לעברית בת זמננו, עבור קוראים משכילים שאינם חוקרים.

תקבל שני דברים: (1) תעתיק המקור ביהודית-ערבית (ערבית באותיות עבריות, לעתים משולבת בעברית ובארמית), שורה אחר שורה; (2) תרגום אנגלי של חוקר.

הנחיות:
- תרגם מן המקור, אבל התרגום האנגלי הוא הכרעה של מומחה ויש לו סמכות: כל מספר, סכום, תאריך, מונח, מוצר, תואר או זיהוי שהחוקר קבע — אמץ אותו, גם כשהמקור נראה לך אחרת. אם אינך בטוח בקריאת שורה, תרגם לפי משמעות השורה המקבילה באנגלית.
- חריג אחד לסמכות האנגלית: קטעים שכתובים במקור בעברית או בארמית (פסוקים, ברכות, נוסחאות פתיחה וסיום כמו "בר עבדו מודה חסדו", לשון שטרות, מונחים הלכתיים, קיצורים כמו "יצ"ו" או "נ"ע") — העתק אותם כלשונם, אות באות, גם כשהחוקר תרגם אותם לאנגלית. לעולם אל תתרגם עברית חזרה לעברית.
- לפני שאתה כותב, עבור על כל שורה ובדוק שהתרגום שלך אומר את מה שהשורה המקבילה באנגלית אומרת. שורה שהחוקר לא תרגם — תרגם מן המקור בזהירות.
- מספרים באותיות (כגון שע"ב, קנט) — חשב את ערכם בדייקנות וכתוב אותם בספרות (372, 159). תאריך עברי (שנה, יום בחודש) כתוב כפי שהוא נהוג בעברית, באותיות.
- שמור על מספור השורות של המקור: שורה אחת בתרגום לכל שורה במקור, בפורמט "1. ...". כותרת צד או אזור (Recto, Verso, Margin וכד') כתוב בשורה נפרדת בסוגריים מרובעים, למשל "[צד א]", "[צד ב]", "[שוליים]".
- חסר או קטוע במקור — סמן [...]. השלמה של החוקר בסוגריים מרובעים — שמור בסוגריים מרובעים.
- עברית טבעית וקריאה, לא מילולית. מונחים ערביים טכניים (ח'גה, מעאמלה, דינר) — השאר בתעתיק, עם הסבר קצר בסוגריים בהופעה הראשונה בלבד.
- כתוב אך ורק את התרגום, בלי הקדמה ובלי הערות."""

REVIEW_PROMPT = """אתה עורך ובודק תרגומים של מסמכי גניזת קהיר מיהודית-ערבית לעברית.

תקבל: (1) תעתיק המקור, (2) תרגום אנגלי של חוקר, (3) טיוטת תרגום עברי.

עבור על הטיוטה שורה אחר שורה מול המקור ומול האנגלית, וחפש רק טעויות ממשיות:
- מספר, סכום, תאריך או כמות שאינם תואמים את המקור או את האנגלית (שים לב לספירת אותיות: שע"ב = 372), או שאינם אפשריים (יום שלושים ושלושה בחודש)
- מונח, מוצר, תואר או שם שתורגם שלא כפי שהחוקר הכריע, כשהכרעת החוקר סבירה
- שורה משובשת, קריאה שגויה של המקור, או כיוון משמעות הפוך
- עברית או ארמית שבמקור שתורגמו במקום להישאר כלשונן
- שורה שחסרה או שנוספה ביחס למקור
אל תשנה ניסוח שהוא עניין של סגנון.

פלט: קודם שורה "תיקונים:" ואחריה רשימה קצרה — "שורה N: <מה היה> → <מה צריך> (<למה>)", או "אין". אחר כך שורה שמכילה רק "===" ואחריה התרגום העברי המלא המתוקן, באותו פורמט בדיוק, בלי שום הערה נוספת."""


def text_lines(fragment):
    """Structure-only HTML (sanitised at import) → '## heading' / plain lines."""
    out = []
    for m in re.finditer(r"<h3>(.*?)</h3>|<li>(.*?)</li>", fragment, re.S):
        if m.group(1) is not None:
            out.append("## " + html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip())
        else:
            out.append(html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip())
    return out


def dedupe(lines):
    """Some imported editions repeat the whole text twice (PGPID 5408: twelve
    lines, then a "Recto" heading and the same twelve again). Sent as is, the
    model rightly translates it once and the line-count check rejects it."""
    body = [l for l in lines if not l.startswith("## ")]
    half = len(body) // 2
    if half and len(body) % 2 == 0 and body[:half] == body[half:]:
        seen, out = 0, []
        for l in lines:
            if not l.startswith("## "):
                seen += 1
                if seen > half:
                    break
            out.append(l)
        return out
    return lines


def numbered(lines):
    n, out = 0, []
    for line in lines:
        if line.startswith("## "):
            out.append(line)
            continue
        n += 1
        out.append(f"{n}. {line}")
    return "\n".join(out)


def source_lang(fragment):
    m = re.search(r'lang="([^"]+)"', fragment)
    return m.group(1).lower() if m else ""


def pick_pair(texts):
    """One transcription and the English translation of the same edition.

    453 documents carry more than one edition. A transcription by one editor
    paired with another editor's translation disagrees line by line, so the
    editor is matched first and position only as a fallback.
    """
    trs = [t for t in texts if t["kind"] == "transcription"]
    tls = [t for t in texts if t["kind"] == "translation"]
    if not trs or not tls:
        return None, None
    for tr in trs:
        for tl in tls:
            if tr.get("editor") and tr.get("editor") == tl.get("editor"):
                return tr, tl
    return trs[0], tls[0]


def select(ids=None):
    targets = []
    for path in sorted(SRC_DIR.glob("*.json"), key=lambda p: int(p.stem) if p.stem.isdigit() else 0):
        doc_id = path.stem
        if ids and doc_id not in ids:
            continue
        if (OUT_DIR / f"{doc_id}.json").exists():
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        tr, tl = pick_pair(data.get("texts", []))
        if not tr:
            continue
        lang = source_lang(tr["html"])
        if lang in SKIP_LANGS:
            continue
        src, en = numbered(dedupe(text_lines(tr["html"]))), numbered(text_lines(tl["html"]))
        if not src.strip():
            continue
        targets.append({"id": doc_id, "src": src, "en": en, "lang": lang,
                        "editor": tr.get("editor", ""), "citation": tr.get("citation", "")})
    return targets


def call(system, stdin):
    proc = subprocess.run(
        ["claude", "--print", "--model", MODEL, "--system-prompt", system,
         "--tools", "", "--disable-slash-commands", "--no-session-persistence",
         "--setting-sources", "project,local", "--output-format", "json"],
        input=stdin, capture_output=True, text=True, timeout=TIMEOUT, cwd=NEUTRAL_CWD)
    if proc.returncode != 0:
        raise RuntimeError(f"claude exit {proc.returncode}: {proc.stderr.strip()[:300]}")
    j = json.loads(proc.stdout)
    if j.get("is_error"):
        raise RuntimeError(f"claude error: {str(j.get('result'))[:300]}")
    return j["result"].strip(), j.get("total_cost_usd") or 0.0


def call_retry(system, stdin, tries=3):
    for attempt in range(tries):
        try:
            return call(system, stdin)
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            if attempt == tries - 1:
                raise
            time.sleep(4 * 2 ** attempt)


LINE_RE = re.compile(r"^(\d+)\.\s")


def line_count(text):
    return sum(1 for l in text.splitlines() if LINE_RE.match(l.strip()))


CHUNK = 35   # numbered lines per call; longer drafts merge or drop lines


def chunks(src):
    """Split a numbered source into runs of about CHUNK lines.

    On an 80-line letter a single call came back 74, 78 or 70 lines long: the
    model merges short lines and drops damaged ones, and the line-count check
    rightly refused every one. Each chunk carries the side headings that fall
    inside it, and a chunk ends early at a heading rather than just after one.
    """
    out, cur, count = [], [], 0
    for line in src.splitlines():
        if line.startswith("## ") and count >= CHUNK * 0.6:
            out.append("\n".join(cur)); cur, count = [], 0
        cur.append(line)
        if LINE_RE.match(line):
            count += 1
            if count >= CHUNK:
                out.append("\n".join(cur)); cur, count = [], 0
    if cur and any(LINE_RE.match(l) for l in cur):
        out.append("\n".join(cur))
    elif cur and out:
        out[-1] += "\n" + "\n".join(cur)
    return out


MERGED = "—"   # a manuscript line the model folded into the one before it


def align(text, want):
    """Re-number a draft against the source's line numbers, or return None.

    Short lines — a lone figure in an account, a single word at a line end —
    are what the model folds into the line before; the content is there, the
    numbering drifts by one. Missing numbers are filled with MERGED so line N
    of the translation still faces line N of the transcription. A draft that
    lost more than a tenth of its lines, or invented numbers, is refused.
    """
    expected = set(want)
    seen, out, last = {}, [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^(\d+)\.\s*(.*)$", line)
        if not m:
            out.append(("h", line))
            continue
        n = int(m.group(1))
        if n not in expected:
            return None
        if n in seen:
            out[seen[n]] = ("n", n, out[seen[n]][2] + " " + m.group(2))
            continue
        seen[n] = len(out)
        out.append(("n", n, m.group(2)))
    missing = expected - set(seen)
    if len(missing) > max(1, len(want) // 10):
        return None
    result, idx = [], 0
    for item in out:
        if item[0] == "h":
            result.append(item[1])
            continue
        while idx < len(want) and want[idx] != item[1]:
            if want[idx] in missing:
                result.append(f"{want[idx]}. {MERGED}")
            idx += 1
        result.append(f"{item[1]}. {item[2]}")
        idx += 1
    for n in want[idx:]:
        if n in missing:
            result.append(f"{n}. {MERGED}")
    return "\n".join(result)


def translate_part(t, part, whole):
    pair = f"=== תעתיק המקור ===\n{t['src']}\n\n=== תרגום אנגלי ===\n{t['en']}"
    if not whole:
        nums = [int(LINE_RE.match(l).group(1)) for l in part.splitlines() if LINE_RE.match(l)]
        pair += (f"\n\n=== הקטע לתרגום ===\nתרגם אך ורק את שורות {nums[0]}–{nums[-1]} "
                 f"(ואת כותרות הצד שבתוכן), במספור המקורי. שאר המקור לעיון בלבד.\n{part}")
    draft, c1 = call_retry(TRANSLATE_PROMPT, pair)
    review, c2 = call_retry(REVIEW_PROMPT, f"{pair}\n\n=== טיוטת תרגום עברי ===\n{draft}")
    fixes, sep, final = review.partition("\n===")
    final = final.strip()
    fixes = fixes.replace("תיקונים:", "", 1).strip()
    # A review that lost its separator, or dropped lines, is not trusted over
    # the draft: the draft already went through the binding-English rules.
    want = [int(LINE_RE.match(l).group(1)) for l in part.splitlines() if LINE_RE.match(l)]
    aligned = align(final, want) if sep else None
    if aligned is None:
        aligned, fixes = align(draft, want), ""
    if aligned is None:
        raise RuntimeError(f"line count {line_count(final)} / {line_count(draft)} != source {len(want)}")
    final = aligned
    return final, ("" if fixes in ("", "אין") else fixes), c1 + c2


def translate(t):
    parts = chunks(t["src"])
    whole = len(parts) == 1
    texts, fixes, cost = [], [], 0.0
    for part in parts:
        text, fix, c = translate_part(t, part, whole)
        texts.append(text); cost += c
        if fix:
            fixes.append(fix)
    return {
        "id": t["id"],
        "text": "\n".join(texts),
        "fixes": "\n".join(fixes),
        "source_editor": t["editor"],
        "source_citation": t["citation"],
        "source_lang": t["lang"],
        "model": MODEL,
    }, cost


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--ids", default="", help="comma-separated PGPIDs")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ids = set(args.ids.split(",")) if args.ids else None
    targets = select(ids)
    print(f"{len(targets):,} documents to translate")
    if args.limit:
        targets = targets[:args.limit]
    if args.dry_run or not targets:
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ERRORS.parent.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    done = errs = 0
    cost = 0.0
    start = time.time()

    def work(t):
        try:
            return t, translate(t)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"{t['id']}\t{e}") from e

    with ThreadPoolExecutor(args.workers) as ex:
        futs = [ex.submit(work, t) for t in targets]
        for fut in as_completed(futs):
            try:
                t, (rec, c) = fut.result()
            except Exception as e:  # noqa: BLE001 — log and keep going
                with lock:
                    errs += 1
                    with open(ERRORS, "a", encoding="utf-8") as f:
                        f.write(f"{e}\n")
                continue
            with open(OUT_DIR / f"{rec['id']}.json", "w", encoding="utf-8") as f:
                json.dump(rec, f, ensure_ascii=False, indent=1)
                f.write("\n")
            with lock:
                done += 1
                cost += c
                if done % 10 == 0:
                    rate = done / (time.time() - start)
                    print(f"  {done}/{len(targets)}  err={errs}  ${cost:.2f}  {rate*60:.0f}/min", flush=True)
    print(f"Done: {done}  Errors: {errs}  Cost: ${cost:.2f}")


if __name__ == "__main__":
    sys.exit(main())
