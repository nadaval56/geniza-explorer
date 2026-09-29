/* Geniza Explorer — the PGP transcription, fetched on request.
 *
 * Same reasoning as doc-english.js, and for the same reason: a transcription is
 * a verbatim copy of geniza.princeton.edu. Prerendering 7,179 of them into d/
 * would make those pages mostly a word-for-word duplicate of a far more
 * authoritative source, which is what the English description was moved out of
 * the HTML to avoid. Googlebot renders JavaScript but does not click, so a
 * click is what actually keeps the duplicate text out of the index. The page is
 * the same for everyone, crawler included: disclosure on demand, not cloaking.
 *
 * The transcriptions themselves are Princeton Geniza Project content under
 * CC BY-NC 4.0, and the editor's name and citation ride along in the data file
 * so the credit is never separated from the text.
 *
 * Without JavaScript the button does nothing beyond what the markup says, and
 * the "צפייה ב-Princeton Geniza Project" link still leads to the text at its
 * source.
 */
(function () {
  'use strict';

  /* סימני ניקוד ערביים (שדה, פתחה, תנוין) על אותיות עבריות: אין גופן שמכסה
     את הצירוף, והטלפון מצייר ריבועים ריקים. כל סימן הופך לנקודה העברית שעושה
     את אותה עבודה — שדה לדגש — ותנוין, שאין לו מקבילה, יורד. אותו כלל בדיוק
     כמו hebrew_marks.py בבנייה; שינוי כאן מחייב שינוי שם. */
  const HEB_MAP = { '\u0651': '\u05BC', '\u064E': '\u05B7', '\u0650': '\u05B4',
    '\u064F': '\u05BB', '\u0652': '\u05B0', '\u064B': '', '\u064C': '', '\u064D': '' };
  function hebraize(s) {
    if (!/[\u064B-\u0652]/.test(s)) return s;
    return s.replace(/[\u05D0-\u05EA][\u0591-\u05C7\u064B-\u0652]+/g, (c) => {
      if (!/[\u064B-\u0652]/.test(c)) return c;
      const out = [];
      for (const ch of c.slice(1)) {
        const m = ch in HEB_MAP ? HEB_MAP[ch] : ch;
        if (m && !out.includes(m)) out.push(m);
      }
      return c[0] + out.join('');
    });
  }

  const btn = document.querySelector('.transcription-toggle');
  if (!btn) return;
  const panel = document.getElementById(btn.getAttribute('aria-controls'));
  const docId = btn.dataset.doc;
  if (!panel || !docId) return;

  const LABEL_SHOW = btn.textContent;
  const LABEL_HIDE = 'הסתר את התעתיק';
  let loaded = false;
  let inFlight = false;

  const message = (text) => {
    const p = document.createElement('p');
    p.className = 'transcription-note';
    p.textContent = text;
    panel.replaceChildren(p);
  };

  const render = (texts) => {
    const parts = [];
    texts.forEach((t) => {
      const block = document.createElement('div');
      block.className = 'transcription-item';

      const head = document.createElement('p');
      head.className = 'transcription-credit';
      head.textContent = `${t.label} · `;
      /* הציטוט לטיני בתוך פסקה עברית, ובלי בידוד הנקודה שבסופו קופצת לתחילת
         השורה. bdi עם dir=ltr מיישב את הפיסוק בתוך הציטוט עצמו. */
      const cite = document.createElement('bdi');
      cite.dir = 'ltr';
      cite.textContent = t.citation || 'Princeton Geniza Project';
      head.appendChild(cite);
      block.appendChild(head);

      const body = document.createElement('div');
      body.className = 'transcription-body';
      /* ה-HTML כאן עבר סינון ב-import_transcriptions.py: רק תגיות מבנה
         ומאפייני dir/lang/class/data-canvas שרדו, בלי script, style או on*. */
      body.innerHTML = hebraize(t.html);
      /* כותרות הקטעים של PGP ("Verso.", "Right margin, perpendicular lines.")
         כתובות כמעט תמיד באנגלית, ובתוך תעתיק מימין לשמאל הנקודה שבסופן
         קפצה להתחלה. dir=auto נותן לכל כותרת את הכיוון של הטקסט שבה. */
      body.querySelectorAll('h2, h3').forEach((h) => { h.dir = 'auto'; });
      /* 661 מהתרגומים הם לעברית (רובם של משה גיל), לא לאנגלית. הכיוון נגזר
         משפת הטקסט עצמו; בלי זה התרגום העברי הוצג משמאל לימין. */
      if (t.kind === 'translation') {
        const m = /lang="([^"]+)"/.exec(t.html);
        const lang = m ? m[1].toLowerCase() : 'en';
        body.lang = lang;
        body.dir = lang === 'he' ? 'rtl' : 'ltr';
      }
      block.appendChild(body);
      parts.push(block);
    });
    panel.replaceChildren(...parts);
    loaded = true;
  };

  const load = () => {
    if (loaded || inFlight) return;
    inFlight = true;
    message('טוען…');

    fetch('../data/transcriptions/' + encodeURIComponent(docId) + '.json', { cache: 'force-cache' })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        const texts = Array.isArray(d && d.texts) ? d.texts.filter((t) => t && t.html) : [];
        if (texts.length) {
          render(texts);
        } else {
          message('אין תעתיק זמין למסמך הזה.');
        }
      })
      .catch(() => {
        message('לא ניתן היה לטעון את התעתיק. הוא זמין באתר Princeton Geniza Project, בקישור שבעמוד.');
      })
      .finally(() => { inFlight = false; });
  };

  btn.addEventListener('click', () => {
    const open = btn.getAttribute('aria-expanded') === 'true';
    btn.setAttribute('aria-expanded', String(!open));
    btn.textContent = open ? LABEL_SHOW : LABEL_HIDE;
    panel.hidden = open;
    if (!open) load();
  });
})();
