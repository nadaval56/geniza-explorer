#!/usr/bin/env python3
"""
Geniza Explorer — the thin "עוד אתרים שלי" strip at the bottom of every footer.

The same strip runs on the owner's other sites (dronexam.co.il carries the
original, in RATA). Here the Geniza entry is swapped for a link back to it.

Links only: nothing is loaded from these sites — no favicon, no script — so the
privacy policy's "no third-party code" still holds.

    nav(root)   goes inside <footer class="site-footer">, as its last child

The list is written twice. The second copy exists only so that the slow scroll
in assets/sister.js can loop without a seam; it is aria-hidden and taken out of
the tab order, and CSS hides it altogether under reduced motion.

The three hand-written pages (about.html, privacy/, accessibility/) carry a
pasted copy of this output. After changing SITES, regenerate them with:

    python3 sister_sites.py            # prints nav("") for about.html
    python3 sister_sites.py ../        # for privacy/ and accessibility/
"""

import sys
from html import escape

# (emoji, url, linked text, trailing unlinked text)
# "מייקינג · יצירה טכנולוגית" is the one entry where only the name is a link —
# the same split as on the other sites.
SITES = [
    ("🛠️", "https://making-il.co.il/", "מייקינג", " · יצירה טכנולוגית"),
    ("💶", "https://banknote.co.il/", "Banknote · שטרות ומטבעות", ""),
    ("🛩️", "https://dronexam.co.il/", 'לעוף לשמיים · מבחן רת"א לרחפנים', ""),
    ("🌱", "https://holisticcenter.co.il/", "מעט צרי · רפואה משלימה", ""),
    ("🛸", "https://pursue.co.il/", 'PURSUE · ארכיון עב"מים', ""),
    ("📅", "https://heb-cal.co.il/", "לוח עברי", ""),
]


def _items(clone: bool) -> str:
    tab = ' tabindex="-1"' if clone else ""
    out = []
    for emoji, url, text, tail in SITES:
        icon = f'<span aria-hidden="true">{emoji}</span>'
        if tail:
            out.append(f'        <span class="sister-item">{icon} '
                       f'<a href="{escape(url)}" rel="noopener"{tab}>{escape(text)}</a>'
                       f'{escape(tail)}</span>')
        else:
            out.append(f'        <a href="{escape(url)}" rel="noopener"{tab}>'
                       f'{icon} {escape(text)}</a>')
    return "\n".join(out)


def nav(root: str = "", version: str = "") -> str:
    v = f"?v={version}" if version else ""
    return f"""    <nav class="sister" aria-label="האתרים הנוספים שלי">
      <span class="sister-lbl">עוד אתרים שלי</span>
      <div class="sister-view">
        <div class="sister-track">
      <div class="sister-set">
{_items(False)}
      </div>
      <div class="sister-set sister-clone" aria-hidden="true">
{_items(True)}
      </div>
        </div>
      </div>
    </nav>
    <script src="{root}assets/sister.js{v}" defer></script>"""


if __name__ == "__main__":
    print(nav(sys.argv[1] if len(sys.argv) > 1 else ""))
