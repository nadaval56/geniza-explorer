/* Geniza Explorer — Fragment detail page */
(function () {
  'use strict';

  // ── Hebrew labels ─────────────────────────────────────────────────────────────
  const META_FIELDS = [
    { key: 'shelfmark',      label: 'מספר ארכיון' },
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
    'מכתב':             'badge-type-letter',
    'מסמך משפטי':       'badge-type-legal',
    'טקסט ספרותי':      'badge-type-lit',
    'טקסט דתי':         'badge-type-rel',
    'טקסט פרא-ספרותי':  'badge-type-para',
  };

  // ── DOM refs ──────────────────────────────────────────────────────────────────
  const loadingEl    = document.getElementById('loading-state');
  const article      = document.getElementById('fragment-article');
  const pageTitle    = document.getElementById('page-title');
  const breadcrumb   = document.getElementById('nav-breadcrumb');
  const badgesEl     = document.getElementById('fragment-badges');
  const shelfmarkEl  = document.getElementById('fragment-shelfmark');
  const libraryEl    = document.getElementById('fragment-library');
  const metaList     = document.getElementById('meta-list');
  const imageFrame   = document.getElementById('image-frame');
  const imgEl        = document.getElementById('fragment-img');
  const imgPlaceholder = document.getElementById('image-placeholder');
  const imgCaption   = document.getElementById('image-caption');
  const imageLinks   = document.getElementById('image-links');
  const descBlock    = document.getElementById('description-block');
  const descText     = document.getElementById('description-text');
  const tagsBlock    = document.getElementById('tags-block');
  const tagsList     = document.getElementById('tags-list');
  const princetonLink = document.getElementById('princeton-link');
  const fragNav      = document.getElementById('fragment-nav');

  // ── Helpers ───────────────────────────────────────────────────────────────────
  function esc(str) {
    return (str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function getQueryId() {
    const params = new URLSearchParams(window.location.search);
    return params.get('id') || '';
  }

  // ── IIIF image loader ─────────────────────────────────────────────────────────
  // Tries to fetch the IIIF manifest and extract a thumbnail.
  // Cambridge IIIF: manifest.sequences[0].canvases[0].images[0].resource.service["@id"]
  // → thumbnail: {service}/full/500,/0/default.jpg
  async function loadIIIFThumbnail(manifestUrl) {
    try {
      const resp = await fetch(manifestUrl, { mode: 'cors', cache: 'force-cache' });
      if (!resp.ok) return null;
      const manifest = await resp.json();

      // IIIF Presentation API 2.x
      const canvases = manifest?.sequences?.[0]?.canvases;
      if (!canvases?.length) return null;

      const canvas = canvases[0];

      // Prefer manifest-level thumbnail
      const manifestThumb = manifest.thumbnail;
      if (manifestThumb) {
        const thumbId = manifestThumb['@id'] || manifestThumb;
        if (typeof thumbId === 'string' && thumbId.startsWith('http')) {
          return { url: thumbId, label: canvas.label || '' };
        }
      }

      // Try canvas thumbnail
      const canvasThumb = canvas.thumbnail;
      if (canvasThumb) {
        const thumbId = canvasThumb['@id'] || canvasThumb;
        if (typeof thumbId === 'string' && thumbId.startsWith('http')) {
          return { url: thumbId, label: canvas.label || '' };
        }
      }

      // Construct from image service
      const images = canvas.images;
      if (!images?.length) return null;
      const resource = images[0].resource;
      const serviceId = resource?.service?.['@id'] || resource?.service?.id;
      if (serviceId) {
        return {
          url: `${serviceId}/full/500,/0/default.jpg`,
          label: canvas.label || '',
        };
      }

      // Last resort: use the resource @id directly
      const resourceId = resource?.['@id'];
      if (resourceId) {
        // Replace /full/full/ with /full/500,/
        return {
          url: resourceId.replace('/full/full/', '/full/500,/').replace('/full/max/', '/full/500,/'),
          label: canvas.label || '',
        };
      }
      return null;
    } catch {
      return null;
    }
  }

  // ── Image display ─────────────────────────────────────────────────────────────
  async function setupImage(doc) {
    if (!doc.iiif_urls?.length && !doc.fragment_urls?.length) return;

    // Build view links for all sources
    const allLinks = [
      ...doc.iiif_urls.map(u => ({ type: 'iiif', url: u })),
      ...doc.fragment_urls.map(u => ({ type: 'page', url: u })),
    ];

    // Try to load a thumbnail from first IIIF URL
    if (doc.iiif_urls.length > 0) {
      const thumb = await loadIIIFThumbnail(doc.iiif_urls[0]);
      if (thumb) {
        imgEl.src = thumb.url;
        imgEl.alt = doc.shelfmark || 'תמונת הקטע';
        imgEl.hidden = false;
        imgPlaceholder.hidden = true;

        if (thumb.label) {
          imgCaption.textContent = thumb.label;
          imgCaption.hidden = false;
        }

        // Click opens first source page
        const viewUrl = doc.fragment_urls[0] || doc.iiif_urls[0];
        imgEl.style.cursor = 'pointer';
        imgEl.addEventListener('click', () => window.open(viewUrl, '_blank', 'noopener'));
      }
    }

    // Link list
    allLinks.forEach((link, i) => {
      const a = document.createElement('a');
      a.href = link.url;
      a.target = '_blank';
      a.rel = 'noopener';
      a.className = 'image-link';
      const label = link.type === 'iiif'
        ? `צפייה בספרייה הדיגיטלית (קטע ${i + 1})`
        : `דף המקור ${i > 0 ? i + 1 : ''}`.trim();
      a.innerHTML = `<span class="image-link-icon">🔗</span><span>${label}</span>`;
      imageLinks.appendChild(a);
    });
  }

  // ── Render document ───────────────────────────────────────────────────────────
  function renderDoc(doc) {
    // Page title + breadcrumb
    const title = doc.shelfmark || `PGPID ${doc.id}`;
    pageTitle.textContent = `${title} — גניזת קהיר`;
    document.title = pageTitle.textContent;
    breadcrumb.textContent = title;
    shelfmarkEl.textContent = title;

    // Library line
    const libParts = [doc.library, doc.collection].filter(Boolean);
    libraryEl.textContent = libParts.join(' · ') || '';

    // Type + language badges
    const typeClass = TYPE_BADGE[doc.type_he] || 'badge-type-other';
    let badgesHTML = `<span class="badge ${typeClass}">${esc(doc.type_he || 'לא מסווג')}</span>`;
    if (doc.lang_he) {
      badgesHTML += `<span class="badge badge-lang">${esc(doc.lang_he)}</span>`;
    }
    if (doc.has_transcription) {
      badgesHTML += `<span class="badge badge-type-rel" title="תמלול קיים">📝 תמלול</span>`;
    }
    if (doc.has_translation) {
      badgesHTML += `<span class="badge badge-type-letter" title="תרגום קיים">🌐 תרגום</span>`;
    }
    badgesEl.innerHTML = badgesHTML;

    // Metadata list
    let metaHTML = '';
    META_FIELDS.forEach(({ key, label }) => {
      const val = doc[key];
      if (!val || val === doc.type_he || (key === 'shelfmark')) return;
      if (key === 'multifragment' && val !== 'true' && val !== 'True' && val !== '1') return;
      metaHTML += `
        <dt>${esc(label)}</dt>
        <dd>${esc(String(val))}</dd>`;
    });
    metaList.innerHTML = metaHTML;

    // Description
    if (doc.description) {
      descText.textContent = doc.description;
      descBlock.hidden = false;
    }

    // Tags
    if (doc.tags?.length) {
      tagsList.innerHTML = doc.tags
        .map(t => `<span class="tag-pill">${esc(t)}</span>`)
        .join('');
      tagsBlock.hidden = false;
    }

    // Princeton link
    if (doc.princeton_url) {
      princetonLink.href = doc.princeton_url;
    }

    // Prev / Next navigation
    let navHTML = '';
    if (doc.prev) {
      navHTML += `<a href="fragment.html?id=${esc(doc.prev)}" class="frag-nav-btn">→ הקודם</a>`;
    } else {
      navHTML += `<span></span>`;
    }
    navHTML += `<span class="frag-nav-label">${doc.pos?.toLocaleString('he') || ''} מתוך ${doc.total?.toLocaleString('he') || ''}</span>`;
    if (doc.next) {
      navHTML += `<a href="fragment.html?id=${esc(doc.next)}" class="frag-nav-btn">הבא ←</a>`;
    } else {
      navHTML += `<span></span>`;
    }
    fragNav.innerHTML = navHTML;

    // Show article
    loadingEl.hidden = true;
    article.hidden = false;
  }

  // ── Bootstrap ─────────────────────────────────────────────────────────────────
  function init() {
    const id = getQueryId();
    if (!id) {
      loadingEl.innerHTML = `
        <p style="color:var(--text-3)">לא צוין מזהה מסמך.</p>
        <a href="index.html" style="color:var(--gold)">← חזרה לגלריה</a>`;
      return;
    }

    fetch(`data/docs/${encodeURIComponent(id)}.json`)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(doc => {
        renderDoc(doc);
        setupImage(doc); // async, does not block render
      })
      .catch(() => {
        loadingEl.innerHTML = `
          <p style="color:var(--text-3);margin-bottom:.5rem">המסמך לא נמצא.</p>
          <a href="index.html" style="color:var(--gold)">← חזרה לגלריה</a>`;
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
