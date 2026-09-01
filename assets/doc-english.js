/* Geniza Explorer — the original English description, fetched on request.
 *
 * Every document page carries the Hebrew description in its HTML. The English
 * original from the Princeton Geniza Project does not, and that is deliberate:
 * it is a verbatim copy of geniza.princeton.edu, and because the median Hebrew
 * description runs about 108 characters it used to be the bulk of the text on
 * most pages. A page that is mostly a word-for-word copy of a far more
 * authoritative source is one Google indexes at the source and drops here.
 *
 * Why a click and not an automatic fetch on load: Googlebot renders JavaScript,
 * so anything fetched automatically ends up in the rendered DOM and is indexed
 * anyway. It does not click buttons. Loading on demand is what actually keeps
 * the duplicate text out of the index, and it costs the reader one click. This
 * is the same page for everyone — crawler included — so it is disclosure on
 * demand, not cloaking.
 *
 * Without JavaScript the button simply does nothing beyond what the markup
 * says, and the "צפייה ב-Princeton Geniza Project" link on the page still
 * leads to the English text at its source.
 */
(function () {
  'use strict';

  const btn = document.querySelector('.english-toggle');
  if (!btn) return;
  const panel = document.getElementById(btn.getAttribute('aria-controls'));
  const docId = btn.dataset.doc;
  if (!panel || !docId) return;

  const LABEL_SHOW = btn.textContent;
  const LABEL_HIDE = 'הסתר את התיאור באנגלית';
  let loaded = false;
  let inFlight = false;

  const message = (text) => {
    const p = document.createElement('p');
    p.className = 'english-note';
    p.textContent = text;
    panel.replaceChildren(p);
  };

  const render = (text) => {
    const note = document.createElement('span');
    note.className = 'desc-lang-note';
    note.textContent = 'Princeton Geniza Project description';

    const body = document.createElement('p');
    body.className = 'description-text';
    body.lang = 'en';
    body.dir = 'ltr';
    body.textContent = text;

    panel.replaceChildren(note, body);
    loaded = true;
  };

  const load = () => {
    if (loaded || inFlight) return;
    inFlight = true;
    message('טוען…');

    fetch('../data/docs/' + encodeURIComponent(docId) + '.json', { cache: 'force-cache' })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        const text = typeof d?.description === 'string' ? d.description.replace(/\s+/g, ' ').trim() : '';
        if (text) {
          render(text);
        } else {
          message('אין תיאור אנגלי זמין למסמך הזה.');
        }
      })
      .catch(() => {
        message('לא ניתן היה לטעון את התיאור באנגלית. הוא זמין באתר Princeton Geniza Project, בקישור שבעמוד.');
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
