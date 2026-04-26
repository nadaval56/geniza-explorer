#!/usr/bin/env python3
"""
Geniza Explorer — Build Script
Generates a static Hebrew website from Princeton Geniza Project metadata.

Usage:
    python build.py                # Full build (downloads CSV if not cached)
    python build.py --no-download  # Use cached CSV only
    python build.py --limit 500    # Build only first N documents

Output:
    index.html              — Main search/browse page
    fragment.html           — Single fragment template (JS-driven)
    data/search.json        — Compact search index (all docs)
    data/docs/{id}.json     — Full detail per document
    assets/                 — CSS + JS (source files, not generated)
"""

import csv
import json
import os
import sys
import re
import urllib.request
from pathlib import Path
from html import escape

# ── Configuration ─────────────────────────────────────────────────────────────
CSV_URL = (
    "https://raw.githubusercontent.com/princetongenizalab/"
    "pgp-metadata/main/data/documents.csv"
)
CACHE_FILE = Path(".cache/documents.csv")
DATA_DIR = Path("data")
DOCS_DIR = DATA_DIR / "docs"

# ── Hebrew translations ────────────────────────────────────────────────────────
TYPE_MAP = {
    "Legal document":                       "מסמך משפטי",
    "Letter":                               "מכתב",
    "Literary text":                        "טקסט ספרותי",
    "Paraliterary text":                    "טקסט פרא-ספרותי",
    "Religious text":                       "טקסט דתי",
    "List or table":                        "רשימה או טבלה",
    "State document":                       "מסמך ממלכתי",
    "Credit instrument or private receipt": "שטר אשראי או קבלה",
    "Legal query or responsum":             "שאלה משפטית",
    "Inscription":                          "כתובת",
    "Unknown type":                         "סוג לא ידוע",
    "Documentary":                          "מסמך",
}

LANG_MAP = {
    "Judaeo-Arabic": "יהודית-ערבית",
    "Hebrew": "עברית",
    "Arabic": "ערבית",
    "Aramaic": "ארמית",
    "Judeo-Persian": "פרסית יהודית",
    "Greek": "יוונית",
    "Latin": "לטינית",
    "Coptic": "קופטית",
    "Persian": "פרסית",
    "Syriac": "סורית",
    "Unknown": "לא ידוע",
}

PLACE_MAP = {
    "Alexandria":    "אלכסנדריה",
    "Jerusalem":     "ירושלים",
    "Fustat":        "פוסטאט",
    "Aden":          "עדן",
    "Damascus":      "דמשק",
    "Cairo":         "קהיר",
    "Tyre":          "צור",
    "Acre":          "עכו",
    "Ascalon":       "אשקלון",
    "Jaffa":         "יפו",
    "Hebron":        "חברון",
    "Tiberias":      "טבריה",
    "Ramle":         "רמלה",
    "Ramla":         "רמלה",
    "Qayrawān":      "קירואן",
    "Baghdad":       "בגדד",
    "Palermo":       "פלרמו",
    "Sicily":        "סיציליה",
    "Egypt":         "מצרים",
    "Palestine":     "ארץ ישראל",
    "Yemen":         "תימן",
    "India":         "הודו",
    "Tunisia":       "תוניסיה",
    "Tripoli":       "טריפולי",
    "Bilbays":       "בלבייס",
    "Tinnis":        "תניס",
    "al-Mahdiyya":   "אל-מהדיה",
    "Tlemcen":       "תלמסאן",
    "Sijilmasa":     "סיג'ילמאסה",
    "Qūṣ":           "קוס",
    "Sahrajt":       "סהרג'ת",
    "Qalyub":        "קליוב",
    "Sunbat":        "סנבאט",
    "Minyat Zifta":  "מנית זפתה",
    "Byzantium":     "ביזנטיון",
}

LIBRARY_MAP = {
    "CUL":      "ספריית קיימברידג'",
    "BL":       "הספרייה הבריטית",
    "AIU":      "כיא פריז",
    "JTS":      "בית המדרש לרבנים",
    "Bodl.":    "בודליאן אוקספורד",
    "NLR":      "הספרייה הלאומית רוסיה",
    "BnF":      "הספרייה הלאומית צרפת",
    "Mosseri":  "אוסף מוסרי",
    "ENA":      "אוסף אדלר",
    "Geneva":   "ז'נבה",
    "Halper":   "אוסף הלפר",
    "Firkovich":"אוסף פירקוביץ'",
}


# ── CSV helpers ────────────────────────────────────────────────────────────────
def split_field(value):
    """Split a semicolon/pipe/space-semicolon separated field."""
    if not value:
        return []
    for sep in ["; ", ";", " | ", "|"]:
        if sep in value:
            return [v.strip() for v in value.split(sep) if v.strip()]
    return [value.strip()] if value.strip() else []


def first_value(value):
    parts = split_field(value)
    return parts[0] if parts else (value.strip() if value else "")


def translate_type(raw):
    primary = first_value(raw)
    return TYPE_MAP.get(primary, primary) if primary else "לא מסווג"


def translate_langs(raw):
    if not raw:
        return ""
    return "؛ ".join(LANG_MAP.get(l.strip(), l.strip()) for l in split_field(raw))


def translate_library(raw):
    if not raw:
        return ""
    parts = split_field(raw)
    translated = [LIBRARY_MAP.get(p.strip(), p.strip()) for p in parts]
    return " · ".join(translated)


def best_date(row):
    for key in ("doc_date_standard", "inferred_date_display", "doc_date_original"):
        v = row.get(key, "").strip()
        if v:
            return v
    return ""


def century_from_date(date_str):
    """Extract century number (e.g. 11) from a date string like '1025-08/1026-09'."""
    if not date_str:
        return None
    import re
    m = re.search(r'\b(9\d\d|1[0-4]\d\d)\b', date_str)
    if m:
        year = int(m.group(1))
        return (year // 100) + 1  # century CE
    return None


def place_he(name):
    """Return Hebrew place name if known, else hyphen-prefixed for readability."""
    return PLACE_MAP.get(name, f"-{name}")


def generate_hebrew_desc(doc):
    """Build a short Hebrew description sentence from structured metadata."""
    type_he = doc.get("type_he", "") or ""
    lang    = (doc.get("lang_he", "") or "").split("؛")[0].strip()
    origin  = doc.get("origin", "") or ""
    dest    = doc.get("destination", "") or ""
    lib     = (doc.get("library", "") or "").split(" · ")[0].strip()
    date    = doc.get("date", "") or ""

    parts = []
    if type_he and type_he not in ("לא מסווג", "סוג לא ידוע"):
        parts.append(type_he)
    if lang and lang != "לא ידוע":
        parts.append(f"ב{lang}")
    c = century_from_date(date)
    if c:
        parts.append(f"מהמאה ה-{c}")
    if origin and dest:
        parts.append(f"מ{place_he(origin)} ל{place_he(dest)}")
    elif origin:
        parts.append(f"מ{place_he(origin)}")
    elif dest:
        parts.append(f"ל{place_he(dest)}")

    if not parts:
        return ""
    sentence = " ".join(parts)
    if lib:
        sentence += f". מוחזק ב{lib}"
    return sentence + "."


def is_truthy(v):
    return str(v).strip().lower() in ("true", "1", "yes", "t")


def parse_doc(row):
    pgpid = row.get("pgpid", "").strip()
    if not pgpid:
        return None

    iiif_raw = row.get("iiif_urls", "").strip()
    frag_raw = row.get("fragment_urls", "").strip()

    iiif_list = split_field(iiif_raw)
    frag_list = split_field(frag_raw)

    # Princeton project URL
    princeton_url = row.get("url", "").strip()
    if not princeton_url:
        princeton_url = f"https://geniza.princeton.edu/en/documents/{pgpid}/"

    doc = {
        "id": pgpid,
        "shelfmark": row.get("shelfmark", "").strip(),
        "multifragment": row.get("multifragment", "").strip(),
        "type_en": first_value(row.get("type", "")),
        "type_he": translate_type(row.get("type", "")),
        "lang_en": row.get("languages_primary", "").strip(),
        "lang_he": translate_langs(row.get("languages_primary", "")),
        "lang2_en": row.get("languages_secondary", "").strip(),
        "lang2_he": translate_langs(row.get("languages_secondary", "")),
        "lang_note": row.get("language_note", "").strip(),
        "origin": row.get("origin", "").strip(),
        "destination": row.get("destination", "").strip(),
        "region": row.get("region", "").strip(),
        "date": best_date(row),
        "date_original": row.get("doc_date_original", "").strip(),
        "date_standard": row.get("doc_date_standard", "").strip(),
        "date_inferred": row.get("inferred_date_display", "").strip(),
        "date_rationale": row.get("inferred_date_rationale", "").strip(),
        "library": translate_library(row.get("library", "")),
        "library_raw": row.get("library", "").strip(),
        "collection": row.get("collection", "").strip(),
        "description": row.get("description", "").strip(),
        "tags": split_field(row.get("tags", "")),
        "has_transcription": is_truthy(row.get("has_transcription", "")),
        "has_translation": is_truthy(row.get("has_translation", "")),
        "iiif_urls": iiif_list,
        "fragment_urls": frag_list,
        "princeton_url": princeton_url,
        "mentioned": row.get("mentioned", "").strip(),
    }
    doc["description_he"] = generate_hebrew_desc(doc)
    return doc


# ── Download ───────────────────────────────────────────────────────────────────
def download_csv(force=False):
    CACHE_FILE.parent.mkdir(exist_ok=True)
    if CACHE_FILE.exists() and not force:
        print(f"  ↩  Using cached CSV ({CACHE_FILE.stat().st_size // 1024} KB)")
        return CACHE_FILE
    print(f"  ⬇  Downloading CSV…")
    urllib.request.urlretrieve(CSV_URL, CACHE_FILE)
    print(f"  ✓  Saved to {CACHE_FILE} ({CACHE_FILE.stat().st_size // 1024} KB)")
    return CACHE_FILE


def load_docs(csv_file, limit=None):
    docs = []
    with open(csv_file, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc = parse_doc(row)
            if doc:
                docs.append(doc)
    # Prioritise docs with IIIF images, then all others
    docs.sort(key=lambda d: (0 if d["iiif_urls"] else 1, d["id"].zfill(10)))
    if limit:
        docs = docs[:limit]
    return docs


# ── JSON output ────────────────────────────────────────────────────────────────
def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def build_search_index(docs):
    """Compact per-doc record for the search index."""
    index = []
    for doc in docs:
        entry = {"id": doc["id"]}
        if doc["shelfmark"]:        entry["s"]   = doc["shelfmark"]
        if doc["type_he"]:          entry["th"]  = doc["type_he"]
        if doc["lang_he"]:          entry["lh"]  = doc["lang_he"]
        if doc["origin"]:           entry["or"]  = doc["origin"]
        if doc["date"]:             entry["dt"]  = doc["date"]
        if doc["library"]:          entry["lib"] = doc["library"]
        desc = doc["description"][:160] if doc["description"] else ""
        if desc:                    entry["d"]   = desc
        if doc["description_he"]:   entry["dh"]  = doc["description_he"]
        if doc["iiif_urls"]:        entry["img"] = 1
        if doc["has_transcription"]:entry["tr"]  = 1
        if doc["has_translation"]:  entry["tl"]  = 1
        c = century_from_date(doc["date"])
        if c:                       entry["c"]   = c
        index.append(entry)
    return index


# ── HTML pages ────────────────────────────────────────────────────────────────
INDEX_HTML = """\
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="גניזת קהיר — חלון אל החיים היהודיים בימי הביניים. {total_docs:,} מסמכים מגניזת בן עזרא.">
  <title>גניזת קהיר</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Frank+Ruhl+Libre:wght@300;400;500;700;900&family=Heebo:wght@300;400;500;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>

  <header class="site-header">
    <div class="header-inner">
      <div class="header-ornament" aria-hidden="true">✦</div>
      <h1 class="site-title">גניזת קהיר</h1>
      <p class="site-subtitle">חלון אל החיים היהודיים בימי הביניים</p>
      <p class="site-intro">
        גניזת בן עזרא בקהיר שמרה במשך מאות שנים על {total_docs:,} מסמכים —
        מכתבים, חוזים, שירה, רפואה ותפילה — שנכתבו בין המאה ה-10 למאה ה-13.
        הם מגלים את חייהם של אנשים רגילים בעולם הים-תיכוני.
      </p>
    </div>
  </header>

  <section class="browse-section" aria-label="עיון מהיר">
    <div class="browse-inner">

      <div class="browse-group">
        <h2 class="browse-label">עיון לפי תקופה</h2>
        <div class="browse-chips" id="era-chips">
          <button class="chip" data-era="10">המאה ה-10</button>
          <button class="chip" data-era="11">המאה ה-11</button>
          <button class="chip" data-era="12">המאה ה-12</button>
          <button class="chip" data-era="13">המאה ה-13</button>
          <button class="chip" data-era="14">המאה ה-14+</button>
        </div>
      </div>

      <div class="browse-group">
        <h2 class="browse-label">עיון לפי סוג</h2>
        <div class="browse-chips" id="type-chips">
          <button class="chip" data-type="מכתב">✉ מכתבים</button>
          <button class="chip" data-type="מסמך משפטי">⚖ משפטיים</button>
          <button class="chip" data-type="רשימה או טבלה">📋 רשימות</button>
          <button class="chip" data-type="מסמך ממלכתי">🏛 ממלכתיים</button>
          <button class="chip" data-type="טקסט ספרותי">📖 ספרותיים</button>
          <button class="chip" data-type="טקסט פרא-ספרותי">📃 פרא-ספרותיים</button>
        </div>
      </div>

      <div class="browse-group browse-group--single">
        <button class="chip chip--surprise" id="btn-surprise" aria-label="מסמך מפתיע">
          🎲 הפתע אותי
        </button>
      </div>

    </div>
  </section>

  <div class="search-bar-wrapper">
    <div class="search-bar-inner">
      <div class="search-input-wrap">
        <span class="search-icon" aria-hidden="true">🔍</span>
        <input type="search" id="search-input" class="search-input"
          placeholder="חיפוש חופשי — שם, מקום, נושא…"
          autocomplete="off" spellcheck="false">
        <button class="search-clear" id="search-clear" aria-label="נקה חיפוש" hidden>✕</button>
      </div>
      <div class="filters" id="filters">
        <select id="filter-type" class="filter-select" aria-label="סוג מסמך">
          <option value="">כל הסוגים</option>
        </select>
        <select id="filter-lang" class="filter-select" aria-label="שפה">
          <option value="">כל השפות</option>
        </select>
        <select id="filter-library" class="filter-select" aria-label="ספרייה">
          <option value="">כל הספריות</option>
        </select>
        <select id="filter-has" class="filter-select" aria-label="תוכן">
          <option value="">כל המסמכים</option>
          <option value="img">🖼 עם תמונה</option>
          <option value="tr">📝 עם תמלול</option>
          <option value="tl">🌐 עם תרגום</option>
        </select>
        <button class="btn-reset" id="btn-reset" hidden aria-label="אפס סינון">✕ נקה</button>
      </div>
    </div>
  </div>

  <main class="main-content">
    <div class="results-bar" id="results-bar" aria-live="polite"></div>
    <div class="cards-grid" id="cards-grid" role="list"></div>
    <div class="pagination" id="pagination" aria-label="דפים"></div>
    <div class="loading-state" id="loading-state">
      <div class="spinner"></div>
      <p>טוען מסמכים…</p>
    </div>
    <div class="empty-state" id="empty-state" hidden>
      <p class="empty-icon" aria-hidden="true">📜</p>
      <p>לא נמצאו מסמכים. נסו לשנות את החיפוש.</p>
      <button class="btn-reset-inline" id="btn-reset-empty">הצג את כל המסמכים</button>
    </div>
  </main>

  <footer class="site-footer">
    <p>
      נתונים: <a href="https://geniza.princeton.edu" target="_blank" rel="noopener">Princeton Geniza Project</a>
      — רישיון CC BY-NC 4.0
    </p>
    <p class="footer-build">עודכן: {build_date}</p>
  </footer>

  <script>const TOTAL_DOCS = {total_docs};</script>
  <script src="assets/search.js"></script>
</body>
</html>
"""

FRAGMENT_HTML = """\
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title id="page-title">מסמך גניזה — גניזת קהיר</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Frank+Ruhl+Libre:wght@300;400;500;700;900&family=Heebo:wght@300;400;500;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="assets/style.css">
</head>
<body class="fragment-body">

  <nav class="top-nav" aria-label="ניווט">
    <a href="index.html" class="nav-home">← חזרה לגלריה</a>
    <span class="nav-breadcrumb" id="nav-breadcrumb" aria-current="page"></span>
  </nav>

  <div class="loading-state" id="loading-state">
    <div class="spinner"></div>
    <p>טוען מסמך…</p>
  </div>

  <article class="fragment-article" id="fragment-article" hidden>

    <header class="fragment-header">
      <div class="fragment-badges" id="fragment-badges"></div>
      <h1 class="fragment-shelfmark" id="fragment-shelfmark"></h1>
      <p class="fragment-library" id="fragment-library"></p>
    </header>

    <div class="fragment-layout">

      <div class="fragment-image-col">
        <div class="image-frame" id="image-frame">
          <div class="image-placeholder" id="image-placeholder">
            <span class="placeholder-glyph" aria-hidden="true">📜</span>
            <span>אין תמונה זמינה</span>
          </div>
          <img
            id="fragment-img"
            class="fragment-img"
            alt=""
            hidden
          >
          <div class="image-caption" id="image-caption" hidden></div>
        </div>
        <div class="image-links" id="image-links"></div>
      </div>

      <div class="fragment-meta-col">
        <dl class="meta-list" id="meta-list"></dl>

        <div class="description-block" id="description-block" hidden>
          <h2 class="section-label">תיאור</h2>
          <p class="description-text" id="description-text"></p>
        </div>

        <div class="tags-block" id="tags-block" hidden>
          <h2 class="section-label">תגיות</h2>
          <div class="tags-list" id="tags-list"></div>
        </div>

        <div class="actions-block">
          <a id="princeton-link" href="#" target="_blank" rel="noopener" class="btn-primary">
            צפייה ב-Princeton Geniza Project ↗
          </a>
        </div>
      </div>

    </div>

    <nav class="fragment-nav" id="fragment-nav" aria-label="ניווט בין מסמכים"></nav>

  </article>

  <footer class="site-footer">
    <p>
      נתונים ממאגר
      <a href="https://github.com/princetongenizalab/pgp-metadata" target="_blank" rel="noopener">Princeton Geniza Project</a>
      — רישיון CC BY-NC 4.0
    </p>
  </footer>

  <script src="assets/fragment.js"></script>
</body>
</html>
"""


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    import argparse
    from datetime import date

    parser = argparse.ArgumentParser(description="Build Geniza Explorer static site")
    parser.add_argument("--no-download", action="store_true", help="Use cached CSV only")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of documents")
    parser.add_argument("--force-download", action="store_true", help="Re-download CSV even if cached")
    args = parser.parse_args()

    print("\n── Geniza Explorer Build ─────────────────────────────")

    # 1. Download / load CSV
    print("\n[1/4] CSV")
    if args.no_download and not CACHE_FILE.exists():
        print("  ✗  No cached CSV found. Remove --no-download to fetch it.")
        sys.exit(1)
    csv_file = download_csv(force=args.force_download) if not args.no_download else CACHE_FILE

    # 2. Parse documents
    print("\n[2/4] Parsing")
    docs = load_docs(csv_file, limit=args.limit)
    print(f"  ✓  {len(docs):,} documents loaded")

    # Build ID → index map for prev/next navigation
    id_to_idx = {doc["id"]: i for i, doc in enumerate(docs)}

    # 3. Write JSON data files
    print("\n[3/4] Writing data files")
    DATA_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)

    # search index
    search_index = build_search_index(docs)
    write_json(DATA_DIR / "search.json", search_index)
    size_kb = (DATA_DIR / "search.json").stat().st_size // 1024
    print(f"  ✓  data/search.json  ({size_kb} KB, {len(search_index):,} entries)")

    # per-document JSON (full detail)
    for i, doc in enumerate(docs):
        idx = id_to_idx[doc["id"]]
        prev_id = docs[idx - 1]["id"] if idx > 0 else None
        next_id = docs[idx + 1]["id"] if idx < len(docs) - 1 else None
        detail = {**doc, "prev": prev_id, "next": next_id, "pos": idx + 1, "total": len(docs)}
        write_json(DOCS_DIR / f"{doc['id']}.json", detail)
        if (i + 1) % 5000 == 0:
            print(f"  …  {i+1:,}/{len(docs):,}")

    print(f"  ✓  {len(docs):,} document JSON files written to data/docs/")

    # 4. Write HTML pages
    print("\n[4/4] Writing HTML")
    build_date = date.today().strftime("%-d %B %Y")

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(INDEX_HTML.format(total_docs=len(docs), build_date=build_date))
    print("  ✓  index.html")

    with open("fragment.html", "w", encoding="utf-8") as f:
        f.write(FRAGMENT_HTML)
    print("  ✓  fragment.html")

    print("\n── Done ──────────────────────────────────────────────")
    print(f"   {len(docs):,} documents • index.html • fragment.html")
    print(f"   Open index.html in a browser to preview.\n")


if __name__ == "__main__":
    main()
