/* Geniza Explorer — Fragment detail page */
(function () {
  'use strict';

  const META_FIELDS = [
    { key: 'type_he',        label: 'סוג מסמך' },
    { key: 'lang_he',        label: 'שפה ראשית' },
    { key: 'lang2_he',       label: 'שפת משנה' },
    { key: 'origin',         label: 'מקום מוצא' },
    { key: 'destination',    label: 'יעד' },
    { key: 'date',           label: 'תאריך' },
    { key: 'date_original',  label: 'תאריך מקורי' },
    { key: 'date_inferred',  label: 'תאריך משוער' },
    { key: 'date_rationale', label: 'בסיס לתיארוך' },
    { key: 'library',        label: 'ספרייה' },
    { key: 'collection',     label: 'אוסף' },
    { key: 'region',         label: 'אזור' },
    { key: 'mentioned',      label: 'אזכורים' },
    { key: 'lang_note',      label: 'הערת שפה' },
    { key: 'multifragment',  label: 'רב-קטע' },
  ];

  const TYPE_BADGE = {
    'מכתב':            'badge-type-letter',
    'מסמך משפטי':      'badge-type-legal',
    'טקסט ספרותי':     'badge-type-lit',
    'טקסט דתי':        'badge-type-rel',
    'טקסט פרא-ספרותי': 'badge-type-para',
  };

  // DOM refs
  const loadingEl     = document.getElementById('loading-state');
  const article       = document.getElementById('fragment-article');
  const pageTitle     = document.getElementById('page-title');
  const breadcrumb    = document.getElementById('nav-breadcrumb');
  const badgesEl      = document.getElementById('fragment-badges');
  const shelfmarkEl   = document.getElementById('fragment-shelfmark');
  const libraryEl     = document.getElementById('fragment-library');
  const metaList      = document.getElementById('meta-list');
  const imgEl         = document.getElementById('fragment-img');
  const imgPlaceholder= document.getElementById('image-placeholder');
  const imgCaption    = document.getElementById('image-caption');
  const imageLinks    = document.getElementById('image-links');
  const descBlock     = document.getElementById('description-block');
  const descText      = document.getElementById('description-text');
  const tagsBlock     = document.getElementById('tags-block');
  const tagsList      = document.getElementById('tags-list');
  const princetonLink = document.getElementById('princeton-link');
  const fragNav       = document.getElementById('fragment-nav');

  function esc(s) {
    return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')
                  .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function getQueryId() {
    return new URLSearchParams(window.location.search).get('id') || '';
  }

  // ── Convert IIIF manifest URL → human viewer URL ──────────────────────────────
  function iiifToViewer(url) {
    if (!url) return null;
    // Cambridge Digital Library: /iiif/MS-TS-... → /view/MS-TS-...
    if (url.includes('cudl.lib.cam.ac.uk/iiif/')) {
      return url.replace('cudl.lib.cam.ac.uk/iiif/', 'cudl.lib.cam.ac.uk/view/');
    }
    // JTS Figgy: .../concern/scanned_resources/{uuid}/manifest → .../catalog/{uuid}
    const figgy = url.match(/figgy\.princeton\.edu\/concern\/scanned_resources\/([^/]+)\/manifest/);
    if (figgy) return `https://figgy.princeton.edu/catalog/${figgy[1]}`;
    // Bodleian
    if (url.includes('iiif.bodleian.ox.ac.uk/iiif/manifest/')) {
      const bod = url.match(/manifest\/([^/]+)$/);
      if (bod) return `https://digital.bodleian.ox.ac.uk/objects/${bod[1]}/`;
    }
    // NLI (National Library of Israel)
    if (url.includes('nli.org.il') || url.includes('rosetta.nli')) return url;
    // Generic fallback: return null so we skip showing the IIIF manifest directly
    return null;
  }

  // ── License text for known institutions ───────────────────────────────────────
  function licenseText(library) {
    if (!library) return '';
    const l = library.toLowerCase();
    if (l.includes('jtsl') || l.includes('jewish theological') || l.includes('jts') || l.includes('בית המדרש')) {
      return 'CC Zero / נחלת הכלל — Jewish Theological Seminary Library';
    }
    if (l.includes('cambridge') || l.includes('cul') || l.includes('קיימברידג')) {
      return 'רישיון פתוח — Cambridge University Library';
    }
    if (l.includes('bodleian') || l.includes('בודליאן')) {
      return 'רישיון פתוח — Bodleian Libraries, Oxford';
    }
    return '';
  }

  // ── IIIF thumbnail loader ─────────────────────────────────────────────────────
  async function loadIIIFThumbnail(manifestUrl) {
    try {
      const resp = await fetch(manifestUrl, { mode: 'cors', cache: 'force-cache' });
      if (!resp.ok) return null;
      const manifest = await resp.json();
      const canvases = manifest?.sequences?.[0]?.canvases;
      if (!canvases?.length) return null;
      const canvas = canvases[0];

      // Try manifest thumbnail
      const mThumb = manifest.thumbnail?.['@id'] || manifest.thumbnail;
      if (typeof mThumb === 'string' && mThumb.startsWith('http')) return { url: mThumb, label: canvas.label||'' };

      // Try canvas thumbnail
      const cThumb = canvas.thumbnail?.['@id'] || canvas.thumbnail;
      if (typeof cThumb === 'string' && cThumb.startsWith('http')) return { url: cThumb, label: canvas.label||'' };

      // Build from image service
      const resource = canvas.images?.[0]?.resource;
      const svcId = resource?.service?.['@id'] || resource?.service?.id;
      if (svcId) return { url: `${svcId}/full/500,/0/default.jpg`, label: canvas.label||'' };

      // Last resort: resource @id, resize
      const rId = resource?.['@id'];
      if (rId) return { url: rId.replace('/full/full/','/full/500,/').replace('/full/max/','/full/500,/'), label: canvas.label||'' };
      return null;
    } catch { return null; }
  }

  // ── Image + links setup ───────────────────────────────────────────────────────
  async function setupImage(doc) {
    if (!doc.iiif_urls?.length && !doc.fragment_urls?.length) return;

    // Load thumbnail from first IIIF manifest
    if (doc.iiif_urls.length) {
      const thumb = await loadIIIFThumbnail(doc.iiif_urls[0]);
      if (thumb) {
        imgEl.src   = thumb.url;
        imgEl.alt   = doc.shelfmark || 'תמונת המסמך';
        imgEl.hidden = false;
        imgPlaceholder.hidden = true;

        // Click → open viewer (not manifest)
        const viewUrl = doc.fragment_urls?.[0] || iiifToViewer(doc.iiif_urls[0]);
        if (viewUrl) {
          imgEl.style.cursor = 'pointer';
          imgEl.addEventListener('click', () => window.open(viewUrl, '_blank', 'noopener'));
        }

        // License
        const lic = licenseText(doc.library || doc.library_raw || '');
        imgCaption.textContent = lic || (thumb.label || '');
        imgCaption.hidden = false;
      }
    }

    // View links — prefer fragment_urls (actual viewer), fall back to converted iiif
    const viewerLinks = [];
    (doc.fragment_urls || []).forEach((u, i) => {
      viewerLinks.push({ url: u, label: `צפייה בספרייה הדיגיטלית${doc.fragment_urls.length > 1 ? ' ' + (i+1) : ''}` });
    });
    if (!viewerLinks.length) {
      (doc.iiif_urls || []).forEach((u, i) => {
        const v = iiifToViewer(u);
        if (v) viewerLinks.push({ url: v, label: `צפייה בספרייה הדיגיטלית${doc.iiif_urls.length > 1 ? ' ' + (i+1) : ''}` });
      });
    }

    viewerLinks.forEach(({ url, label }) => {
      const a = document.createElement('a');
      a.href = url; a.target = '_blank'; a.rel = 'noopener';
      a.className = 'image-link';
      a.innerHTML = `<span class="image-link-icon">🔗</span><span>${label}</span>`;
      imageLinks.appendChild(a);
    });
  }

  // ── Render document ───────────────────────────────────────────────────────────
  function renderDoc(doc) {
    const title = doc.shelfmark || `PGPID ${doc.id}`;
    pageTitle.textContent = `${title} — גניזת קהיר`;
    document.title = pageTitle.textContent;
    breadcrumb.textContent = title;
    shelfmarkEl.textContent = title;

    const libParts = [doc.library, doc.collection].filter(Boolean);
    libraryEl.textContent = libParts.join(' · ') || '';

    // Badges
    const cls = TYPE_BADGE[doc.type_he] || 'badge-type-other';
    let bHTML = `<span class="badge ${cls}">${esc(doc.type_he||'לא מסווג')}</span>`;
    if (doc.lang_he)           bHTML += `<span class="badge badge-lang">${esc(doc.lang_he)}</span>`;
    if (doc.has_transcription) bHTML += `<span class="badge badge-type-rel">📝 תמלול</span>`;
    if (doc.has_translation)   bHTML += `<span class="badge badge-type-letter">🌐 תרגום</span>`;
    badgesEl.innerHTML = bHTML;

    // Meta list
    let mHTML = '';
    META_FIELDS.forEach(({ key, label }) => {
      const val = doc[key];
      if (!val) return;
      if (key === 'multifragment' && !['true','True','1'].includes(String(val))) return;
      mHTML += `<dt>${esc(label)}</dt><dd>${esc(String(val))}</dd>`;
    });
    metaList.innerHTML = mHTML;

    // Description (English — labelled)
    if (doc.description) {
      descText.innerHTML = `<span class="desc-lang-note">תיאור (באנגלית):</span> ${esc(doc.description)}`;
      descBlock.hidden = false;
    }

    // Tags
    if (doc.tags?.length) {
      tagsList.innerHTML = doc.tags.map(t=>`<span class="tag-pill">${esc(t)}</span>`).join('');
      tagsBlock.hidden = false;
    }

    if (doc.princeton_url) princetonLink.href = doc.princeton_url;

    // Prev / Next
    let navHTML = doc.prev
      ? `<a href="fragment.html?id=${esc(doc.prev)}" class="frag-nav-btn">→ הקודם</a>`
      : '<span></span>';
    navHTML += `<span class="frag-nav-label">${(doc.pos||'').toLocaleString('he-IL')} מתוך ${(doc.total||'').toLocaleString('he-IL')}</span>`;
    navHTML += doc.next
      ? `<a href="fragment.html?id=${esc(doc.next)}" class="frag-nav-btn">הבא ←</a>`
      : '<span></span>';
    fragNav.innerHTML = navHTML;

    loadingEl.hidden = true;
    article.hidden = false;
  }

  // ── Boot ──────────────────────────────────────────────────────────────────────
  function init() {
    const id = getQueryId();
    if (!id) {
      loadingEl.innerHTML = `<p style="color:var(--text-3)">לא צוין מזהה מסמך.</p>
        <a href="index.html" style="color:var(--gold)">← חזרה לגלריה</a>`;
      return;
    }
    fetch(`data/docs/${encodeURIComponent(id)}.json`)
      .then(r => { if(!r.ok) throw new Error(r.status); return r.json(); })
      .then(doc => { renderDoc(doc); setupImage(doc); })
      .catch(() => {
        loadingEl.innerHTML = `<p style="color:var(--text-3);margin-bottom:.5rem">המסמך לא נמצא.</p>
          <a href="index.html" style="color:var(--gold)">← חזרה לגלריה</a>`;
      });
  }

  document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', init)
    : init();
})();
