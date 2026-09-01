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
import html
import json
import pathlib
import re
import sys
from datetime import date

import a11y_snippets

ROOT = pathlib.Path(__file__).parent
DOCS_DIR = ROOT / "data" / "docs"
OUT_DIR = ROOT / "d"

DEFAULT_BASE_URL = "https://nadaval56.github.io/geniza-explorer/"

SITE_NAME = "הגניזה הקהירית"
SITE_TAGLINE = "חלון אל החיים היהודיים בימי הביניים"
PER_INDEX_PAGE = 250

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
    shelfmark = clean(doc.get("shelfmark")) or f"PGPID {doc['id']}"
    kind = clean(doc.get("type_he"))
    return f"{shelfmark} — {kind}" if kind else shelfmark


def doc_description(doc):
    """Best available prose, Hebrew first, English as a fallback."""
    return clean(doc.get("description_he")) or clean(doc.get("description"))


def summary_line(doc):
    """One-line factual summary for pages with no description at all."""
    bits = [clean(doc.get("type_he")), clean(doc.get("lang_he")),
            clean(doc.get("date")), clean(doc.get("library"))]
    return " · ".join(b for b in bits if b)


def meta_description(doc):
    text = doc_description(doc)
    if not text:
        text = summary_line(doc)
    shelfmark = clean(doc.get("shelfmark")) or f"PGPID {doc['id']}"
    return truncate(f"{shelfmark} — {text}" if text else shelfmark)


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


def render_tags(doc):
    tags = [clean(t) for t in (doc.get("tags_he") or doc.get("tags") or []) if clean(t)]
    if not tags:
        return ""
    pills = "".join(f'<span class="tag-pill">{esc(t)}</span>' for t in tags)
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
        "name": doc_title(doc),
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
    <a href="{root}" class="nav-home">← חזרה לגלריה</a>
    <span class="nav-breadcrumb" aria-current="page">{breadcrumb}</span>
  </nav>

  <article class="fragment-article" id="doc-main">

    <header class="fragment-header">
      <div class="fragment-badges">{badges}</div>
      <h1 class="fragment-shelfmark">{shelfmark}</h1>
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
{a11y_foot}
</body>
</html>
"""


def render_doc(doc, base):
    doc_id = doc["id"]
    url = f"{base}d/{doc_id}.html"
    title = doc_title(doc)
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
    <a href="../" class="nav-home">← חזרה לגלריה</a>
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
        for m in sorted({1, 2, n - 1, n, n + 1, pages - 1, pages} & set(range(1, pages + 1))):
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


# ── sitemap.xml / robots.txt ──────────────────────────────────────────────────
def write_sitemap(docs, base, index_pages):
    today = date.today().isoformat()
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

    def add(loc, priority, changefreq="monthly"):
        parts.append(
            f"  <url><loc>{html.escape(loc)}</loc><lastmod>{today}</lastmod>"
            f"<changefreq>{changefreq}</changefreq>"
            f"<priority>{priority}</priority></url>"
        )

    add(base, "1.0", "weekly")
    add(base + "about.html", "0.8", "yearly")
    add(base + "privacy/", "0.4", "yearly")
    add(base + "accessibility/", "0.4", "yearly")
    add(base + "d/", "0.9", "weekly")
    for n in range(2, index_pages + 1):
        add(f"{base}d/index-{n}.html", "0.5")
    for doc in docs:
        add(f"{base}d/{doc['id']}.html", "0.6", "yearly")

    parts.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(parts) + "\n", encoding="utf-8")
    return len(docs) + index_pages + 4


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
Disallow: /data/docs/

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
    for i, doc in enumerate(docs):
        (OUT_DIR / f"{doc['id']}.html").write_text(render_doc(doc, base), encoding="utf-8")
        if (i + 1) % 5000 == 0:
            print(f"  …  {i + 1:,}/{len(docs):,}")
    print(f"  ✓  d/*.html  ({len(docs):,} pages)")

    index_pages = render_index_pages(docs, base, OUT_DIR)
    print(f"  ✓  d/index.html  ({index_pages} directory pages)")

    urls = write_sitemap(docs, base, index_pages)
    print(f"  ✓  sitemap.xml  ({urls:,} URLs)")

    write_robots(base)
    print("  ✓  robots.txt")

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
