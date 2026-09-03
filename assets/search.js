/* Geniza Explorer — Index page: search, filter, era/type browse, pagination */
(function () {
  'use strict';

  const PAGE_SIZE = 8;

  // ── State ─────────────────────────────────────────────────────────────────────
  let allDocs   = [];
  let filtered  = [];
  let page      = 1;
  let query     = '';
  let fType     = '';
  let fLang     = '';
  let fLib      = '';
  let fHas      = '';
  let fEra      = 0;   // century number (10-15), 0 = all
  let fTag      = '';  // exact Hebrew tag from tag cloud
  let fLocation = '';  // Hebrew location name, e.g. 'קהיר'

  let locationDocIds  = {};  // { 'קהיר': Set([id, ...]), ... }
  let _activeLocMarker = null;

  // ── DOM ───────────────────────────────────────────────────────────────────────
  const grid        = document.getElementById('cards-grid');
  const pagination  = document.getElementById('pagination');
  const resultsBar  = document.getElementById('results-bar');
  const loadingEl   = document.getElementById('loading-state');
  const emptyEl     = document.getElementById('empty-state');
  const searchInput = document.getElementById('search-input');
  const clearBtn    = document.getElementById('search-clear');
  const selType     = document.getElementById('filter-type');
  const selLang     = document.getElementById('filter-lang');
  const selLib      = document.getElementById('filter-library');
  const selHas      = document.getElementById('filter-has');
  const selEra      = document.getElementById('filter-era');
  const btnReset    = document.getElementById('btn-reset');
  const btnResetEmpty = document.getElementById('btn-reset-empty');
  const btnSurprise = document.getElementById('btn-surprise');

  // ── Helpers ───────────────────────────────────────────────────────────────────
  function esc(s) {
    return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
                    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  function norm(s) {
    return (s || '').toLowerCase().replace(/[־‐\-]/g,' ');
  }

  // ── Hebrew name → English equivalents (for cross-language search) ────────────
  const HE_TO_EN = {
    'אברהם': ['abraham','avraham'], 'משה': ['moses','moshe'],
    'יצחק': ['isaac','yitzhak'],   'יעקב': ['jacob','yaakov'],
    'יוסף': ['joseph','yosef'],    'שמואל': ['samuel','shmuel'],
    'דוד': ['david'],              'שלמה': ['solomon','shlomo'],
    'אליהו': ['elijah','eliyahu'], 'יהודה': ['judah','yehuda'],
    'בנימין': ['benjamin'],        'אהרן': ['aaron','aharon'],
    'אליעזר': ['eliezer'],         'מרדכי': ['mordecai','mordechai'],
    'חנן': ['hanan'],              'יחיאל': ['yehiel'],
    'פרחייה': ['perahya'],         'הלפון': ['halfon'],
    'מיימון': ['maimon'],          'עובדיה': ['ovadia','obadiah'],
    'נתנאל': ['nathanel','natanel'],'יוחנן': ['yohanan','johanan'],
    'ירושלים': ['jerusalem'],      'מצרים': ['egypt','fustat'],
    'פוסטאט': ['fustat'],          'קהיר': ['cairo'],
    'אלכסנדריה': ['alexandria'],   'עדן': ['aden'],
    'דמשק': ['damascus'],          'בגדד': ['baghdad'],
  };

  function matchTerm(term, hay) {
    if (hay.includes(term)) return true;
    const variants = HE_TO_EN[term];
    return variants ? variants.some(v => hay.includes(v)) : false;
  }

  // ── Badge colours ─────────────────────────────────────────────────────────────
  const TYPE_CLASS = {
    'מכתב':            'badge-type-letter',
    'מסמך משפטי':      'badge-type-legal',
    'טקסט ספרותי':     'badge-type-lit',
    'טקסט דתי':        'badge-type-rel',
    'טקסט פרא-ספרותי': 'badge-type-para',
  };

  // ── Populate dropdowns ────────────────────────────────────────────────────────
  function populateFilters(docs) {
    const types = new Set(), langs = new Set(), libs = new Set();
    docs.forEach(d => {
      if (d.th)  types.add(d.th);
      if (d.lh)  d.lh.split('؛').forEach(l => { const t=l.trim(); if(t) langs.add(t); });
      if (d.lib) d.lib.split('·').forEach(l => { const t=l.trim(); if(t) libs.add(t); });
    });
    const fill = (sel, items) => {
      const first = sel.options[0].outerHTML;
      sel.innerHTML = first;
      [...items].sort().forEach(v => {
        const o = document.createElement('option');
        o.value = v; o.textContent = v; sel.appendChild(o);
      });
    };
    fill(selType, types);
    fill(selLang, langs);
    fill(selLib,  libs);
  }

  // ── Filter logic ──────────────────────────────────────────────────────────────
  function applyFilters() {
    const q = norm(query);
    filtered = allDocs.filter(d => {
      if (fType && d.th !== fType) return false;
      if (fLang && !(d.lh||'').includes(fLang)) return false;
      if (fLib  && !(d.lib||'').includes(fLib))  return false;
      if (fHas === 'img' && !d.img) return false;
      if (fEra && d.c !== fEra) return false;
      if (fTag && !(d.tgh||[]).includes(fTag)) return false;
      if (fLocation) {
        const locSet = locationDocIds[fLocation];
        if (locSet && !locSet.has(d.id)) return false;
      }
      if (q) {
        const hay = norm([d.s||'',d.th||'',d.lh||'',d.or||'',d.dt||'',d.lib||'',d.dh||'',d.d||''].join(' '));
        return q.split(/\s+/).filter(Boolean).every(w => matchTerm(w, hay));
      }
      return true;
    });
    page = 1;
    updateResetVisibility();
    render();
  }

  function hasActiveFilter() {
    return !!(query || fType || fLang || fLib || fHas || fEra || fTag || fLocation);
  }

  function resetAll() {
    query = ''; fType = ''; fLang = ''; fLib = ''; fHas = ''; fEra = 0; fTag = ''; fLocation = '';
    searchInput.value = '';
    clearBtn.hidden = true;
    selType.value = ''; selLang.value = ''; selLib.value = ''; selHas.value = '';
    if (selEra) selEra.value = '';
    if (_activeLocMarker) {
      _activeLocMarker.getElement()?.querySelector('.gmap-pin')?.classList.remove('gmap-pin--active');
      _activeLocMarker = null;
    }
    applyFilters();
  }

  function updateResetVisibility() {
    if (btnReset) btnReset.hidden = !hasActiveFilter();
  }

  // ── IIIF thumbnail lazy loader ────────────────────────────────────────────────
  let thumbObserver = null;

  async function fetchIIIFThumb(manifestUrl) {
    try {
      const resp = await fetch(manifestUrl, { mode: 'cors', cache: 'force-cache' });
      if (!resp.ok) return null;
      const m = await resp.json();
      const canvas = m?.sequences?.[0]?.canvases?.[0];
      if (!canvas) return null;
      const mThumb = m.thumbnail?.['@id'] || m.thumbnail;
      if (typeof mThumb === 'string' && mThumb.startsWith('http')) return mThumb;
      const cThumb = canvas.thumbnail?.['@id'] || canvas.thumbnail;
      if (typeof cThumb === 'string' && cThumb.startsWith('http')) return cThumb;
      const res = canvas.images?.[0]?.resource;
      const svc = res?.service?.['@id'] || res?.service?.id;
      if (svc) return `${svc}/full/300,/0/default.jpg`;
      const rid = res?.['@id'];
      if (rid) return rid.replace('/full/full/', '/full/300,/').replace('/full/max/', '/full/300,/');
      return null;
    } catch { return null; }
  }

  function initThumbObserver() {
    if (!('IntersectionObserver' in window)) return;
    thumbObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        const img = entry.target;
        const url = img.dataset.iu;
        if (!url) return;
        thumbObserver.unobserve(img);
        fetchIIIFThumb(url).then(src => {
          if (src) { img.src = src; img.hidden = false; }
        });
      });
    }, { rootMargin: '200px' });
  }

  function observeThumb(el) {
    if (thumbObserver) thumbObserver.observe(el);
  }

  // ── Card HTML ─────────────────────────────────────────────────────────────────
  // התיאור המלא נשאר ב-search.json כי החיפוש סורק אותו (ראו שורת ה-hay),
  // אבל הכרטיס מדפיס רק את מה ש-CSS מראה ממנו — שלוש שורות. בלי זה גלריה של
  // 8 כרטיסים נשאה אלפי תווים מיותרים ב-DOM, ורכזת נושא נשאה עשרות אלפים.
  // התקרה זהה ל-CARD_DESC ב-prerender.py, כדי ששני מחוללי הכרטיס יסכימו.
  const CARD_DESC = 140;
  const trunc = (s, n) => s.length <= n
    ? s
    : s.slice(0, n).replace(/\s+\S*$/, '').replace(/[ ,.;:\u05BE-]+$/, '') + '\u2026';

  function cardHTML(doc) {
    const cls  = TYPE_CLASS[doc.th] || 'badge-type-other';
    const icons = [
      doc.tr  ? '<span class="card-icon" title="תמלול">📝</span>' : '',
      doc.tl  ? '<span class="card-icon" title="תרגום">🌐</span>'  : '',
    ].join('');

    const langBadge = doc.lh
      ? `<span class="badge badge-lang">${esc(doc.lh.split('؛')[0].trim())}</span>` : '';

    const dateLine   = doc.dt ? `<span class="card-date">${esc(doc.dt)}</span>` : '';
    const originLine = doc.or ? `<span class="card-origin">${esc(doc.or)}</span>` : '';
    const libLine    = doc.lib ? `<span class="card-lib">${esc(doc.lib)}</span>` : '';
    const descLine = doc.dh
      ? `<p class="card-description">${esc(trunc(doc.dh, CARD_DESC))}</p>`
      : (doc.d
          ? `<p class="card-description"><span class="card-desc-label">תיאור: </span>${esc(doc.d.split(' ').slice(0,20).join(' '))}…</p>`
          : '');
    const thumbImg = doc.iu
      ? `<img class="card-thumb" data-iu="${esc(doc.iu)}" alt="" hidden loading="lazy">`
      : '';

    return `
      <a href="d/${esc(doc.id)}.html" class="card${doc.iu?' card--has-thumb':''}" role="listitem"
         aria-label="${esc(doc.s||'מסמך')}">
        ${thumbImg}
        <div class="card-top">
          <span class="card-shelfmark">${esc(doc.s) || 'PGPID ' + esc(doc.id)}</span>
          <span class="card-icons" aria-hidden="true">${icons}</span>
        </div>
        <div class="card-meta">
          <span class="badge ${cls}">${esc(doc.th||'לא מסווג')}</span>
          ${langBadge}
        </div>
        ${dateLine||originLine ? `<div class="card-geo">${dateLine}${originLine}</div>` : ''}
        ${descLine}
        ${libLine ? `<div class="card-footer">${libLine}</div>` : ''}
      </a>`;
  }

  // ── Render ────────────────────────────────────────────────────────────────────
  function render() {
    const total = filtered.length;
    const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    page = Math.min(page, pages);

    const slice = filtered.slice((page-1)*PAGE_SIZE, page*PAGE_SIZE);

    if (!hasActiveFilter()) {
      resultsBar.innerHTML = `<strong>${allDocs.length.toLocaleString('he-IL')}</strong> מסמכים באוסף`;
    } else {
      resultsBar.innerHTML = `נמצאו <strong>${total.toLocaleString('he-IL')}</strong> מסמכים`;
    }

    emptyEl.hidden  = total > 0;
    grid.hidden     = total === 0;
    if (total > 0) {
      grid.innerHTML = slice.map(cardHTML).join('');
      grid.querySelectorAll('.card-thumb').forEach(observeThumb);
    }

    renderPagination(pages);
  }

  function renderPagination(pages) {
    if (pages <= 1) { pagination.innerHTML = ''; return; }
    const p = page;

    /* Jumps of five hundred were worse than useless here. The gallery has no
       meaningful order to jump into, so "page 2500" tells a reader nothing —
       it only made the bar long. What a reader actually does is step through
       neighbours, or go straight to a page they already have in mind, and the
       box serves the second far better than any set of buttons could. */
    const shown = new Set([1, pages]);
    for (let n = p - 2; n <= p + 2; n++) if (n >= 1 && n <= pages) shown.add(n);

    let html = `<button class="page-btn" ${p === 1 ? 'disabled' : ''} data-page="${p - 1}" aria-label="לעמוד הקודם">→</button>`;
    let prev = 0;
    [...shown].sort((a, b) => a - b).forEach(n => {
      if (prev && n > prev + 1) html += '<span class="page-gap" aria-hidden="true">…</span>';
      html += `<button class="page-btn${n === p ? ' active' : ''}" data-page="${n}"`
            + `${n === p ? ' aria-current="page"' : ''} aria-label="עמוד ${n}">${n}</button>`;
      prev = n;
    });
    html += `<button class="page-btn" ${p === pages ? 'disabled' : ''} data-page="${p + 1}" aria-label="לעמוד הבא">←</button>`;

    html += `<form class="page-jump" id="page-jump">`
          + `<label for="page-jump-input">עבור לעמוד</label>`
          + `<input id="page-jump-input" type="number" min="1" max="${pages}" `
          + `inputmode="numeric" placeholder="${p}" aria-label="מספר עמוד, בין 1 ל-${pages}">`
          + `<span class="page-jump-total">מתוך ${pages.toLocaleString('he-IL')}</span>`
          + `<button type="submit" class="page-btn page-jump-go">עבור</button>`
          + `</form>`;

    pagination.innerHTML = html;
  }

  function goToPage(n, pages) {
    page = Math.min(Math.max(1, n), pages);
    render();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }


  // ── Events ────────────────────────────────────────────────────────────────────
  function wire() {
    let timer;
    searchInput.addEventListener('input', () => {
      query = searchInput.value;
      clearBtn.hidden = !query;
      clearTimeout(timer);
      timer = setTimeout(applyFilters, 220);
    });
    clearBtn.addEventListener('click', () => {
      query = ''; fTag = ''; searchInput.value = ''; clearBtn.hidden = true; applyFilters();
    });

    selType.addEventListener('change', () => { fType = selType.value; applyFilters(); });
    selLang.addEventListener('change', () => { fLang = selLang.value; applyFilters(); });
    selLib.addEventListener('change',  () => { fLib  = selLib.value;  applyFilters(); });
    selHas.addEventListener('change',  () => { fHas  = selHas.value;  applyFilters(); });
    if (selEra) selEra.addEventListener('change', () => {
      fEra = +selEra.value || 0;
      applyFilters();
    });

    if (btnReset)      btnReset.addEventListener('click', resetAll);
    if (btnResetEmpty) btnResetEmpty.addEventListener('click', resetAll);

    // Surprise button — random Hebrew fragment with an image
    if (btnSurprise) {
      btnSurprise.addEventListener('click', () => {
        if (!allDocs.length) return;
        const pool = allDocs.filter(d => d.img && (d.lh || '').includes('עברית'));
        const pick = (pool.length ? pool : allDocs)[Math.floor(Math.random() * (pool.length || allDocs.length))];
        window.location.href = `d/${encodeURIComponent(pick.id)}.html`;
      });
    }

    pagination.addEventListener('click', e => {
      const btn = e.target.closest('[data-page]');
      if (!btn || btn.disabled) return;
      goToPage(+btn.dataset.page, Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)));
    });

    pagination.addEventListener('submit', e => {
      const form = e.target.closest('#page-jump');
      if (!form) return;
      e.preventDefault();
      const n = parseInt(form.querySelector('input').value, 10);
      if (Number.isFinite(n)) goToPage(n, Math.max(1, Math.ceil(filtered.length / PAGE_SIZE)));
    });
  }

  // ── Dashboard ────────────────────────────────────────────────────────────────
  const TAG_HE = {
    'marriage':'נישואים','divorce':'גירושין','trade':'מסחר','medicine':'רפואה',
    'legal':'משפטי','synagogue':'בית כנסת','court':'בית דין','debt':'חוב',
    'debts':'חובות','loan':'הלוואה','women':'נשים','children':'ילדים',
    'travel':'נסיעות','partnership':'שותפות','charity':'צדקה',
    'captive':'שבויים','captives':'שבויים','family':'משפחה',
    'inheritance':'ירושה','property':'נכסים','food':'מזון',
    'clothing':'ביגוד','money':'כסף','silk':'משי','flax':'פשתן',
    'spices':'תבלינים','india':'הודו','maghreb':'מגרב',
    'community':'קהילה','nagid':'נגיד','gaon':'גאון','yeshiva':'ישיבה',
    'responsa':'שו"ת','prayer':'תפילה','poetry':'שירה','liturgy':'ליטורגיה',
    'ketubba':'כתובה','dowry':'נדוניה','estate':'עיזבון','rent':'שכר דירה',
    'house':'בית','orphan':'יתום','widow':'אלמנה','heqdesh':'הקדש',
    'waqf':'ווקף','business':'עסקים','merchant':'סוחר','ship':'ספינה',
    'tax':'מס','pilgrimage':'עלייה לרגל','scholarship':'לימוד תורה',
    'bible':'תנ"ך','letter':'מכתב','lists':'רשימות','account':'חשבון',
    'accounts':'חשבונות','lease':'חכירה','sale':'מכירה','gift':'מתנה',
  };

  function loadDidYouKnow() {
    fetch('data/did_you_know.json')
      .then(r => r.ok ? r.json() : null)
      .then(facts => {
        if (!facts || !facts.length) return;
        const f = facts[Math.floor(Math.random() * facts.length)];
        const card = document.getElementById('kpi-dyk');
        if (!card) return;
        const textEl = document.getElementById('dyk-text');
        const markEl = document.getElementById('dyk-shelfmark');
        if (textEl) textEl.textContent = f.text;
        if (markEl) markEl.textContent = f.shelfmark;
        card.href = 'd/' + encodeURIComponent(f.pgpid) + '.html';
      })
      .catch(() => {});
  }

  function loadStats() {
    fetch('data/stats.json')
      .then(r => r.ok ? r.json() : null)
      .then(s => {
        if (!s) return;
        renderKPI(s);
        renderTagCloud(s.top_tags || []);
      })
      .catch(() => {});
  }

  function renderKPI(s) {
    const total = s.total || 1;
    const pct = n => Math.round(n / total * 100) + '%';
    const el = document.getElementById('kpi-img');
    if (el && s.has_img) {
      const num = el.querySelector('.kpi-num');
      if (num) num.textContent = s.has_img.toLocaleString('he-IL');
      const lbl = el.querySelector('.kpi-label');
      if (lbl) lbl.textContent = lbl.textContent + ' (' + pct(s.has_img) + ')';
    }
  }

  /* האישים שכבר מוצגים ברצועת "אישים בגניזה לאורך הדורות". הרשימה מגיעה
     מ-TIMELINE_TAGS שב-index.html, שנכתב מ-PEOPLE_TIMELINE, כדי שהוספת אדם
     לרצועה תסיר אותו מן הענן בלי עריכה שנייה כאן. */
  const CLOUD_SKIP = new Set([
    ...(typeof TIMELINE_TAGS !== 'undefined' ? TIMELINE_TAGS : []),
    'יהודית-ערבית','מכתב','מסמך משפטי','ערבית','חשבונות','עברית','מסמך מדינה',
    // location names — shown on the map instead
    'קהיר','פוסטאט','אלכסנדריה','ירושלים','צור','דמשק','עדן','בגדד','טבריה',
    'ספרד','סיציליה','הודו','חלב','קוס','פרס','פלרמו','עכו','רמלה','טריפולי','קירואן','דמיאט',
    // spices & luxury goods — shown in spice bar instead
    'פלפל','זעפרן','קינמון','זנגביל','כמון','כוסברה','דבש','סוכר',
    'שומשום','ציפורן','אניס','מסטיק','לבונה','כמון שחור','גלנגל','נרד','לכה','עץ ברזיל','סטוראקס',
    'נענע','פיגם',
    'משי','זהב','כסף','פנינים','נחושת','אלמוג','אינדיגו','ארגמן','עופרת',
  ]);

  const SPICE_TAGS = [
    'פלפל','זעפרן','קינמון','סוכר','דבש','זנגביל','כמון','כוסברה',
    'שומשום','ציפורן','אניס','מסטיק','לבונה','כמון שחור','גלנגל','נרד','לכה','עץ ברזיל','סטוראקס',
    'נענע','פיגם',
    'משי','זהב','כסף','פנינים','נחושת','אלמוג','אינדיגו','ארגמן','עופרת',
  ];

  // Latin/English subtitle for less familiar spices/goods
  const SPICE_LATIN = {
    'גלנגל':    'Galangal',
    'נרד':      'Spikenard',
    'לכה':      'Lac resin',
    'עץ ברזיל': 'Brazilwood',
    'סטוראקס':  'Storax',
    'מסטיק':    'Mastic',
    'לבונה':    'Frankincense',
    'כמון שחור':'Nigella',
    'פיגם':     'Rue',
    'אינדיגו':  'Indigo',
    'אלמוג':    'Coral',
    'ארגמן':    'Purple dye',
  };

  // tag → /t/<slug>/. Populated from data/tag_slugs.json before the cloud and the
  // spice bar render. A tag that has a hub page becomes a link to it: the hub
  // carries an introduction and lists every document, which is strictly more
  // than the in-place filter did. A tag with no page keeps the old behaviour.
  let TAG_SLUGS = {};

  function tagChip(tag, inner, cls, extraAttr) {
    const slug = TAG_SLUGS[tag];
    if (slug) {
      return `<a class="${cls}" href="t/${esc(slug)}/" ${extraAttr}>${inner}</a>`;
    }
    return `<button class="${cls}" data-tag="${esc(tag)}" ${extraAttr}>${inner}</button>`;
  }

  function renderTagCloud(tags) {
    const el = document.getElementById('tag-cloud');
    if (!el || !tags.length) return;
    const filtered_tags = tags.filter(({t}) => t && !/^\d/.test(t) && !CLOUD_SKIP.has(t));
    if (!filtered_tags.length) { el.innerHTML = ''; return; }
    const maxC = filtered_tags[0].c, minC = filtered_tags[filtered_tags.length - 1].c;
    const range = maxC - minC || 1;
    const MIN_SIZE = 0.82, MAX_SIZE = 1.85;
    const MIN_ALPHA = 0.72;
    const display = filtered_tags.slice(0, 65)
      .sort((a, b) => a.t.localeCompare(b.t, 'he'));
    el.innerHTML = display.map(({t, c}) => {
      const size  = (MIN_SIZE + (c - minC) / range * (MAX_SIZE - MIN_SIZE)).toFixed(2);
      const alpha = (MIN_ALPHA + (c - minC) / range * (1 - MIN_ALPHA)).toFixed(2);
      const attrs = `style="font-size:${size}rem;opacity:${alpha}" `
                  + `title="${esc(t)} (${c.toLocaleString('he-IL')} מסמכים)"`;
      return tagChip(t, esc(t), 'tag-pill-cloud', attrs);
    }).join('');
    el.addEventListener('click', e => {
      const btn = e.target.closest('.tag-pill-cloud');
      if (!btn) return;
      fTag = btn.dataset.tag;
      searchInput.value = btn.dataset.tag;
      query = '';
      clearBtn.hidden = false;
      applyFilters();
      document.getElementById('cards-grid')?.scrollIntoView({behavior:'smooth', block:'start'});
    });
  }

  function renderSpiceBar(tagCounts) {
    const el = document.getElementById('spice-buttons');
    if (!el) return;
    el.innerHTML = SPICE_TAGS.map(tag => {
      const count = tagCounts[tag] || 0;
      const inner = `<span class="spice-btn-name">${esc(tag)}</span>`
        + (SPICE_LATIN[tag] ? `<span class="spice-btn-latin">${esc(SPICE_LATIN[tag])}</span>` : '')
        + `<span class="spice-btn-count">${count.toLocaleString('he-IL')}</span>`;
      return tagChip(tag, inner, 'spice-btn',
        `title="${esc(tag)} (${count.toLocaleString('he-IL')} מסמכים)"`);
    }).join('');
    el.addEventListener('click', e => {
      const btn = e.target.closest('.spice-btn');
      if (!btn) return;
      fTag = btn.dataset.tag;
      searchInput.value = btn.dataset.tag;
      query = '';
      clearBtn.hidden = false;
      applyFilters();
      document.getElementById('cards-grid')?.scrollIntoView({behavior:'smooth', block:'start'});
    });
  }

  // ── Location map ─────────────────────────────────────────────────────────────
  const MAP_LOCATIONS = [
    { name: 'פוסטאט',    lat: 30.008, lng: 31.233 },
    { name: 'קהיר',      lat: 30.100, lng: 31.350 },
    { name: 'אלכסנדריה', lat: 31.200, lng: 29.919 },
    { name: 'ירושלים',   lat: 31.768, lng: 35.214 },
    { name: 'צור',       lat: 33.271, lng: 35.199 },
    { name: 'דמשק',      lat: 33.510, lng: 36.291 },
    { name: 'עדן',       lat: 12.786, lng: 45.019 },
    { name: 'בגדד',      lat: 33.315, lng: 44.366 },
    { name: 'טבריה',     lat: 32.792, lng: 35.531 },
    { name: 'חלב',       lat: 36.202, lng: 37.161  },
    { name: 'קוס',       lat: 25.907, lng: 32.753  },
    { name: 'פרס',       lat: 32.661, lng: 51.680  },
    { name: 'ספרד',      lat: 37.384, lng: -5.976  },
    { name: 'סיציליה',   lat: 37.600, lng: 14.015  },
    { name: 'הודו',      lat: 11.000, lng: 76.000  },
    { name: 'דמיאט',    lat: 31.416, lng: 31.815  },
    { name: 'עכו',      lat: 32.927, lng: 35.073  },
    { name: 'פלרמו',    lat: 38.115, lng: 13.361  },
    { name: 'טריפולי',  lat: 32.904, lng: 13.180  },
    { name: 'רמלה',     lat: 31.928, lng: 34.872  },
    { name: 'קירואן',   lat: 35.678, lng: 10.099  },
  ];

  function initLocationMap(locCounts) {
    const mapEl = document.getElementById('geniza-map');
    if (!mapEl || typeof L === 'undefined') return;

    const map = L.map('geniza-map', { scrollWheelZoom: false });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://osm.org/copyright">OpenStreetMap</a>',
      maxZoom: 13,
    }).addTo(map);

    const bounds = [];
    MAP_LOCATIONS.forEach(loc => {
      const count = locCounts[loc.name];
      if (!count) return;
      bounds.push([loc.lat, loc.lng]);

      const icon = L.divIcon({
        html: `<div class="gmap-pin"><span class="gmap-pin-name">${esc(loc.name)}</span><span class="gmap-pin-count">${count.toLocaleString('he-IL')}</span></div>`,
        className: '',
        iconSize: [90, 42],
        iconAnchor: [45, 42],
      });

      const marker = L.marker([loc.lat, loc.lng], { icon, keyboard: true }).addTo(map);
      /* Leaflet מוסיף לסיכה tabindex=0, ולכן היא נגישה במקלדת — אבל
         בלי role ובלי שם היא מוכרזת כ"קבוצה" ריקה. */
      const slug = TAG_SLUGS[loc.name];
      /* Leaflet gives the pin tabindex=0 and role="button", so it is reachable
         by keyboard but announced as an unnamed button. The name has to be set
         on the element Leaflet builds, and that element does not exist until
         the marker is on the map — reading it straight after addTo() returns
         null and the labels are silently dropped. */
      const label = () => {
        const el = marker.getElement();
        if (!el) return;
        el.setAttribute('role', slug ? 'link' : 'button');
        el.setAttribute('aria-label', slug
          ? `${loc.name} — ${count.toLocaleString('he-IL')} מסמכים, לדף הנושא`
          : `סינון לפי ${loc.name} — ${count.toLocaleString('he-IL')} מסמכים`);
        if (slug) el.removeAttribute('aria-pressed');
        else el.setAttribute('aria-pressed', 'false');
      };
      marker.on('add', label);
      label();
      const el = marker.getElement();
      marker.on('click', () => {
        /* A pin used to filter the gallery in place, which left the reader on
           the home page with no URL to share and no way back to the place
           itself. Every location on this map now has a hub under t/, and the
           hub is strictly more: an introduction, every document rather than
           the first page of them, and an address. Filtering stays only for a
           location that has no hub yet. */
        if (slug) { window.location.href = `t/${slug}/`; return; }
        const pinEl = marker.getElement()?.querySelector('.gmap-pin');
        const isActive = fLocation === loc.name;

        if (_activeLocMarker) {
          const prev = _activeLocMarker.getElement();
          prev?.querySelector('.gmap-pin')?.classList.remove('gmap-pin--active');
          prev?.setAttribute('aria-pressed', 'false');
        }

        if (isActive) {
          fLocation = '';
          _activeLocMarker = null;
          el?.setAttribute('aria-pressed', 'false');
        } else {
          fLocation = loc.name;
          pinEl?.classList.add('gmap-pin--active');
          _activeLocMarker = marker;
          el?.setAttribute('aria-pressed', 'true');
        }

        updateResetVisibility();
        applyFilters();
        setTimeout(() => {
          const el = document.getElementById('results-bar');
          if (!el) return;
          const y = el.getBoundingClientRect().top + window.pageYOffset - 80;
          window.scrollTo({ top: Math.max(0, y), behavior: 'smooth' });
        }, 50);
      });
    });

    const isMobile = window.innerWidth < 700;
    map.setView([32, 35.5], isMobile ? 6 : 7);
  }

  function loadTagsAndMap() {
    // The slug map has to arrive before the chips render, or they fall back to
    // filtering in place and the hub pages become unreachable from here.
    const slugs = fetch('data/tag_slugs.json')
      .then(r => r.ok ? r.json() : {})
      .then(map => { TAG_SLUGS = map || {}; })
      .catch(() => { TAG_SLUGS = {}; });

    slugs.then(() => fetch('data/tags_he.json')
      .then(r => r.ok ? r.json() : null)
      .then(tags => {
        if (!tags) return;
        const locNames  = new Set(MAP_LOCATIONS.map(l => l.name));
        const spiceSet  = new Set(SPICE_TAGS);
        const locCounts   = {};
        const spiceCounts = {};
        for (const [docId, docTags] of Object.entries(tags)) {
          for (const tag of docTags) {
            if (locNames.has(tag)) {
              if (!locationDocIds[tag]) locationDocIds[tag] = new Set();
              locationDocIds[tag].add(docId);
              locCounts[tag] = (locCounts[tag] || 0) + 1;
            }
            if (spiceSet.has(tag)) {
              spiceCounts[tag] = (spiceCounts[tag] || 0) + 1;
            }
          }
        }
        initLocationMap(locCounts);
        renderSpiceBar(spiceCounts);
      })
      .catch(() => {}));
  }

  // ── Boot ──────────────────────────────────────────────────────────────────────
  function init() {
    initThumbObserver();
    wire();
    loadTagsAndMap();
    fetch('data/search.json')
      .then(r => { if(!r.ok) throw new Error(r.status); return r.json(); })
      .then(data => {
        allDocs = filtered = data;
        loadingEl.hidden = true;
        populateFilters(data);
        render();
        loadStats();
        loadDidYouKnow();
      })
      .catch(() => {
        loadingEl.hidden = true;
        grid.innerHTML = `
          <div style="grid-column:1/-1;text-align:center;padding:3rem;color:var(--text-3)">
            <p style="font-size:2rem;margin-bottom:.5rem">⚠️</p>
            <p>לא ניתן לטעון נתונים.</p>
            <p style="font-size:.85rem;margin-top:.5rem">הריצו: <code>python build.py</code></p>
          </div>`;
      });
  }

  document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', init)
    : init();
})();
