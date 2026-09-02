#!/usr/bin/env python3
"""
Prerender the Geniza Explorer for crawlers.

The gallery and the document viewer are client-side rendered: index.html ships
an empty grid and fragment.html?id=N pulls data/docs/N.json with fetch(). That
works for people with JavaScript, but it leaves the site invisible to anything
that does not execute JS — the AI/LLM crawlers (GPTBot, ClaudeBot, PerplexityBot,
Applebot-Extended), the link unfurlers behind WhatsApp, Telegram, Slack, X and
iMessage, and Googlebot's first-pass HTML indexer. There is also no crawl path
at all: nothing in the shipped HTML links to any of the 35,924 documents.

This script closes both gaps without touching the interactive experience:

    d/<id>.html      a complete, self-contained HTML page per document, with
                     per-document <title>, description, canonical, Open Graph,
                     Twitter card and schema.org JSON-LD, plus rel=prev/next
                     links that chain every document into one walkable path
    d/index.html     paginated static directory of the whole collection, so a
                     crawler can reach every document from the home page
    sitemap.xml      every URL on the site
    robots.txt       crawl directives + sitemap pointer

Run it after build.py (build.py writes data/docs/*.json, which is the input
here). Output paths are gitignored and generated in CI at deploy time.

    python prerender.py [--limit N] [--base-url https://example.com/]
"""

import argparse
import hashlib
import html
import json
import pathlib
import re
import sys
from datetime import date

import a11y_snippets
import tag_pages

ROOT = pathlib.Path(__file__).parent
DOCS_DIR = ROOT / "data" / "docs"
EN_DIR   = ROOT / "data" / "en"
OUT_DIR = ROOT / "d"
TAG_DIR = ROOT / "t"

DEFAULT_BASE_URL = "https://nadaval56.github.io/geniza-explorer/"

SITE_NAME = "הגניזה הקהירית"
SITE_TAGLINE = "חלון אל החיים היהודיים בימי הביניים"
PER_INDEX_PAGE = 250
# Documents listed on one tag hub page. Page 1 is the indexable page and
# carries the intro; the overflow pages exist to keep every document linked.
PER_TAG_PAGE = 100

LICENSE_URL = "https://creativecommons.org/licenses/by-nc/4.0/deed.he"
PGP_URL = "https://geniza.princeton.edu"

META_FIELDS = [
    ("type_he", "סוג מסמך"),
    ("lang_he", "שפה ראשית"),
    ("lang2_he", "שפת משנה"),
    ("origin", "מקום מוצא"),
    ("destination", "יעד"),
    ("date", "תאריך"),
    ("date_original", "תאריך מקורי"),
    ("date_inferred", "תאריך משוער"),
    ("date_rationale", "בסיס לתיארוך"),
    ("library", "ספרייה"),
    ("collection", "אוסף"),
    ("region", "אזור"),
    ("mentioned", "אזכורים"),
    ("lang_note", "הערת שפה"),
    ("multifragment", "רב-קטע"),
]


# ── Helpers ───────────────────────────────────────────────────────────────────
def esc(value):
    return html.escape(str(value or ""), quote=True)


def clean(text):
    """Collapse whitespace — descriptions carry newlines from the source CSV."""
    return re.sub(r"\s+", " ", (text or "")).strip()


def truncate(text, limit=155):
    text = clean(text)
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:־-") + "…"


def base_url():
    """Custom domain if a CNAME is present, otherwise the GitHub Pages URL."""
    cname = ROOT / "CNAME"
    if cname.exists():
        host = cname.read_text().strip().splitlines()[0].strip()
        if host:
            return f"https://{host}/"
    return DEFAULT_BASE_URL


def is_true(value):
    return str(value).strip().lower() in ("true", "1", "yes")


def doc_title(doc):
    """Catalogue-style label. Used in listings, where a shelfmark column scans."""
    shelfmark = clean(doc.get("shelfmark")) or f"PGPID {doc['id']}"
    kind = clean(doc.get("type_he"))
    return f"{shelfmark} — {kind}" if kind else shelfmark


# A description too short to hold a real clause; below this the shelfmark is
# still the most useful thing a search result can show.
TITLE_MIN_SOURCE = 60
TITLE_LIMIT = 62        # <title>: what a search result shows before it truncates
HEADING_LIMIT = 115     # <h1>: the page has room the search result does not

CLAUSE_BREAK = re.compile(r"[,;:]")

# Hebrew words that demand a continuation. Cutting after one of them reads as a
# sentence that broke rather than one that ended: "לאליהו הכהן הרביעי בן",
# "האישה הנקראת בת", "מדריך לניחוש, תוך שימוש".
DANGLING = {
    "של", "את", "עם", "אל", "על", "בן", "בת", "מן", "אב", "בת", "לפי", "תוך",
    "בין", "או", "גם", "כי", "אך", "אבל", "אשר", "כל", "אחד", "אחת", "שתי",
    "שני", "לכבוד", "בנוגע", "בשם", "מאת", "בידי", "עבור", "נגד", "לאחר",
    "לפני", "בתוך", "מתוך", "ללא", "בעניין", "בדבר", "כדי", "וכן", "כנראה",
    "הנקרא", "הנקראת", "הידוע", "המכונה", "ר'", "ר׳", "בר", "אבו", "אבן", "בני",
}

# Words that can end a sentence but not a heading: they announce what comes next.
TRAILING = {
    "במילים", "בנוסח", "כדלקמן", "הבא", "הבאים", "הבאות", "הכלה", "החתן",
    "לאמור", "ובו", "ובה", "שבו", "שבה", "כולל", "הכולל", "המכיל", "ובהם",
}


def _clause(text, limit):
    """The opening of a description, cut where a reader would actually stop.

    Nine descriptions in ten open with a sentence shorter than HEADING_LIMIT, so
    the common case is no cut at all. When one is needed, a comma beats a word
    boundary and a word boundary beats a character count — and a tail word that
    cannot end a phrase is dropped rather than left hanging.
    """
    # Many descriptions open with a bare label — "מסמך משפטי.", "מכתב בעברית." —
    # and a heading of eleven characters says nothing a shelfmark does not. When
    # the opening sentence is too thin to stand alone, the next one joins it,
    # as long as the pair still fits.
    parts = [x for x in re.split(r"(?<=[.!?])\s", text) if x.strip()]
    first = parts[0].strip()
    i = 1
    while len(first) < 45 and i < len(parts):
        # Below 25 the label alone is unusable, so the next sentence is taken
        # even when it overshoots — the clipping below trims it to fit, and a
        # trimmed clause still tells the reader more than a catalogue number.
        if len(first) >= 25 and len(first) + 1 + len(parts[i]) > limit:
            break
        first = f"{first} {parts[i].strip()}"
        i += 1
    if len(first) <= limit:
        out = first
    else:
        cut = first[:limit + 1]
        for m in reversed(list(CLAUSE_BREAK.finditer(cut))):
            if m.start() >= 25:
                cut = cut[:m.start()]
                break
        else:
            words = cut.rsplit(" ", 1)[0].split(" ")
            while words and (words[-1] in DANGLING or len(words[-1]) <= 1):
                words.pop()
            cut = " ".join(words)
        out = cut

    # An opened bracket that never closes reads as damage; drop it and its tail.
    # Dropping it can expose a new dangling word ("הפותח במילים" once the quote
    # it introduced is gone), so the tail is cleaned again afterwards.
    for opener, closer in (("(", ")"), ("[", "]"), ("\"", "\"")):
        if out.count(opener) > out.count(closer):
            out = out[:out.rindex(opener)]
    words = out.strip().split(" ")
    while len(words) > 4 and (words[-1] in DANGLING or words[-1] in TRAILING):
        words.pop()
    return " ".join(words).strip().rstrip(" .,;:־-–\u05f3\u05f4")


def search_title(doc):
    """What a search result should say — for <title>, og:title and JSON-LD.

    The catalogue label is what a researcher types when they already know the
    document: T-S 13J35.3. Nobody else types it, and it was occupying the one
    line a search result gives you. The Hebrew description opens with the words
    people actually search, so that goes first and the shelfmark follows it,
    still findable by exact match.

    Documents whose Hebrew description is too short to yield a clause keep the
    catalogue label: half a sentence cut mid-word is worse than a shelfmark.
    """
    shelfmark = clean(doc.get("shelfmark")) or f"PGPID {doc['id']}"
    heading = page_heading(doc, limit=TITLE_LIMIT)
    return f"{heading} · {shelfmark}" if heading else doc_title(doc)


def page_heading(doc, limit=HEADING_LIMIT):
    """The descriptive clause on its own, for the visible <h1>.

    Longer than the <title> version on purpose. A search result is one line and
    Google cuts it near sixty characters; the page itself has a whole heading to
    spend, and at this limit nine descriptions in ten need no cut at all.

    Returns None when the description is too short to yield a clause, and the
    heading falls back to the shelfmark.
    """
    text = clean(doc.get("description_he"))
    if len(text) < TITLE_MIN_SOURCE:
        return None
    out = _clause(text, limit)
    return out if len(out) >= 25 else None


def doc_description(doc):
    """Best available prose, Hebrew first, English as a fallback."""
    return clean(doc.get("description_he")) or clean(doc.get("description"))


def summary_line(doc):
    """One-line factual summary for pages with no description at all."""
    bits = [clean(doc.get("type_he")), clean(doc.get("lang_he")),
            clean(doc.get("date")), clean(doc.get("library"))]
    return " · ".join(b for b in bits if b)


def meta_description(doc):
    """The snippet under the title. The Hebrew description leads.

    It used to open with the shelfmark, which spent the first twenty-odd
    characters — the ones a reader actually reads — on a catalogue number.
    """
    text = clean(doc.get("description_he"))
    if text:
        return truncate(text)
    shelfmark = clean(doc.get("shelfmark")) or f"PGPID {doc['id']}"
    fallback = doc_description(doc) or summary_line(doc)
    return truncate(f"{shelfmark} — {fallback}" if fallback else shelfmark)


# ── Per-institution image rights ──────────────────────────────────────────────
# Deliberately specific: "open licence" is not a licence. Each holding library
# publishes its digitised Geniza images under its own terms, and most of them
# are non-commercial, which the site has to state rather than imply.
IMAGE_RIGHTS = [
    (("jtsl", "jewish theological", "jts", "בית המדרש"),
     "תצלומים: Jewish Theological Seminary — נחלת הכלל / CC0",
     "https://creativecommons.org/publicdomain/zero/1.0/"),
    (("cul", "cambridge", "קיימברידג"),
     "תצלומים: Cambridge University Library — CC BY-NC 3.0",
     "https://creativecommons.org/licenses/by-nc/3.0/"),
    (("bodleian", "בודליאן", "oxford"),
     "תצלומים: Bodleian Libraries, University of Oxford — CC BY-NC 4.0",
     "https://creativecommons.org/licenses/by-nc/4.0/"),
    (("nli", "national library of israel", "הספרייה הלאומית"),
     "תצלומים: הספרייה הלאומית של ישראל — ראו תנאי השימוש באתר הספרייה", ""),
    (("jrl", "john rylands", "manchester"),
     "תצלומים: John Rylands Library, University of Manchester — CC BY-NC-SA 4.0",
     "https://creativecommons.org/licenses/by-nc-sa/4.0/"),
]


def image_rights(library):
    key = (library or "").lower()
    for needles, label, url in IMAGE_RIGHTS:
        if any(n in key for n in needles):
            return label, url
    return ("תצלומים: זכויות היוצרים שמורות למוסד המחזיק — "
            "ראו תנאי השימוש באתר הספרייה הדיגיטלית"), ""


TYPE_BADGE = {
    "מכתב": "badge-type-letter",
    "מסמך משפטי": "badge-type-legal",
    "טקסט ספרותי": "badge-type-lit",
    "טקסט דתי": "badge-type-rel",
    "טקסט פרא-ספרותי": "badge-type-para",
}


# ── Page rendering ────────────────────────────────────────────────────────────
def render_meta_rows(doc):
    """Bare <dt>/<dd> pairs — .meta-list is a CSS grid whose children they are."""
    rows = []
    for key, label in META_FIELDS:
        value = clean(doc.get(key))
        if not value:
            continue
        if key == "multifragment" and value not in ("true", "True", "1"):
            continue
        rows.append(f"          <dt>{esc(label)}</dt><dd>{esc(value)}</dd>")
    return "\n".join(rows)


def render_tags(doc, root="../"):
    """Tag pills. A tag with a hub page under /t/ becomes a link to it.

    This is what builds the internal link graph: without it every document is a
    leaf that only the paginated index reaches. Tags with no hub page — and the
    raw English tags shown for documents that were never tagged in Hebrew — stay
    plain text, because there is nowhere to send the reader.
    """
    tags = [clean(t) for t in (doc.get("tags_he") or doc.get("tags") or []) if clean(t)]
    if not tags:
        return ""

    def pill(tag):
        page = tag_pages.TAG_PAGES.get(tag)
        if not page:
            return f'<span class="tag-pill">{esc(tag)}</span>'
        return (f'<a class="tag-pill tag-pill-link" href="{root}t/{esc(page["slug"])}/">'
                f'{esc(tag)}</a>')

    pills = "".join(pill(t) for t in tags)
    return f"""
        <div class="tags-block">
          <h2 class="section-label">תגיות</h2>
          <div class="tags-list">{pills}</div>
        </div>"""


def render_links(doc):
    links = []
    for i, url in enumerate(doc.get("fragment_urls") or []):
        suffix = f" {i + 1}" if len(doc["fragment_urls"]) > 1 else ""
        links.append((url, f"צפייה בספרייה הדיגיטלית{suffix}"))
    if not links:
        for i, url in enumerate(doc.get("iiif_urls") or []):
            suffix = f" {i + 1}" if len(doc["iiif_urls"]) > 1 else ""
            links.append((url, f"מניפסט IIIF{suffix}"))
    if not links:
        return ""
    items = "".join(
        f'<a class="image-link" href="{esc(u)}" target="_blank" rel="noopener nofollow">'
        f'<span class="image-link-icon" aria-hidden="true">🔗</span><span>{esc(label)}</span></a>'
        for u, label in links
    )
    return f'<div class="image-links">{items}</div>'


def render_json_ld(doc, url, base):
    """schema.org description of the manuscript item, for rich results."""
    node = {
        "@context": "https://schema.org",
        "@type": "CreativeWork",
        "@id": url,
        "url": url,
        "name": search_title(doc),
        "inLanguage": "he",
        "isPartOf": {
            "@type": "Collection",
            "name": "Princeton Geniza Project",
            "url": PGP_URL,
        },
        "license": LICENSE_URL,
        "isBasedOn": doc.get("princeton_url") or PGP_URL,
        "creditText": "Princeton Geniza Project (CC BY-NC 4.0)",
        "publisher": {"@type": "Organization", "name": SITE_NAME, "url": base},
    }
    description = doc_description(doc)
    if description:
        node["description"] = truncate(description, 500)
    if clean(doc.get("shelfmark")):
        node["identifier"] = clean(doc["shelfmark"])
    if clean(doc.get("date")):
        node["temporalCoverage"] = clean(doc["date"])
    if clean(doc.get("origin")):
        node["contentLocation"] = {"@type": "Place", "name": clean(doc["origin"])}
    if clean(doc.get("library")):
        node["holdingArchive"] = {
            "@type": "ArchiveOrganization", "name": clean(doc["library"])
        }
    if clean(doc.get("lang_he")):
        node["material"] = clean(doc["lang_he"])
    if doc.get("princeton_url"):
        node["sameAs"] = doc["princeton_url"]

    crumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": SITE_NAME, "item": base},
            {"@type": "ListItem", "position": 2, "name": "כל המסמכים",
             "item": base + "d/"},
            {"@type": "ListItem", "position": 3, "name": doc_title(doc), "item": url},
        ],
    }
    dumps = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    return (f'<script type="application/ld+json">{dumps(node)}</script>\n'
            f'  <script type="application/ld+json">{dumps(crumbs)}</script>')


DOC_PAGE = """<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — {site}</title>
  <meta name="description" content="{description}">
  <link rel="canonical" href="{url}">
{prevnext}  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="{site}">
  <meta property="og:locale" content="he_IL">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{base}assets/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="{site} — {tagline}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{description}">
  <meta name="twitter:image" content="{base}assets/og-image.png">
  <meta name="theme-color" content="#b5621e">
  <link rel="icon" href="{root}favicon.ico" sizes="32x32">
  <link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
  <link rel="apple-touch-icon" href="{root}assets/apple-touch-icon.png">
  <link rel="manifest" href="{root}site.webmanifest">
  <link rel="stylesheet" href="{root}assets/fonts.css">
  <link rel="stylesheet" href="{root}assets/style.css">
{a11y_head}
  {jsonld}
</head>
<body class="fragment-body">

  <a href="#doc-main" class="skip-link">דלג לתוכן המסמך</a>

  <nav class="top-nav" aria-label="ניווט">
    <a href="{root}" class="nav-home">← חזרה לדף הבית של הגניזה</a>
    <span class="nav-breadcrumb" aria-current="page">{breadcrumb}</span>
  </nav>

  <article class="fragment-article" id="doc-main">

    <header class="fragment-header">
      <div class="fragment-badges">{badges}</div>
      {heading_block}
      <p class="fragment-library">{library}</p>
    </header>

    <div class="fragment-layout">

      <div class="fragment-image-col">
        <div class="image-frame">
          <div class="image-placeholder"{ph_hidden}>
            <span class="placeholder-glyph" aria-hidden="true">📜</span>
            <span>{image_note}</span>
          </div>
          <img id="fragment-img" class="fragment-img" alt="" hidden{iiif_attr}>
          <div class="image-caption">{rights}</div>
        </div>
        {links}
      </div>

      <div class="fragment-meta-col">
        <dl class="meta-list">
{meta_rows}
        </dl>
{description_block}{tags}
        <div class="actions-block">
          <a href="{princeton}" target="_blank" rel="noopener" class="btn-primary">
            צפייה ב-Princeton Geniza Project ↗
          </a>
        </div>
      </div>

    </div>

{related}
    <nav class="fragment-nav" aria-label="ניווט בין מסמכים">{docnav}</nav>

  </article>

  <footer class="site-footer">
    <p>
      מסמך {pos} מתוך {total} · נתונים:
      <a href="{pgp}" target="_blank" rel="noopener">Princeton Geniza Project</a>
      — <a href="{license}" target="_blank" rel="noopener license">CC BY-NC 4.0</a>
    </p>
    <p class="footer-note">
      התיאור בעברית הוא תרגום/עיבוד של תיאור המסמך המקורי באנגלית מאת
      Princeton Geniza Project. השימוש בחומרים מותר למטרות לא-מסחריות בלבד.
    </p>
    <p>
      <a href="{root}about.html">אודות הגניזה</a> ·
      <a href="./">כל המסמכים</a> ·
      <a href="{root}privacy/">מדיניות פרטיות</a> ·
      <a href="{root}accessibility/">הצהרת נגישות</a>
    </p>
  </footer>

  <script src="{root}assets/doc-image.js" defer></script>
  <script src="{root}assets/doc-english.js" defer></script>
  <script src="{root}assets/card-thumbs.js" defer></script>
{a11y_foot}
</body>
</html>
"""


def render_doc(doc, base, related_index=None):
    doc_id = doc["id"]
    url = f"{base}d/{doc_id}.html"
    title = search_title(doc)
    heading = page_heading(doc)
    shelfmark = clean(doc.get("shelfmark")) or f"PGPID {doc_id}"

    kind = clean(doc.get("type_he"))
    badges = (f'<span class="badge {TYPE_BADGE.get(kind, "badge-type-other")}">'
              f'{esc(kind or "לא מסווג")}</span>')
    if clean(doc.get("lang_he")):
        badges += f'<span class="badge badge-lang">{esc(clean(doc["lang_he"]))}</span>'
    if is_true(doc.get("has_transcription")):
        badges += '<span class="badge badge-type-rel">📝 תמלול</span>'
    if is_true(doc.get("has_translation")):
        badges += '<span class="badge badge-type-letter">🌐 תרגום</span>'

    # Only the Hebrew is prerendered. The English original from PGP is a verbatim
    # copy of geniza.princeton.edu, and with a median Hebrew description of 108
    # characters it was the bulk of the text on most pages — a near-duplicate of a
    # far more authoritative source, which is a plausible cause of the
    # "crawled, currently not indexed" status. It now loads from
    # data/docs/<id>.json only when the reader asks for it; assets/doc-english.js
    # explains why a click rather than an automatic fetch. Attribution is
    # unaffected: the CC BY-NC credit and the link to PGP are both still on the page.
    #
    # The exception is a document with no Hebrew description at all (6 of 35,940).
    # There the English is all the prose there is, so it stays in the HTML.
    paragraphs = []
    has_he = bool(clean(doc.get("description_he")))
    if has_he:
        paragraphs.append(f'<p class="description-text">{esc(clean(doc["description_he"]))}</p>')
    if clean(doc.get("description")):
        if has_he:
            paragraphs.append(
                f'<button type="button" class="english-toggle" data-doc="{esc(doc_id)}"'
                ' aria-expanded="false" aria-controls="english-desc">'
                'הצג את התיאור המקורי באנגלית</button>'
                '<div class="english-desc" id="english-desc" hidden></div>'
            )
        else:
            paragraphs.append(
                '<p class="description-text" lang="en" dir="ltr">'
                '<span class="desc-lang-note">Princeton Geniza Project description: </span>'
                f'{esc(clean(doc["description"]))}</p>'
            )
    description_block = ""
    if paragraphs:
        description_block = ('\n        <div class="description-block">\n'
                             '          <h2 class="section-label">תיאור</h2>\n          '
                             + "\n          ".join(paragraphs)
                             + "\n        </div>")

    iiif = (doc.get("iiif_urls") or [None])[0]
    rights_label, rights_url = image_rights(doc.get("library") or doc.get("library_raw"))
    rights = (f'<a href="{esc(rights_url)}" target="_blank" rel="noopener license">{esc(rights_label)}</a>'
              if rights_url else esc(rights_label))

    prevnext = ""
    if doc.get("prev"):
        prevnext += f'  <link rel="prev" href="{base}d/{doc["prev"]}.html">\n'
    if doc.get("next"):
        prevnext += f'  <link rel="next" href="{base}d/{doc["next"]}.html">\n'

    nav = []
    if doc.get("prev"):
        nav.append(f'<a class="frag-nav-btn" rel="prev" href="{doc["prev"]}.html">→ המסמך הקודם</a>')
    if doc.get("next"):
        nav.append(f'<a class="frag-nav-btn" rel="next" href="{doc["next"]}.html">המסמך הבא ←</a>')

    return DOC_PAGE.format(
        a11y_head=a11y_snippets.head("../"),
        a11y_foot=a11y_snippets.foot("../"),
        site=esc(SITE_NAME),
        tagline=esc(SITE_TAGLINE),
        title=esc(title),
        description=esc(meta_description(doc)),
        url=esc(url),
        base=esc(base),
        root="../",
        prevnext=prevnext,
        jsonld=render_json_ld(doc, url, base),
        breadcrumb=esc(shelfmark),
        badges=badges,
        heading_block=(
            f'<h1 class="fragment-heading">{esc(heading)}</h1>\n'
            f'      <p class="fragment-shelfmark">{esc(shelfmark)}</p>'
            if heading else
            f'<h1 class="fragment-shelfmark">{esc(shelfmark)}</h1>'
        ),
        shelfmark=esc(shelfmark),
        library=esc(clean(doc.get("library"))),
        image_note=("התצלום זמין בספרייה הדיגיטלית" if iiif else "אין תצלום זמין"),
        ph_hidden="",
        iiif_attr=f' data-iiif="{esc(iiif)}"' if iiif else "",
        rights=rights,
        links=render_links(doc),
        meta_rows=render_meta_rows(doc),
        description_block=description_block,
        tags=render_tags(doc),
        princeton=esc(doc.get("princeton_url") or PGP_URL),
        related=render_related(doc, related_index) if related_index else "",
        docnav="".join(nav),
        pos=f'{doc["pos"]:,}' if isinstance(doc.get("pos"), int) else "",
        total=f'{doc["total"]:,}' if isinstance(doc.get("total"), int) else "",
        pgp=PGP_URL,
        license=LICENSE_URL,
    )


# ── Static collection directory ───────────────────────────────────────────────
INDEX_PAGE = """<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>כל המסמכים — עמוד {page} מתוך {pages} — {site}</title>
  <meta name="description" content="מפתח מלא של {total} מסמכי הגניזה הקהירית — עמוד {page} מתוך {pages}.">
  <link rel="canonical" href="{url}">
{prevnext}  <meta name="robots" content="index, follow">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{site}">
  <meta property="og:locale" content="he_IL">
  <meta property="og:title" content="כל המסמכים — עמוד {page} מתוך {pages}">
  <meta property="og:description" content="מפתח מלא של {total} מסמכי הגניזה הקהירית.">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{base}assets/og-image.png">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="theme-color" content="#b5621e">
  <link rel="icon" href="../favicon.ico" sizes="32x32">
  <link rel="icon" href="../favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="../assets/fonts.css">
  <link rel="stylesheet" href="../assets/style.css">
{a11y_head}
</head>
<body class="fragment-body">

  <a href="#doc-index" class="skip-link">דלג לרשימת המסמכים</a>

  <nav class="top-nav" aria-label="ניווט">
    <a href="../" class="nav-home">← חזרה לדף הבית של הגניזה</a>
    <span class="nav-breadcrumb" aria-current="page">כל המסמכים · עמוד {page}</span>
  </nav>

  <main class="doc-index" id="doc-index">
    <h1 class="doc-index-title">כל המסמכים</h1>
    <p class="doc-index-sub">
      מפתח מלא של {total} המסמכים באוסף, לעיון ולסריקה. לחיפוש חופשי וסינון
      השתמשו ב<a href="../">גלריה הראשית</a>.
    </p>
    <ol class="doc-index-list" start="{start}">
{items}
    </ol>
    <nav class="pagination" aria-label="דפים">{pager}</nav>
  </main>

  <footer class="site-footer">
    <p>
      נתונים: <a href="{pgp}" target="_blank" rel="noopener">Princeton Geniza Project</a>
      — <a href="{license}" target="_blank" rel="noopener license">CC BY-NC 4.0</a>
    </p>
    <p>
      <a href="../about.html">אודות הגניזה</a> ·
      <a href="../privacy/">מדיניות פרטיות</a> ·
      <a href="../accessibility/">הצהרת נגישות</a>
    </p>
  </footer>

{a11y_foot}
</body>
</html>
"""


def render_index_pages(docs, base, out_dir):
    pages = max(1, -(-len(docs) // PER_INDEX_PAGE))
    for n in range(1, pages + 1):
        chunk = docs[(n - 1) * PER_INDEX_PAGE: n * PER_INDEX_PAGE]
        name = "index.html" if n == 1 else f"index-{n}.html"
        url = f"{base}d/" if n == 1 else f"{base}d/index-{n}.html"

        items = "\n".join(
            f'      <li><a href="{esc(d["id"])}.html">{esc(doc_title(d))}</a>'
            f'<span class="doc-index-meta">{esc(summary_line(d))}</span></li>'
            for d in chunk
        )

        prevnext = ""
        if n > 1:
            prev = "" if n == 2 else f"index-{n - 1}.html"
            prevnext += f'  <link rel="prev" href="{base}d/{prev}">\n'
        if n < pages:
            prevnext += f'  <link rel="next" href="{base}d/index-{n + 1}.html">\n'

        links = []
        if n > 1:
            links.append(f'<a class="page-btn" href="{"./" if n == 2 else f"index-{n-1}.html"}">→ הקודם</a>')
        # First, last, a window around the current page, and jumps of ten the
        # whole way. Without the jumps, reaching page 70 of 144 meant clicking
        # "next" sixty-nine times, and a crawler measuring click depth from the
        # home page put every document on that page dozens of levels down.
        window = {1, 2, n - 1, n, n + 1, pages - 1, pages}
        window |= set(range(10, pages + 1, 10))
        for m in sorted(window & set(range(1, pages + 1))):
            target = "./" if m == 1 else f"index-{m}.html"
            active = " active" if m == n else ""
            links.append(f'<a class="page-btn{active}" href="{target}">{m}</a>')
        if n < pages:
            links.append(f'<a class="page-btn" href="index-{n + 1}.html">הבא ←</a>')

        (out_dir / name).write_text(
            INDEX_PAGE.format(
                a11y_head=a11y_snippets.head("../"),
                a11y_foot=a11y_snippets.foot("../"),
                site=esc(SITE_NAME), page=n, pages=pages,
                total=f"{len(docs):,}", url=esc(url), base=esc(base),
                prevnext=prevnext, start=(n - 1) * PER_INDEX_PAGE + 1,
                items=items, pager="".join(links),
                pgp=PGP_URL, license=LICENSE_URL,
            ),
            encoding="utf-8",
        )
    return pages


# How many candidates to keep per bucket. Without a cap, a document tagged
# יהודית-ערבית scans all 12,413 of its neighbours, once per document — the
# build never finished. Keeping the best few dozen per bucket is also better
# on the merits: a reader wants the strongest neighbours, not the nearest.
RELATED_BUCKET = 40
RELATED_DESC = 110
# רכזת נושא מדפיסה מאה כרטיסים בעמוד. בלי תקרה, עמוד פוסטאט לבדו נשא 46,750
# תווי תיאור — טקסט שכבר קיים במלואו בעמוד המסמך עצמו, ו-CSS ממילא קוצץ אותו
# לשלוש שורות. התקרה שומרת בדיוק את מה שנראה.
CARD_DESC = 140

# Cut to four when the site looked like it was at 1,010 MB against a 1 GB
# ceiling. That figure came from du, which counts filesystem blocks: 35,940
# small JSON files under data/docs round up to 4 KB each. Counted in bytes,
# the way Pages counts, the site was 696 MB. Eight is restored.
RELATED_MAX = 8


def _quality(doc):
    """Sort key: a photograph first, then the fuller description.

    Computed once per document in build_related_index and cached by id. Calling
    clean() here for every candidate of every document meant eight hundred
    thousand regex substitutions and a six-minute build.
    """
    return (0 if (doc.get("iiif_urls") or []) else 1,
            -len(clean(doc.get("description_he"))),
            doc.get("pos") or 0)


def build_related_index(docs):
    """Everything needed to find a document's neighbours, built once.

    Before this, the only link from one document to another was "המסמך הבא ←" —
    a single chain 35,940 links long. To get from a letter about Fustat to
    another letter about Fustat you had to walk the whole way, and so did a
    crawler. Every page was a link in a chain instead of a node in a graph.
    """
    buckets = {"tag": {}, "origin": {}, "library": {}}
    sizes = {}
    for doc in docs:
        for raw in (doc.get("tags_he") or []):
            tag = clean(raw)
            if tag:
                buckets["tag"].setdefault(tag, []).append(doc)
        for key in ("origin", "library"):
            value = clean(doc.get(key))
            if value:
                buckets[key].setdefault(value, []).append(doc)

    quality = {doc["id"]: _quality(doc) for doc in docs}
    for kind, groups in buckets.items():
        for value, members in groups.items():
            sizes[(kind, value)] = len(members)
            groups[value] = sorted(members, key=lambda d: quality[d["id"]])[:RELATED_BUCKET]

    return {**buckets, "sizes": sizes, "quality": quality,
            "by_id": {doc["id"]: doc for doc in docs}}


def _tag_weight(size):
    """A tag shared by twelve thousand documents says almost nothing; one shared
    by forty says these two are about the same thing. Weight accordingly."""
    if size <= 200:
        return 6
    if size <= 1000:
        return 4
    if size <= 4000:
        return 2
    return 1


def related_docs(doc, index, limit=RELATED_MAX):
    """Documents worth reading next, scored by how much they share.

    A shared tag is the strongest signal, scaled by how rare that tag is. Same
    place of origin comes next, same holding library last: a library says where
    the fragment sits today, not what it says.
    """
    scores = {}
    for raw in (doc.get("tags_he") or []):
        tag = clean(raw)
        weight = _tag_weight(index["sizes"].get(("tag", tag), 0))
        for other in index["tag"].get(tag, ()):
            if other["id"] != doc["id"]:
                scores[other["id"]] = scores.get(other["id"], 0) + weight
    for kind, weight in (("origin", 2), ("library", 1)):
        value = clean(doc.get(kind))
        for other in index[kind].get(value, ()):
            if other["id"] != doc["id"]:
                scores[other["id"]] = scores.get(other["id"], 0) + weight

    if not scores:
        return []

    lookup, quality = index["by_id"], index["quality"]
    ranked = sorted(scores.items(),
                    key=lambda pair: (-pair[1], quality[pair[0]]))
    return [lookup[doc_id] for doc_id, _ in ranked[:limit]]


def render_doc_card(doc, root="../../", desc_limit=None):
    """A document card, matching the one the home page builds in search.js.

    Deliberately duplicated rather than shared: the home page renders cards in
    the browser from data/search.json, and a tag hub renders them at build time
    from data/docs/. Same markup, same CSS, two producers. If cardHTML() in
    assets/search.js changes shape, change this too — the classes are the
    contract between them.
    """
    kind = clean(doc.get("type_he"))
    badge = f'<span class="badge {TYPE_BADGE.get(kind, "badge-type-other")}">{esc(kind or "לא מסווג")}</span>'

    lang = clean(doc.get("lang_he")).split("؛")[0].strip()
    lang_badge = f'<span class="badge badge-lang">{esc(lang)}</span>' if lang else ""

    icons = ""
    if is_true(doc.get("has_transcription")):
        icons += '<span class="card-icon" title="תמלול">📝</span>'
    if is_true(doc.get("has_translation")):
        icons += '<span class="card-icon" title="תרגום">🌐</span>'

    date = clean(doc.get("date"))
    origin = clean(doc.get("origin"))
    geo = ""
    if date or origin:
        geo = ('<div class="card-geo">'
               + (f'<span class="card-date">{esc(date)}</span>' if date else "")
               + (f'<span class="card-origin">{esc(origin)}</span>' if origin else "")
               + "</div>")

    desc = clean(doc.get("description_he"))
    # A hub lists a hundred documents on one page and a description can run
    # long, so callers that repeat this card across every document page cap it.
    if desc_limit:
        desc = truncate(desc, desc_limit)
    desc_html = f'<p class="card-description">{esc(desc)}</p>' if desc else ""

    library = clean(doc.get("library"))
    footer = f'<div class="card-footer"><span class="card-lib">{esc(library)}</span></div>' if library else ""

    iiif = (doc.get("iiif_urls") or [None])[0]
    thumb = f'<img class="card-thumb" data-iu="{esc(iiif)}" alt="" hidden loading="lazy">' if iiif else ""
    shelfmark = clean(doc.get("shelfmark")) or f'PGPID {doc["id"]}'

    return (
        f'      <a href="{root}d/{esc(doc["id"])}.html" '
        f'class="card{" card--has-thumb" if iiif else ""}" role="listitem" '
        f'aria-label="{esc(shelfmark)}">\n'
        f'        {thumb}\n'
        f'        <div class="card-top">\n'
        f'          <span class="card-shelfmark">{esc(shelfmark)}</span>\n'
        f'          <span class="card-icons" aria-hidden="true">{icons}</span>\n'
        f'        </div>\n'
        f'        <div class="card-meta">{badge}{lang_badge}</div>\n'
        f'        {geo}{desc_html}{footer}\n'
        f'      </a>'
    )

def render_related(doc, index):
    neighbours = related_docs(doc, index)
    if not neighbours:
        return ""
    # The same card the home page and the tag hubs draw, thumbnail included.
    # A related document with no picture next to it reads as an afterthought,
    # and a manuscript is the one thing a reader can judge at a glance.
    items = "\n".join(render_doc_card(other, root="../", desc_limit=RELATED_DESC) for other in neighbours)
    return ('\n    <section class="related-block" aria-labelledby="related-hd">\n'
            '      <h2 class="section-label" id="related-hd">מסמכים קשורים</h2>\n'
            f'      <div class="cards-grid related-grid" role="list">\n{items}\n      </div>\n'
            '    </section>\n')



# ── Tag hub pages ─────────────────────────────────────────────────────────────
TAG_PAGE = """<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — {site}</title>
  <meta name="description" content="{description}">
  <link rel="canonical" href="{url}">
{prevnext}  <meta name="robots" content="{robots}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{site}">
  <meta property="og:locale" content="he_IL">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{base}assets/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="theme-color" content="#b5621e">
  <link rel="icon" href="../../favicon.ico" sizes="32x32">
  <link rel="icon" href="../../favicon.svg" type="image/svg+xml">
  <link rel="manifest" href="../../site.webmanifest">
  <link rel="stylesheet" href="../../assets/fonts.css">
  <link rel="stylesheet" href="../../assets/style.css">
{a11y_head}
  {jsonld}
</head>
<body class="fragment-body">

  <a href="#tag-main" class="skip-link">דלג לרשימת המסמכים</a>

  <nav class="top-nav" aria-label="ניווט">
    <a href="../../" class="nav-home">← חזרה לדף הבית של הגניזה</a>
    <span class="nav-breadcrumb" aria-current="page">{crumb}</span>
  </nav>

  <main class="tag-hub" id="tag-main">

    <header class="tag-header">
      <p class="tag-kicker">{group_label}</p>
      <h1 class="tag-title">{h1}</h1>
      <p class="tag-count">{count} מסמכים באוסף נושאים את התגית הזו.</p>
    </header>
{intro}
    <h2 class="section-label tag-list-label">{list_label}</h2>
    <div class="cards-grid" role="list">
{items}
    </div>
{pager}{related}
  </main>

  <footer class="site-footer">
    <p>
      נתונים: <a href="{pgp}" target="_blank" rel="noopener">Princeton Geniza Project</a>
      — <a href="{license}" target="_blank" rel="noopener license">CC BY-NC 4.0</a>
    </p>
    <p>
      <a href="../../about.html">אודות הגניזה</a> ·
      <a href="../../d/">כל המסמכים</a> ·
      <a href="../../privacy/">מדיניות פרטיות</a> ·
      <a href="../../accessibility/">הצהרת נגישות</a>
    </p>
  </footer>

  <script src="../../assets/card-thumbs.js" defer></script>
{a11y_foot}
</body>
</html>
"""


TAG_DIRECTORY = """<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>נושאים — {count} תגיות במסמכי הגניזה — {site}</title>
  <meta name="description" content="כל הנושאים במסמכי הגניזה הקהירית: סוגי מסמכים, מקומות, תקופות, שפות, בעלי מלאכה, צמחים, תבלינים ואישים — {count} נושאים, כל אחד עם דף משלו.">
  <link rel="canonical" href="{url}">
  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{site}">
  <meta property="og:locale" content="he_IL">
  <meta property="og:title" content="נושאים במסמכי הגניזה הקהירית">
  <meta property="og:description" content="{count} נושאים — סוגי מסמכים, מקומות, תקופות, שפות, בעלי מלאכה, צמחים, תבלינים ואישים.">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{base}assets/og-image.png">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="theme-color" content="#b5621e">
  <link rel="icon" href="../favicon.ico" sizes="32x32">
  <link rel="icon" href="../favicon.svg" type="image/svg+xml">
  <link rel="manifest" href="../site.webmanifest">
  <link rel="stylesheet" href="../assets/fonts.css">
  <link rel="stylesheet" href="../assets/style.css">
{a11y_head}
</head>
<body class="fragment-body">

  <a href="#tag-dir" class="skip-link">דלג לרשימת הנושאים</a>

  <nav class="top-nav" aria-label="ניווט">
    <a href="../" class="nav-home">← חזרה לדף הבית של הגניזה</a>
    <span class="nav-breadcrumb" aria-current="page">נושאים</span>
  </nav>

  <main class="tag-hub" id="tag-dir">

    <header class="tag-header">
      <h1 class="tag-title">נושאים במסמכי הגניזה</h1>
      <p class="tag-count">{count} נושאים, כל אחד עם דף משלו.</p>
    </header>

{sections}
  </main>

  <footer class="site-footer">
    <p>
      נתונים: <a href="{pgp}" target="_blank" rel="noopener">Princeton Geniza Project</a>
      — <a href="{license}" target="_blank" rel="noopener license">CC BY-NC 4.0</a>
    </p>
    <p>
      <a href="../about.html">אודות הגניזה</a> ·
      <a href="../d/">כל המסמכים</a> ·
      <a href="../privacy/">מדיניות פרטיות</a> ·
      <a href="../accessibility/">הצהרת נגישות</a>
    </p>
  </footer>

{a11y_foot}
</body>
</html>
"""


def tag_index(docs):
    """tag → its documents, the ones worth looking at first.

    Order is photo, then length of the Hebrew description, then position. Only
    57% of documents have a photograph, and mixing them in at random left every
    grid row half empty. Sorting them forward also tidies the layout for free:
    the picture cards sit together and the text-only cards sit together, instead
    of alternating down the page.

    Within each group the fullest descriptions come first, so page 1 of a hub —
    the page that has to earn its place in the index — shows the documents with
    the most to say. It also means the hubs improve on their own as the Hebrew
    rewrite project fills descriptions in.
    """
    buckets = {}
    for doc in docs:
        for raw in (doc.get("tags_he") or []):
            tag = clean(raw)
            if tag in tag_pages.TAG_PAGES:
                buckets.setdefault(tag, []).append(doc)
    for items in buckets.values():
        items.sort(key=lambda d: (
            0 if (d.get("iiif_urls") or []) else 1,          # a photo first
            -len(clean(d.get("description_he"))),            # then the fullest description
            d.get("pos") or 0,                               # then stable by position
        ))
    return buckets


def related_tags(tag, buckets, limit=8):
    """Other tags in the same group, biggest first. This is what links the hubs
    to each other instead of leaving 131 dead ends."""
    group = tag_pages.TAG_PAGES[tag]["group"]
    siblings = [(t, len(d)) for t, d in buckets.items()
                if t != tag and tag_pages.TAG_PAGES[t]["group"] == group]
    siblings.sort(key=lambda pair: -pair[1])
    return [t for t, _ in siblings[:limit]]


def render_tag_json_ld(tag, page, url, base, chunk):
    node = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "@id": url,
        "url": url,
        "name": page["h1"],
        "description": truncate(page["intro"], 500),
        "inLanguage": "he",
        "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": base},
        "license": LICENSE_URL,
        "hasPart": [
            {"@type": "CreativeWork", "name": doc_title(d), "url": f"{base}d/{d['id']}.html"}
            for d in chunk
        ],
    }
    crumbs = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": SITE_NAME, "item": base},
            {"@type": "ListItem", "position": 2, "name": "נושאים",
             "item": base + "t/"},
            {"@type": "ListItem", "position": 3, "name": page["h1"], "item": url},
        ],
    }
    dumps = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    return (f'<script type="application/ld+json">{dumps(node)}</script>\n'
            f'  <script type="application/ld+json">{dumps(crumbs)}</script>')


def render_tag_directory(buckets, base, out_dir):
    """/t/ — the hub of hubs. The breadcrumb on every tag page points here, and
    it gives the 131 hubs a single parent that the home page can link to."""
    sections = []
    for key, label in tag_pages.GROUPS.items():
        members = sorted(((t, len(d)) for t, d in buckets.items()
                          if tag_pages.TAG_PAGES[t]["group"] == key),
                         key=lambda pair: -pair[1])
        if not members:
            continue
        links = "".join(
            f'<li><a href="{esc(tag_pages.TAG_PAGES[t]["slug"])}/">{esc(t)}</a>'
            f'<span class="doc-index-meta">{n:,} מסמכים</span></li>'
            for t, n in members
        )
        sections.append(f'      <section class="tag-group">\n'
                        f'        <h2 class="section-label">{esc(label)}</h2>\n'
                        f'        <ul class="tag-group-list">{links}</ul>\n'
                        f'      </section>')

    out_dir.mkdir(exist_ok=True)
    (out_dir / "index.html").write_text(TAG_DIRECTORY.format(
        a11y_head=a11y_snippets.head("../"),
        a11y_foot=a11y_snippets.foot("../"),
        site=esc(SITE_NAME),
        url=esc(base + "t/"),
        base=esc(base),
        count=len(buckets),
        sections="\n".join(sections),
        pgp=PGP_URL,
        license=LICENSE_URL,
    ), encoding="utf-8")


def render_tag_pages(docs, base, out_dir):
    """One hub per tag under /t/<slug>/, paginated so every document is listed.

    Page 1 is the page that has to earn a place in the index: it carries the
    intro, the JSON-LD and the sitemap entry. Pages 2+ carry noindex,follow —
    they exist so a reader who lands on "פוסטאט" can browse all 2,386 documents,
    not so that ~700 lists of card links compete for a slot in an index the site
    is already struggling to enter. follow keeps them in the link graph.
    """
    buckets = tag_index(docs)
    out_dir.mkdir(exist_ok=True)
    hubs = overflow = 0

    for tag, items in buckets.items():
        page = tag_pages.TAG_PAGES[tag]
        slug = page["slug"]
        tag_dir = out_dir / slug
        tag_dir.mkdir(exist_ok=True)
        pages = max(1, -(-len(items) // PER_TAG_PAGE))

        siblings = related_tags(tag, buckets)
        related = ""
        if siblings:
            links = "".join(
                f'<a class="tag-pill tag-pill-link" '
                f'href="../{esc(tag_pages.TAG_PAGES[s]["slug"])}/">{esc(s)}</a>'
                for s in siblings
            )
            related = ('\n    <section class="tag-related">\n'
                       f'      <h2 class="section-label">{esc(tag_pages.GROUPS[page["group"]])} נוספים</h2>\n'
                       f'      <div class="tags-list">{links}</div>\n'
                       '    </section>\n')

        for n in range(1, pages + 1):
            first = n == 1
            chunk = items[(n - 1) * PER_TAG_PAGE: n * PER_TAG_PAGE]
            name = "index.html" if first else f"page-{n}.html"
            url = f"{base}t/{slug}/" if first else f"{base}t/{slug}/page-{n}.html"

            prevnext = ""
            if n > 1:
                prev = "" if n == 2 else f"page-{n - 1}.html"
                prevnext += f'  <link rel="prev" href="{base}t/{slug}/{prev}">\n'
            if n < pages:
                prevnext += f'  <link rel="next" href="{base}t/{slug}/page-{n + 1}.html">\n'

            pager = ""
            if pages > 1:
                links = []
                if n > 1:
                    links.append(f'<a class="page-btn" href="{"./" if n == 2 else f"page-{n-1}.html"}">→ הקודם</a>')
                # First, last, a window around the current page, and jumps of ten
                # the whole way, so no page is more than a few clicks from any other.
                window = {1, 2, n - 1, n, n + 1, pages - 1, pages}
                window |= set(range(10, pages + 1, 10))
                for m in sorted(window & set(range(1, pages + 1))):
                    target = "./" if m == 1 else f"page-{m}.html"
                    active = " active" if m == n else ""
                    links.append(f'<a class="page-btn{active}" href="{target}">{m}</a>')
                if n < pages:
                    links.append(f'<a class="page-btn" href="page-{n + 1}.html">הבא ←</a>')
                pager = f'\n    <nav class="pagination" aria-label="דפים">{"".join(links)}</nav>\n'

            (tag_dir / name).write_text(TAG_PAGE.format(
                a11y_head=a11y_snippets.head("../../"),
                a11y_foot=a11y_snippets.foot("../../"),
                site=esc(SITE_NAME),
                title=esc(page["h1"] if first else f'{page["h1"]} — עמוד {n} מתוך {pages}'),
                description=esc(truncate(page["intro"], 155) if first
                                else f'{page["h1"]} — עמוד {n} מתוך {pages}.'),
                url=esc(url),
                base=esc(base),
                robots=("index, follow, max-image-preview:large, max-snippet:-1"
                        if first else "noindex, follow"),
                prevnext=prevnext,
                jsonld=render_tag_json_ld(tag, page, url, base, chunk) if first else "",
                crumb=esc(page["h1"] if first else f'{page["h1"]} · עמוד {n}'),
                group_label=esc(tag_pages.GROUPS[page["group"]]),
                h1=esc(page["h1"] if first else f'{page["h1"]} — עמוד {n}'),
                count=f"{len(items):,}",
                intro=(f'\n    <div class="tag-intro">\n      <p>{esc(page["intro"])}</p>\n    </div>\n'
                       if first else ""),
                list_label=("המסמכים" if pages == 1 else
                            f"המסמכים — עמוד {n} מתוך {pages}"),
                items="\n".join(render_doc_card(d, desc_limit=CARD_DESC) for d in chunk),
                pager=pager,
                related=related if first else "",
                pgp=PGP_URL,
                license=LICENSE_URL,
            ), encoding="utf-8")

            hubs += first
            overflow += not first

    return hubs, overflow


# ── sitemap.xml / robots.txt ──────────────────────────────────────────────────
LASTMOD_FILE = DOCS_DIR.parent / "lastmod.json"


def page_fingerprint(payload):
    """Short hash of everything that ends up visible on a page."""
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def write_english(docs):
    """The one field the browser fetches, in a file of its own.

    assets/doc-english.js asks for the English description on click. It used to
    read data/docs/<id>.json, which carries the whole record — description,
    tags, library, IIIF links, dates — every one of which is already in the
    HTML of that same page. Publishing it meant shipping each document twice.

    data/docs stays in the repository: prerender.py builds every page from it,
    and it is the fallback when the Princeton CSV cannot be fetched. It is the
    deploy that drops it, and this that takes its place — 57 MB become 11 MB.

    Written here rather than in build.py because build.py --html-only and the
    degraded CSV-less path both skip the step that writes data/docs, and a
    missing data/en is a reader clicking a button that answers nothing.
    """
    EN_DIR.mkdir(parents=True, exist_ok=True)
    fresh = 0
    for doc in docs:
        target = EN_DIR / f"{doc['id']}.json"
        body = json.dumps({"description": clean(doc.get("description"))},
                          ensure_ascii=False)
        if not target.exists() or target.read_text(encoding="utf-8") != body:
            target.write_text(body, encoding="utf-8")
            fresh += 1
    print(f"  ✓  data/en/  ({len(docs):,} files, {fresh:,} rewritten)")


def resolve_lastmod(docs, tag_slugs, buckets):
    """Real <lastmod> dates, by remembering when each page's content last changed.

    The sitemap used to stamp today's date on all 36,000 URLs on every build,
    which told Google that the entire Cairo Geniza changed this morning. An
    obviously automatic lastmod is one Google learns to ignore, and then the
    signal is worth nothing on the pages where it would actually have helped.

    So: hash what the page is made of, keep the hash and a date in
    data/lastmod.json, and only move the date when the hash moves. A document
    whose Hebrew description gets rewritten reports the day it was rewritten;
    one that has not changed since keeps its old date, which is the truth.

    The manifest has to be COMMITTED for the dates to survive — CI rebuilds it
    but never pushes it back. An uncommitted manifest degrades safely: pages
    look new rather than reporting a wrong old date, and the file self-corrects
    the next time it is committed. The rewrite workflow should include it.
    """
    stored = {}
    if LASTMOD_FILE.exists():
        try:
            stored = json.loads(LASTMOD_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("  !  data/lastmod.json unreadable — every page dates from today")

    today = date.today().isoformat()
    fresh, moved = {}, 0

    def stamp(key, payload):
        nonlocal moved
        sha = page_fingerprint(payload)
        was = stored.get(key)
        if was and was.get("sha") == sha:
            fresh[key] = was
        else:
            fresh[key] = {"sha": sha, "date": today}
            if was:
                moved += 1
        return fresh[key]["date"]

    dates = {}
    for doc in docs:
        # Only what a reader sees. prev/next/pos shift whenever a neighbouring
        # document is added, and that is not a change to this page's content.
        dates[f"d/{doc['id']}.html"] = stamp(f"d/{doc['id']}", {
            "shelfmark": doc.get("shelfmark"), "type": doc.get("type_he"),
            "lang": doc.get("lang_he"), "date": doc.get("date"),
            "origin": doc.get("origin"), "library": doc.get("library"),
            "he": doc.get("description_he"), "tags": sorted(doc.get("tags_he") or []),
            "iiif": (doc.get("iiif_urls") or [None])[0],
        })

    for tag in buckets:
        page = tag_pages.TAG_PAGES[tag]
        dates[f"t/{page['slug']}/"] = stamp(f"t/{page['slug']}", {
            "h1": page["h1"], "intro": page["intro"], "group": page["group"],
            # The listing changes when its top documents change, so the hub's
            # own date follows the documents it actually shows.
            "docs": [d["id"] for d in buckets[tag][:PER_TAG_PAGE]],
        })

    # Index and static pages: whatever they list, or the file itself.
    dates["t/"] = stamp("t/", sorted(
        (t, len(d)) for t, d in buckets.items()))
    dates["d/"] = stamp("d/", [d["id"] for d in docs])
    for name in ("about.html", "privacy/", "accessibility/"):
        path = ROOT / (name if name.endswith(".html") else name + "index.html")
        dates[name] = stamp(name, path.read_text(encoding="utf-8") if path.exists() else "")
    dates[""] = stamp("", {"docs": len(docs), "tags": len(buckets)})

    LASTMOD_FILE.write_text(
        json.dumps(fresh, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return dates, moved


def write_sitemap(docs, base, index_pages, tag_slugs=(), dates=None):
    dates = dates or {}
    today = date.today().isoformat()
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

    def add(path, priority, changefreq="monthly"):
        loc = base + path
        lastmod = dates.get(path, today)
        parts.append(
            f"  <url><loc>{html.escape(loc)}</loc><lastmod>{lastmod}</lastmod>"
            f"<changefreq>{changefreq}</changefreq>"
            f"<priority>{priority}</priority></url>"
        )

    add("", "1.0", "weekly")
    add("about.html", "0.8", "yearly")
    add("privacy/", "0.4", "yearly")
    add("accessibility/", "0.4", "yearly")
    add("d/", "0.9", "weekly")
    for n in range(2, index_pages + 1):
        # A paginated index page changes whenever the index it slices does.
        add(f"d/index-{n}.html", "0.5")

    # Tag hubs rank above individual documents: each one is a real page about a
    # subject, and each is the entry point for a query no shelfmark can answer.
    # Only page 1 goes in — the overflow pages are noindex by design.
    if tag_slugs:
        add("t/", "0.9", "monthly")
    for slug in tag_slugs:
        add(f"t/{slug}/", "0.8", "monthly")
    for doc in docs:
        add(f"d/{doc['id']}.html", "0.6", "yearly")

    parts.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(parts) + "\n", encoding="utf-8")
    return len(docs) + index_pages + 4 + (len(tag_slugs) + 1 if tag_slugs else 0)


ROBOTS = """# הגניזה הקהירית — Geniza Explorer
# All content is derived from the Princeton Geniza Project and is published
# under CC BY-NC 4.0: https://creativecommons.org/licenses/by-nc/4.0/
# Reuse, including by AI systems, must be non-commercial and must credit the
# Princeton Geniza Project.

User-agent: *
Allow: /

# fragment.html is only a redirect shim kept alive for old ?id= links; every
# document's real page lives under /d/.
Disallow: /fragment.html

# data/docs/ is one JSON file per document. Two reasons to keep it out:
# most of it duplicates the prerendered page, and it also holds the original
# English PGP description, which assets/doc-english.js fetches on click and
# which is deliberately not in any page's HTML. Blocking it here means that even
# if a crawler did trigger the fetch, it could not index the text.
# data/search.json and data/stats.json stay crawlable on purpose: Googlebot has
# to fetch them to render the gallery, and blocking them would make the home
# page look empty to it.
Disallow: /data/en/

Sitemap: {base}sitemap.xml
"""


def write_robots(base):
    (ROOT / "robots.txt").write_text(ROBOTS.format(base=base), encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────
def load_docs(limit=None):
    if not DOCS_DIR.exists():
        sys.exit(f"  ✗  {DOCS_DIR} not found — run build.py first.")
    files = sorted(DOCS_DIR.glob("*.json"), key=lambda p: int(p.stem)
                   if p.stem.isdigit() else 0)
    if limit:
        files = files[:limit]
    docs = []
    for path in files:
        with open(path, encoding="utf-8") as handle:
            docs.append(json.load(handle))
    docs.sort(key=lambda d: d.get("pos") or 0)
    return docs


def run(base=None, limit=None, docs=None, verbose=True):
    """Generate d/, sitemap.xml and robots.txt. Importable from build.py."""
    base = base or base_url()
    if not base.endswith("/"):
        base += "/"

    if verbose:
        print(f"  base URL: {base}")

    if docs is None:
        docs = load_docs(limit)
    if verbose:
        print(f"  {len(docs):,} documents loaded")

    OUT_DIR.mkdir(exist_ok=True)
    related_index = build_related_index(docs)
    for i, doc in enumerate(docs):
        (OUT_DIR / f"{doc['id']}.html").write_text(
            render_doc(doc, base, related_index), encoding="utf-8")
        if (i + 1) % 5000 == 0:
            print(f"  …  {i + 1:,}/{len(docs):,}")
    print(f"  ✓  d/*.html  ({len(docs):,} pages)")

    # ב-CI התיקייה נבנית מאפס ואין מה לגזום, אבל בבנייה מקומית חוזרת עמוד של
    # מסמך שפרינסטון מחקה שורד את המחיקה: הוא נעדר מה-sitemap ומן המפתח, ועדיין
    # נפתח בדפדפן. גוזמים רק d/<ספרות>.html, כך שדפי המפתח אינם בסכנה.
    if limit is None:
        live = {doc["id"] for doc in docs}
        gone = [p for p in OUT_DIR.glob("*.html")
                if p.stem.isdigit() and p.stem not in live]
        for p in gone:
            p.unlink()
        if gone:
            print(f"  ✓  {len(gone)} stale document page(s) removed from d/")

    index_pages = render_index_pages(docs, base, OUT_DIR)
    print(f"  ✓  d/index.html  ({index_pages} directory pages)")

    buckets = tag_index(docs)
    hubs, overflow = render_tag_pages(docs, base, TAG_DIR)
    render_tag_directory(buckets, base, TAG_DIR)
    print(f"  ✓  t/*/  ({hubs} tag hubs + {overflow:,} paginated pages, noindex)")
    tag_slugs = [tag_pages.TAG_PAGES[t]["slug"]
                 for t, _ in sorted(buckets.items(), key=lambda kv: -len(kv[1]))]

    dates, moved = resolve_lastmod(docs, tag_slugs, buckets)
    urls = write_sitemap(docs, base, index_pages, tag_slugs, dates)
    print(f"  ✓  sitemap.xml  ({urls:,} URLs, {moved:,} with a new lastmod)")

    write_robots(base)
    print("  ✓  robots.txt")

    # tag → hub slug, for the chips on the home page. Written here and not in
    # build.py because build.py is continue-on-error in CI: if the Princeton CSV
    # is unreachable it stops early, and the home page would then link chips to
    # a stale map. prerender.py always runs.
    slugs = {tag: page["slug"] for tag, page in tag_pages.TAG_PAGES.items()}
    (DOCS_DIR.parent / "tag_slugs.json").write_text(
        json.dumps(slugs, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    print(f"  ✓  data/tag_slugs.json  ({len(slugs)} tags)")

    write_english(docs)

    total = sum(p.stat().st_size for p in OUT_DIR.glob("*.html"))
    if verbose:
        print(f"  ✓  {total / 1048576:.0f} MB of static HTML in d/")
    return {"documents": len(docs), "index_pages": index_pages, "sitemap_urls": urls}


def main():
    parser = argparse.ArgumentParser(description="Prerender Geniza Explorer for crawlers")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--base-url", default=None,
                        help="Canonical site root; defaults to CNAME or GitHub Pages")
    args = parser.parse_args()

    print("\n── Prerender ─────────────────────────────────────────")
    run(base=args.base_url, limit=args.limit)
    print("── Done ──────────────────────────────────────────────\n")


if __name__ == "__main__":
    main()
