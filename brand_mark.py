#!/usr/bin/env python3
"""
Geniza Explorer — the site mark: a torn fragment with its left side missing.

A piece of parchment with a triangle torn out of its left edge, and the lines
of writing stopping at the tear — the text ran on into the part that was lost,
which is what nearly every document in the Geniza looks like.

It replaced the ✦ ornament in two places: over the title on the home page
(build.py, .header-ornament) and in the small masthead at the top of every
inner page (prerender.py and the three hand-written pages, .nav-brand). The
hand-written pages carry a pasted copy of SVG — after changing it, paste
`python3 brand_mark.py` into about.html, privacy/ and accessibility/.

The colours are CSS variables, not fixed values, so the mark follows the
accessibility menu's display modes: a11y.css redefines --parchment, --gold and
--text-2 for high contrast and inverted contrast.

It is decorative — the site name sits right beside it — so it is aria-hidden.
"""

# ה-path מקיף את הקלף עם כיס משולש בצד שמאל, שקודקודו כמעט במרכז (16,15.4).
# השורות מיושרות לימין (x=22.5) ונעצרות בקו הקרע.
SVG = (
    '<svg class="brand-mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false">'
    '<path class="brand-mark-leaf" d="M6 4.5L10 5L13 3.5L17 4.5L20 3.5L24 4L25.5 7L24.5 10'
    'L26 13L24.8 16L26 19.5L25.2 22.5L26.2 27L22.2 27.8L19.2 26.8L16.2 28L12.7 27.2L9.7 28'
    'L6.7 27.5L6.2 24L6.6 21L8.5 20.2L10 19.4L11.4 18.4L12.6 17.6L14 16.4L16 15.4L14 14.4'
    'L12.8 13.3L11.2 12.6L9.8 11.4L8 10.6L6 9.8L5 7z"/>'
    '<path class="brand-mark-ink" d="M22.5 8.5H10M22.5 12H13.2M22.5 15.5H17.6M22.5 19H13.6'
    'M22.5 22.5H10M22.5 25.5H12"/>'
    '</svg>'
)

if __name__ == "__main__":
    print(SVG)
