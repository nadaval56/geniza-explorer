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

import a11y_snippets

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


def build_search_index(docs, translations_he=None, tags_he=None):
    """Compact per-doc record for the search index."""
    translations_he = translations_he or {}
    tags_he = tags_he or {}
    index = []
    for doc in docs:
        entry = {"id": doc["id"]}
        if doc["shelfmark"]:        entry["s"]   = doc["shelfmark"]
        if doc["type_he"]:          entry["th"]  = doc["type_he"]
        if doc["lang_he"]:          entry["lh"]  = doc["lang_he"]
        if doc["origin"]:           entry["or"]  = doc["origin"]
        if doc["date"]:             entry["dt"]  = doc["date"]
        if doc["library"]:          entry["lib"] = doc["library"]
        # Rich English text for search + display (description + tags + mentioned)
        rich_parts = []
        if doc["description"]: rich_parts.append(doc["description"][:200])
        if doc["tags"]:        rich_parts.append(" ".join(doc["tags"]))
        if doc["mentioned"]:   rich_parts.append(doc["mentioned"])
        rich = " ".join(rich_parts)[:400] if rich_parts else ""
        if rich:                    entry["d"]   = rich
        # Hebrew description: prefer real translation, fall back to auto-generated
        desc_he = translations_he.get(doc["id"]) or doc["description_he"]
        if desc_he:                 entry["dh"]  = desc_he
        if doc["iiif_urls"]:
            entry["img"] = 1
            entry["iu"]  = doc["iiif_urls"][0]
        if doc["has_transcription"]:entry["tr"]  = 1
        if doc["has_translation"]:  entry["tl"]  = 1
        c = century_from_date(doc["date"])
        if c:                       entry["c"]   = c
        doc_tags = tags_he.get(doc["id"], [])
        if doc_tags:                entry["tgh"] = doc_tags
        index.append(entry)
    return index


def build_stats(docs, tags_he=None):
    """Compute aggregate statistics for the dashboard."""
    from collections import Counter
    tags_he = tags_he or {}
    type_c, lang_c, cent_c, tag_c = Counter(), Counter(), Counter(), Counter()
    has_img = has_tr = has_tl = 0
    for doc in docs:
        if doc["iiif_urls"]:         has_img += 1
        if doc["has_transcription"]: has_tr  += 1
        if doc["has_translation"]:   has_tl  += 1
        if doc["type_he"]:           type_c[doc["type_he"]] += 1
        lang = (doc["lang_he"] or "").split("؛")[0].strip()
        if lang and lang != "לא ידוע": lang_c[lang] += 1
        c = century_from_date(doc["date"])
        if c: cent_c[c] += 1
        for t in tags_he.get(doc["id"], []):
            if t: tag_c[t] += 1
    return {
        "total":      len(docs),
        "has_img":    has_img,
        "has_tr":     has_tr,
        "has_tl":     has_tl,
        "by_type":    dict(type_c.most_common()),
        "by_lang":    dict(lang_c.most_common(12)),
        "by_century": {str(k): v for k, v in sorted(cent_c.items())},
        "top_tags":   [{"t": t, "c": c} for t, c in tag_c.most_common(200)],
    }


# ── HTML pages ────────────────────────────────────────────────────────────────
INDEX_HTML = """\
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>הגניזה הקהירית — {total_docs:,} מסמכים מגניזת קהיר</title>
  <meta name="description" content="הגניזה הקהירית — {total_docs:,} מסמכים יהודיים מבית הכנסת בן עזרא בקהיר העתיקה. חלון אל החיים היהודיים בימי הביניים: הלכה, מסחר, משפחה ויומיום.">
  <link rel="canonical" href="{base_url}">
  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">

  <!-- Open Graph -->
  <meta property="og:type" content="website">
  <meta property="og:locale" content="he_IL">
  <meta property="og:site_name" content="הגניזה הקהירית">
  <meta property="og:title" content="הגניזה הקהירית — חלון אל החיים היהודיים בימי הביניים">
  <meta property="og:description" content="{total_docs:,} מסמכים יהודיים מבית הכנסת בן עזרא בקהיר העתיקה: הלכה, מסחר, משפחה ויומיום.">
  <meta property="og:url" content="{base_url}">
  <meta property="og:image" content="{base_url}assets/og-image.png">
  <meta property="og:image:type" content="image/png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="הגניזה הקהירית — חלון אל החיים היהודיים בימי הביניים">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="הגניזה הקהירית — חלון אל החיים היהודיים בימי הביניים">
  <meta name="twitter:description" content="{total_docs:,} מסמכים יהודיים מבית הכנסת בן עזרא בקהיר העתיקה.">
  <meta name="twitter:image" content="{base_url}assets/og-image.png">

  <!-- Real favicon files. The previous emoji-in-SVG data URI relied on the
       browser rendering <text> inside an SVG favicon, which Chrome and Safari
       do not do — the tab fell back to a blank page icon. -->
  <meta name="theme-color" content="#b5621e">
  <link rel="icon" href="favicon.ico" sizes="32x32">
  <link rel="icon" href="favicon.svg" type="image/svg+xml">
  <link rel="apple-touch-icon" href="assets/apple-touch-icon.png">
  <link rel="manifest" href="site.webmanifest">

  <link rel="preload" href="assets/fonts/frank-ruhl-libre-hebrew.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="assets/fonts/heebo-hebrew.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="assets/fonts.css?v={build_ts}">
  <link rel="stylesheet" href="assets/style.css?v={build_ts}">
  <!-- Leaflet is served from this site, not from a CDN: a CDN <script> tag hands
       every visitor's IP address to a third party on page load, which is exactly
       what the privacy notice promises does not happen. Same reasoning as the
       locally hosted fonts. Vendored copy: assets/vendor/leaflet/ (BSD-2-Clause). -->
  <link rel="stylesheet" href="assets/vendor/leaflet/leaflet.css">
{a11y_head}

  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@graph": [
      {{
        "@type": "WebSite",
        "@id": "{base_url}#website",
        "url": "{base_url}",
        "name": "הגניזה הקהירית",
        "alternateName": "Cairo Geniza — Hebrew Explorer",
        "description": "חלון אל החיים היהודיים בימי הביניים — {total_docs:,} מסמכים מגניזת קהיר.",
        "inLanguage": "he",
        "license": "https://creativecommons.org/licenses/by-nc/4.0/",
        "potentialAction": {{
          "@type": "SearchAction",
          "target": {{"@type": "EntryPoint", "urlTemplate": "{base_url}?q={{search_term_string}}"}},
          "query-input": "required name=search_term_string"
        }}
      }},
      {{
        "@type": "DataCatalog",
        "@id": "{base_url}#catalog",
        "name": "הגניזה הקהירית",
        "url": "{base_url}",
        "inLanguage": ["he", "en"],
        "isAccessibleForFree": true,
        "license": "https://creativecommons.org/licenses/by-nc/4.0/",
        "creditText": "Princeton Geniza Project (CC BY-NC 4.0)",
        "isBasedOn": "https://github.com/princetongenizalab/pgp-metadata",
        "provider": {{
          "@type": "Organization",
          "name": "Princeton Geniza Lab, Princeton University",
          "url": "https://geniza.princeton.edu"
        }},
        "about": {{
          "@type": "Thing",
          "name": "Cairo Geniza",
          "sameAs": "https://www.wikidata.org/wiki/Q1044504"
        }}
      }}
    ]
  }}
  </script>
</head>
<body>

  <a href="#main-content" class="skip-link">דלג לתוכן הראשי</a>

  <header class="site-header">
    <div class="header-inner">
      <div class="header-ornament" aria-hidden="true">✦</div>
      <h1 class="site-title">הגניזה הקהירית</h1>
      <p class="site-subtitle">חלון אל החיים היהודיים בימי הביניים</p>
      <p class="site-intro">
        בבית הכנסת הקטן של בן עזרא בקהיר העתיקה נשמרו, כמעט בנס, כ - 300,000 מסמכים יהודיים — אוצרות שלא נועדו לעיני זרים. במשך למעלה מתשע מאות שנה הצטברו בה דפים נושאי שם ה׳ שאסור היה להשליכם לאשפה: פסקי הלכה ותפילות, שטרי מסחר ומכתבים אישיים, פנקסי קהילה ומכתבי יתומים. מתוך אבק הדורות עולים קולותיהם של חיים יהודיים שלמים, וקודש וחול משמשים בעירבוביה.  {total_docs:,} מהמסמכים האלה מוצגים לפניכם בפרויקט זה.
      </p>
      <a href="about.html" class="about-link">אודות הגניזה הקהירית ←</a>
    </div>
  </header>

  <!-- KPI row -->
  <section class="dashboard-kpi" aria-label="סטטיסטיקות">
    <div class="dash-kpi-row dash-kpi-row--two">
      <div class="kpi-card">
        <span class="kpi-icon" aria-hidden="true">📜</span>
        <span class="kpi-num">{total_docs:,}</span>
        <span class="kpi-label">מסמכים באוסף</span>
      </div>
      <a class="kpi-card kpi-card--dyk" id="kpi-dyk" href="#" aria-label="הידעת?">
        <span class="kpi-icon" aria-hidden="true">💡</span>
        <span class="kpi-dyk-label">הידעת?</span>
        <span class="kpi-dyk-text" id="dyk-text">…</span>
        <span class="kpi-dyk-shelfmark" id="dyk-shelfmark"></span>
      </a>
      <div class="kpi-card" id="kpi-img">
        <span class="kpi-icon" aria-hidden="true">🖼</span>
        <span class="kpi-num">…</span>
        <span class="kpi-label">עם תמונה</span>
      </div>
    </div>
  </section>

  <!-- Search + Cards (appear right after KPIs) -->
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
        </select>
        <button class="btn-reset" id="btn-reset" hidden aria-label="אפס סינון">✕ נקה</button>
      </div>
    </div>
  </div>

  <main class="main-content" id="main-content">
    <noscript>
      <div class="noscript-note">
        <p>
          החיפוש והסינון בעמוד זה פועלים ב-JavaScript. אפשר לעיין בכל
          {total_docs:,} המסמכים גם ללא JavaScript —
          <a href="d/">מפתח המסמכים המלא</a> מכיל עמוד נפרד לכל מסמך,
          ו<a href="t/">דפי הנושאים</a> מרכזים אותם לפי סוג, מקום, תקופה ונושא.
        </p>
      </div>
    </noscript>
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

  <section class="dashboard" id="dashboard" aria-label="סטטיסטיקות אוסף">
    <div class="dash-inner">

      <div class="surprise-wrap">
        <button class="surprise-btn" id="btn-surprise" aria-label="בחר קטע אקראי מהגניזה">
          <div class="surprise-dice">
            <svg viewBox="0 0 100 98" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
              <defs>
                <linearGradient id="sg-top" x1="20%" y1="0%" x2="80%" y2="100%">
                  <stop offset="0%" stop-color="#ffe066"/>
                  <stop offset="100%" stop-color="#f5a623"/>
                </linearGradient>
                <linearGradient id="sg-left" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#e0455a"/>
                  <stop offset="100%" stop-color="#9b1a30"/>
                </linearGradient>
                <linearGradient id="sg-right" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#2a72c3"/>
                  <stop offset="100%" stop-color="#163f7a"/>
                </linearGradient>
                <filter id="sg-sh" x="-20%" y="-20%" width="140%" height="160%">
                  <feDropShadow dx="0" dy="5" stdDeviation="5" flood-color="#1a1040" flood-opacity="0.32"/>
                </filter>
              </defs>
              <ellipse cx="50" cy="93" rx="34" ry="4.5" fill="#1a1040" opacity="0.18"/>
              <polygon points="15,30 50,50 50,88 15,68" fill="url(#sg-left)" stroke="#7a0820" stroke-width="1.2" stroke-linejoin="round"/>
              <polygon points="85,30 50,50 50,88 85,68" fill="url(#sg-right)" stroke="#0e2a5a" stroke-width="1.2" stroke-linejoin="round"/>
              <polygon points="50,10 85,30 50,50 15,30" fill="url(#sg-top)" stroke="#c07800" stroke-width="1.2" stroke-linejoin="round" filter="url(#sg-sh)"/>
              <circle cx="34" cy="21" r="3.2" fill="#7a3800" opacity="0.85"/>
              <circle cx="66" cy="21" r="3.2" fill="#7a3800" opacity="0.85"/>
              <circle cx="50" cy="30" r="3.2" fill="#7a3800" opacity="0.85"/>
              <circle cx="34" cy="39" r="3.2" fill="#7a3800" opacity="0.85"/>
              <circle cx="66" cy="39" r="3.2" fill="#7a3800" opacity="0.85"/>
              <circle cx="28" cy="43" r="2.4" fill="#ffb0bb" opacity="0.7"/>
              <circle cx="38" cy="74" r="2.4" fill="#ffb0bb" opacity="0.7"/>
              <circle cx="78" cy="41" r="2.4" fill="#a8d4ff" opacity="0.65"/>
              <circle cx="68" cy="59" r="2.4" fill="#a8d4ff" opacity="0.65"/>
              <circle cx="57" cy="77" r="2.4" fill="#a8d4ff" opacity="0.65"/>
            </svg>
          </div>
          <span class="surprise-title">הפתע אותי</span>
          <span class="surprise-sub">בחר קטע אקראי מהגניזה</span>
        </button>
      </div>

      <div class="dash-panels">

        <div class="dash-panel dash-panel--wide">
          <div class="dash-panel-hd">
            <h2 class="dash-panel-title">נושאים מרכזיים</h2>
            <a class="dash-panel-hint dash-panel-link" href="t/">כל 131 הנושאים ←</a>
          </div>
          <div class="tag-cloud" id="tag-cloud"><span class="dash-loading">טוען…</span></div>
        </div>

        <div class="dash-panel dash-panel--wide dash-panel--map">
          <div class="dash-panel-hd">
            <h2 class="dash-panel-title">מפת המקומות שמוזכרים בגניזה</h2>
            <span class="dash-panel-hint">לחץ על סיכה לסינון לפי מיקום</span>
          </div>
          <div id="geniza-map"></div>
        </div>

        <div class="dash-panel dash-panel--wide dash-panel--spices">
          <div class="spice-banner-wrap">
            <img src="assets/spice-market.png" alt="שוק התבלינים" class="spice-banner-img" onerror="this.style.display='none'">
          </div>
          <div class="dash-panel-hd">
            <h2 class="dash-panel-title">תבלינים וסחורות יקרות</h2>
            <a class="dash-panel-hint dash-panel-link" href="t/">כל הנושאים ←</a>
          </div>
          <div class="spice-buttons" id="spice-buttons"><span class="dash-loading">טוען…</span></div>
        </div>

        <div class="dash-panel">
          <div class="dash-panel-hd">
            <h2 class="dash-panel-title">לפי סוג מסמך</h2>
            <span class="dash-panel-hint">לחץ לסינון</span>
          </div>
          <div class="dist-list" id="dist-type"></div>
        </div>

        <div class="dash-panel">
          <h2 class="dash-panel-title">לפי שפה ראשית</h2>
          <div class="dist-list" id="dist-lang"></div>
        </div>

        <div class="dash-panel dash-panel--century">
          <div class="dash-panel-hd">
            <h2 class="dash-panel-title">לאורך הדורות</h2>
            <span class="dash-panel-hint">לחץ לסינון</span>
          </div>
          <div class="century-chart" id="dist-century"></div>
        </div>

      </div>

    </div>
  </section>

  <footer class="site-footer">
    <p>
      נתונים: <a href="https://geniza.princeton.edu" target="_blank" rel="noopener">Princeton Geniza Project</a>
      — רישיון
      <a href="https://creativecommons.org/licenses/by-nc/4.0/deed.he" target="_blank" rel="noopener license">CC BY-NC 4.0</a>
    </p>
    <p class="footer-note">
      התיאורים בעברית הם תרגום ועיבוד של תיאורי המסמכים המקוריים באנגלית.
      השימוש בחומרים מותר למטרות לא-מסחריות בלבד, בציון המקור.
    </p>
    <p>
      <a href="about.html">אודות, קרדיטים ותנאי שימוש</a> ·
      <a href="t/">נושאים</a> ·
      <a href="d/">מפתח כל המסמכים</a> ·
      <a href="privacy/">מדיניות פרטיות</a> ·
      <a href="accessibility/">הצהרת נגישות</a>
    </p>
    <p class="footer-build">עודכן: {build_date}</p>
  </footer>

  <script>const TOTAL_DOCS = {total_docs};</script>
  <script src="assets/vendor/leaflet/leaflet.js"></script>
  <script src="assets/search.js?v={build_ts}"></script>
{a11y_foot}
</body>
</html>
"""

FRAGMENT_HTML = """\
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>מסמך גניזה — הגניזה הקהירית</title>
  <!-- Every document now has its own prerendered page under /d/, which carries
       real HTML content plus per-document title, description, Open Graph and
       schema.org data. This page is kept only so that links and bookmarks of
       the form fragment.html?id=N — the URL shape the site used before — keep
       working. It is Disallow-ed in robots.txt so it never competes with the
       canonical page for indexing. -->
  <meta name="robots" content="noindex, follow">
  <link rel="icon" href="favicon.ico" sizes="32x32">
  <link rel="stylesheet" href="assets/fonts.css?v={build_ts}">
  <link rel="stylesheet" href="assets/style.css?v={build_ts}">
  <script>
    (function () {{
      var id = new URLSearchParams(location.search).get('id');
      location.replace(id ? 'd/' + encodeURIComponent(id) + '.html' : 'index.html');
    }})();
  </script>
</head>
<body class="fragment-body">
  <div class="loading-state">
    <div class="spinner"></div>
    <p>מעביר לעמוד המסמך…</p>
    <p><a id="manual-link" href="./">המשך לגלריה</a></p>
  </div>
  <noscript>
    <p style="text-align:center;padding:2rem">
      עמוד זה עבר. <a href="d/">עברו למפתח המסמכים</a> או
      <a href="./">חזרו לגלריה</a>.
    </p>
  </noscript>
  <script>
    (function () {{
      var id = new URLSearchParams(location.search).get('id');
      if (id) document.getElementById('manual-link').href = 'd/' + encodeURIComponent(id) + '.html';
    }})();
  </script>
</body>
</html>
"""


# ── Main ───────────────────────────────────────────────────────────────────────
def write_html_only(args):
    """Regenerate the HTML pages (and d/, sitemap, robots) from committed data.

    Useful when only the templates changed: it skips the CSV fetch and the
    36k-file data rewrite, and it is the path CI falls back to when the
    Princeton Geniza Project CSV is unreachable.
    """
    from datetime import date
    import prerender

    with open(DATA_DIR / "stats.json", encoding="utf-8") as f:
        total = json.load(f)["total"]

    site_url = args.base_url or prerender.base_url()
    if not site_url.endswith("/"):
        site_url += "/"

    build_date = date.today().strftime("%-d %B %Y")
    build_ts = date.today().strftime("%Y%m%d")

    print("\n── Geniza Explorer: HTML only ────────────────────────")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(INDEX_HTML.format(total_docs=total, build_date=build_date,
                                  build_ts=build_ts, base_url=site_url,
                                  a11y_head=a11y_snippets.head("", build_ts),
                                  a11y_foot=a11y_snippets.foot("", build_ts)))
    print("  ✓  index.html")
    with open("fragment.html", "w", encoding="utf-8") as f:
        f.write(FRAGMENT_HTML.format(build_ts=build_ts))
    print("  ✓  fragment.html (redirect shim → d/<id>.html)")

    if not args.no_prerender:
        prerender.run(base=site_url)
    print("── Done ──────────────────────────────────────────────\n")


def main():
    import argparse
    from datetime import date

    parser = argparse.ArgumentParser(description="Build Geniza Explorer static site")
    parser.add_argument("--no-download", action="store_true", help="Use cached CSV only")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of documents")
    parser.add_argument("--force-download", action="store_true", help="Re-download CSV even if cached")
    parser.add_argument("--no-prerender", action="store_true",
                        help="Skip generating the crawlable pages under d/")
    parser.add_argument("--base-url", default=None,
                        help="Canonical site root; defaults to CNAME, else GitHub Pages")
    parser.add_argument("--html-only", action="store_true",
                        help="Rewrite the HTML pages from the committed data, no CSV fetch")
    args = parser.parse_args()

    if args.html_only:
        return write_html_only(args)

    print("\n── Geniza Explorer Build ─────────────────────────────")

    # 0. Load Hebrew translations + Hebrew tags (generated by translate.py / apply_tags.py)
    translations_path = DATA_DIR / "translations_he.json"
    translations_he = {}
    if translations_path.exists():
        with open(translations_path, encoding="utf-8") as f:
            translations_he = json.load(f)
        print(f"\n[0/5] Translations: {len(translations_he):,} cached Hebrew descriptions loaded")
    else:
        print("\n[0/5] Translations: none yet (run translate.py to generate)")

    tags_he_path = DATA_DIR / "tags_he.json"
    tags_he = {}
    if tags_he_path.exists():
        with open(tags_he_path, encoding="utf-8") as f:
            tags_he = json.load(f)
        print(f"       Hebrew tags:  {len(tags_he):,} documents tagged")

    # 1. Download / load CSV
    print("\n[1/5] CSV")
    if args.no_download and not CACHE_FILE.exists():
        print("  ✗  No cached CSV found. Remove --no-download to fetch it.")
        sys.exit(1)
    csv_file = download_csv(force=args.force_download) if not args.no_download else CACHE_FILE

    # 2. Parse documents
    print("\n[2/5] Parsing")
    docs = load_docs(csv_file, limit=args.limit)
    print(f"  ✓  {len(docs):,} documents loaded")

    # Build ID → index map for prev/next navigation
    id_to_idx = {doc["id"]: i for i, doc in enumerate(docs)}

    # 3. Write JSON data files
    print("\n[3/5] Writing data files")
    DATA_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)

    # search index
    search_index = build_search_index(docs, translations_he, tags_he)
    write_json(DATA_DIR / "search.json", search_index)
    size_kb = (DATA_DIR / "search.json").stat().st_size // 1024
    print(f"  ✓  data/search.json  ({size_kb} KB, {len(search_index):,} entries)")

    # stats
    stats = build_stats(docs, tags_he)
    write_json(DATA_DIR / "stats.json", stats)
    print(f"  ✓  data/stats.json")

    # per-document JSON (full detail)
    for i, doc in enumerate(docs):
        idx = id_to_idx[doc["id"]]
        prev_id = docs[idx - 1]["id"] if idx > 0 else None
        next_id = docs[idx + 1]["id"] if idx < len(docs) - 1 else None
        # Prefer real translation over auto-generated metadata description
        doc_he = translations_he.get(doc["id"])
        if doc_he:
            doc = {**doc, "description_he": doc_he}
        doc_tags_he = tags_he.get(doc["id"], [])
        detail = {**doc, "tags_he": doc_tags_he, "prev": prev_id, "next": next_id, "pos": idx + 1, "total": len(docs)}
        write_json(DOCS_DIR / f"{doc['id']}.json", detail)
        if (i + 1) % 5000 == 0:
            print(f"  …  {i+1:,}/{len(docs):,}")

    print(f"  ✓  {len(docs):,} document JSON files written to data/docs/")

    # מסמך שפרינסטון מחקה או מיזגה נעלם מן ה-CSV, אבל הקובץ שלו נשאר כאן —
    # prerender בונה לו עמוד, ה-sitemap מכריז עליו, ומספר העמודים בפועל גדל
    # מעל המספר ש-index.html מצהיר עליו. שלושה כאלה הצטברו עד ספטמבר 2026.
    # הגיזום מדלג על --limit, שבו הקיצור עצמו הוא שמותיר את השאר "יתומים".
    if args.limit is None:
        live = {doc["id"] for doc in docs}
        stale = [p for p in DOCS_DIR.glob("*.json") if p.stem not in live]
        # רשת ביטחון: CSV קטוע לא ימחק את האוסף. הסף היה 1%, וזה היה צר מדי:
        # בין הסנאפשוט של מאי 2026 ל-CSV של ספטמבר פרינסטון הסירה 268 מסמכים
        # והוסיפה 570 — כלומר מחיקות אמיתיות הגיעו ל-0.74%, במרחק נגיעה מסף
        # שהיה עוצר את הגיזום ומחזיר בשקט את הפער בין המספרים. 5% עדיין תופס
        # את המקרה שהסף נועד לו: הורדה שנקטעה מותירה עשרות אחוזים של "מתים".
        if len(stale) > max(50, len(docs) // 20):
            print(f"  !  {len(stale):,} stale files — too many to be real deletions, "
                  f"keeping them. Check the CSV.")
        else:
            for p in stale:
                p.unlink()
            if stale:
                print(f"  ✓  {len(stale)} stale document file(s) removed: "
                      f"{', '.join(sorted(p.stem for p in stale))}")

    # 4. Write HTML pages
    print("\n[4/5] Writing HTML")
    build_date = date.today().strftime("%-d %B %Y")
    build_ts   = date.today().strftime("%Y%m%d")

    import prerender

    site_url = args.base_url or prerender.base_url()
    if not site_url.endswith("/"):
        site_url += "/"

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(INDEX_HTML.format(total_docs=len(docs), build_date=build_date,
                                  build_ts=build_ts, base_url=site_url,
                                  a11y_head=a11y_snippets.head("", build_ts),
                                  a11y_foot=a11y_snippets.foot("", build_ts)))
    print("  ✓  index.html")

    with open("fragment.html", "w", encoding="utf-8") as f:
        f.write(FRAGMENT_HTML.format(build_ts=build_ts))
    print("  ✓  fragment.html (redirect shim → d/<id>.html)")

    # Prerender for crawlers. index.html and the viewer are client-side
    # rendered, so without this step nothing that skips JavaScript — the AI
    # crawlers, the WhatsApp/Telegram/Slack unfurlers, Googlebot's first pass
    # — can see a single document.
    if args.no_prerender:
        print("\n[5/5] Prerender skipped (--no-prerender)")
    else:
        print("\n[5/5] Prerender")
        prerender.run(base=site_url)

    print("\n── Done ──────────────────────────────────────────────")
    print(f"   {len(docs):,} documents • index.html • fragment.html")
    print(f"   Open index.html in a browser to preview.\n")


if __name__ == "__main__":
    main()
