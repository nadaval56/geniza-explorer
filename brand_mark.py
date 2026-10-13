#!/usr/bin/env python3
"""
Geniza Explorer — the site mark: a pointed arch standing on a threshold.

The arch is the Ben Ezra synagogue, where the Geniza was kept, and it is also
the "חלון" of the subtitle. A smaller arch inside it is the doorway. Two
strokes and a line, no fill: it has to read at 16px in a browser tab.

The geometry lives here once, and everything else is drawn from it:

    SVG                  the inline mark, over the home-page title (build.py)
                         and in the masthead of every inner page (prerender.py)
    make_brand_assets.py the favicon set and the arch on assets/og-image.png

The three hand-written pages (about.html, privacy/, accessibility/) carry a
pasted copy of SVG — after changing the geometry, paste `python3 brand_mark.py`
into them and re-run make_brand_assets.py.

The inline colours are CSS variables (--gold for the arch, --text-2 for the
doorway), so the accessibility menu's display modes apply to the mark too.
It is decorative — the site name sits right beside it — so it is aria-hidden.
"""

# Paths in a 32×32 box. Each is a start point followed by segments:
# ("L", end) or ("C", ctrl1, ctrl2, end).
ARCH = [(9, 27), ("L", (9, 15.5)),
        ("C", (9, 10), (12.5, 6), (16, 4)),
        ("C", (19.5, 6), (23, 10), (23, 15.5)),
        ("L", (23, 27))]
THRESHOLD = [(6, 27), ("L", (26, 27))]
DOORWAY = [(13, 27), ("L", (13, 18.5)),
           ("C", (13, 16.5), (14.3, 14.9), (16, 14)),
           ("C", (17.7, 14.9), (19, 16.5), (19, 18.5)),
           ("L", (19, 27))]

OUTER = (ARCH, THRESHOLD)   # drawn in the accent colour
INNER = (DOORWAY,)          # drawn in the ink colour


def path_d(path):
    """SVG path data for one of the paths above."""
    fmt = lambda p: f"{p[0]:g} {p[1]:g}"
    out = [f"M{fmt(path[0])}"]
    for seg in path[1:]:
        out.append(seg[0] + " ".join(fmt(p) for p in seg[1:]))
    return "".join(out)


def polyline(path, steps=24):
    """The same path flattened into points, for raster drawing (Pillow has
    no Bézier curves)."""
    pts = [path[0]]
    for seg in path[1:]:
        if seg[0] == "L":
            pts.append(seg[1])
            continue
        p0, (c1, c2, p3) = pts[-1], seg[1:]
        for i in range(1, steps + 1):
            t = i / steps
            u = 1 - t
            pts.append(tuple(u**3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t**3 * d
                             for a, b, c, d in zip(p0, c1, c2, p3)))
    return pts


# pathLength="1" lets the CSS draw each stroke in with a dash of length 1,
# whatever its real length (style.css, "הנפשת הסמלים").
SVG = (
    '<svg class="brand-mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false">'
    + "".join(f'<path class="brand-mark-line" pathLength="1" d="{path_d(p)}"/>' for p in OUTER)
    + "".join(f'<path class="brand-mark-ink" pathLength="1" d="{path_d(p)}"/>' for p in INNER)
    + "</svg>"
)

# ── The KPI icons on the home page, in the mark's line style ─────────────────
# Same stroke classes as SVG, so they follow the display modes too; the one
# filled surface uses --bg-2, which a11y.css redefines for each mode. The
# extra classes (layer-*, hill, sun, ray, glass) are only hooks for the
# animations in style.css (replayed by assets/brand-anim.js).
#   ICON_DOCS    three stacked leaves: the documents, piled up over centuries
#   ICON_IMAGES  a frame with a hill and a sun: the documents with a photograph
#   ICON_DYK     a bulb with its filament and rays: "הידעת?"
def _icon(body):
    return f'<svg class="brand-mark kpi-svg" viewBox="0 0 32 32" focusable="false">{body}</svg>'


ICON_DOCS = _icon(
    '<path class="brand-mark-line layer-1" d="M6 21l10 5 10-5"/>'
    '<path class="brand-mark-line layer-2" d="M6 16l10 5 10-5" opacity=".7"/>'
    '<path class="brand-mark-line brand-mark-fill layer-3" d="M6 11l10-5 10 5-10 5z"/>'
)
ICON_IMAGES = _icon(
    '<rect class="brand-mark-line brand-mark-fill" x="5" y="7" width="22" height="18" rx="2"/>'
    '<path class="brand-mark-ink hill" pathLength="1" d="M8.5 21.5l5.5-6.5 4 4.5 2.5-2.5 3 4.5"/>'
    '<circle class="brand-mark-line sun" cx="21" cy="12.2" r="1.8"/>'
)
ICON_DYK = _icon(
    '<path class="brand-mark-line brand-mark-fill glass" d="M12 21v-2.6C9.6 16.8 8.2 14.6 8.2 12'
    'a7.8 7.8 0 0 1 15.6 0c0 2.6-1.4 4.8-3.8 6.4V21z"/>'
    '<path class="brand-mark-ink" d="M14 18.5v-2.8l2-2.4 2 2.4v2.8"/>'
    '<path class="brand-mark-line" d="M12.5 24h7M14 27h4"/>'
    '<path class="brand-mark-line ray" d="M16 .9v1.6"/>'
    '<path class="brand-mark-line ray" d="M6.3 4.3l1.2 1.2M25.7 4.3l-1.2 1.2"/>'
    '<path class="brand-mark-line ray" d="M2.4 12h1.7M29.6 12h-1.7"/>'
)

if __name__ == "__main__":
    print(SVG)
