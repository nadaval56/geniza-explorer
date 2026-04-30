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
  let fEra      = 0;   // century number (10-14), 0 = all
  let fTag      = '';  // exact Hebrew tag from tag cloud

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
  const btnReset    = document.getElementById('btn-reset');
  const btnResetEmpty = document.getElementById('btn-reset-empty');
  const btnSurprise = document.getElementById('btn-surprise');
  const eraChips    = document.querySelectorAll('[data-era]');
  const typeChips   = document.querySelectorAll('[data-type]');

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
      if (fEra) {
        if (!d.c) return false;
        if (fEra === 14 ? d.c < 14 : d.c !== fEra) return false;
      }
      if (fTag && !(d.tgh||[]).includes(fTag)) return false;
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
    return !!(query || fType || fLang || fLib || fHas || fEra || fTag);
  }

  function resetAll() {
    query = ''; fType = ''; fLang = ''; fLib = ''; fHas = ''; fEra = 0; fTag = '';
    searchInput.value = '';
    clearBtn.hidden = true;
    selType.value = ''; selLang.value = ''; selLib.value = ''; selHas.value = '';
    eraChips.forEach(c => c.classList.remove('chip--active'));
    typeChips.forEach(c => c.classList.remove('chip--active'));
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
      ? `<p class="card-description">${esc(doc.dh)}</p>`
      : (doc.d
          ? `<p class="card-description"><span class="card-desc-label">תיאור: </span>${esc(doc.d.split(' ').slice(0,20).join(' '))}…</p>`
          : '');
    const thumbImg = doc.iu
      ? `<img class="card-thumb" data-iu="${esc(doc.iu)}" alt="" hidden loading="lazy">`
      : '';

    return `
      <a href="fragment.html?id=${esc(doc.id)}" class="card${doc.iu?' card--has-thumb':''}" role="listitem"
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
    let html = `<button class="page-btn" ${p===1?'disabled':''} data-page="${p-1}" aria-label="קודם">→</button>`;
    const shown = new Set();
    [1,2,p-2,p-1,p,p+1,p+2,pages-1,pages].forEach(n => { if(n>=1&&n<=pages) shown.add(n); });
    let prev=0;
    [...shown].sort((a,b)=>a-b).forEach(n => {
      if (prev && n>prev+1) html += '<span class="page-btn" style="pointer-events:none;opacity:.3">…</span>';
      html += `<button class="page-btn${n===p?' active':''}" data-page="${n}">${n}</button>`;
      prev=n;
    });
    html += `<button class="page-btn" ${p===pages?'disabled':''} data-page="${p+1}" aria-label="הבא">←</button>`;
    pagination.innerHTML = html;
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

    if (btnReset)      btnReset.addEventListener('click', resetAll);
    if (btnResetEmpty) btnResetEmpty.addEventListener('click', resetAll);

    // Era chips
    eraChips.forEach(btn => {
      btn.addEventListener('click', () => {
        const era = +btn.dataset.era;
        if (fEra === era) { fEra = 0; btn.classList.remove('chip--active'); }
        else {
          fEra = era;
          eraChips.forEach(c => c.classList.remove('chip--active'));
          btn.classList.add('chip--active');
        }
        applyFilters();
      });
    });

    // Type chips
    typeChips.forEach(btn => {
      btn.addEventListener('click', () => {
        const t = btn.dataset.type;
        if (fType === t) { fType = ''; btn.classList.remove('chip--active'); }
        else {
          fType = t;
          selType.value = t;
          typeChips.forEach(c => c.classList.remove('chip--active'));
          btn.classList.add('chip--active');
        }
        applyFilters();
      });
    });

    // Surprise button
    if (btnSurprise) {
      btnSurprise.addEventListener('click', () => {
        if (!allDocs.length) return;
        const doc = allDocs[Math.floor(Math.random() * allDocs.length)];
        window.location.href = `fragment.html?id=${encodeURIComponent(doc.id)}`;
      });
    }

    pagination.addEventListener('click', e => {
      const btn = e.target.closest('[data-page]');
      if (!btn || btn.disabled) return;
      page = +btn.dataset.page;
      render();
      window.scrollTo({ top: 0, behavior: 'smooth' });
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
        card.href = 'fragment.html?id=' + f.pgpid;
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
        renderDist('dist-type', s.by_type || {});
        renderDist('dist-lang', s.by_lang || {});
        renderCentury(s.by_century || {});
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

  const SKIP_TAGS = new Set([
    'dimme','fgp stub','arabic','hebrew','judaeo-arabic','aramaic',
    'latin','coptic','persian','syriac','greek','new','old',
  ]);

  const CLOUD_SKIP = new Set(['יהודית-ערבית','מכתב','מסמך משפטי','ערבית','חשבונות','עברית','מסמך מדינה']);

  function renderTagCloud(tags) {
    const el = document.getElementById('tag-cloud');
    if (!el || !tags.length) return;
    const filtered_tags = tags.filter(({t}) => t && !/^\d/.test(t) && !CLOUD_SKIP.has(t));
    if (!filtered_tags.length) return;
    const maxC = filtered_tags[0].c, minC = filtered_tags[filtered_tags.length - 1].c;
    const range = maxC - minC || 1;
    const MIN_SIZE = 0.72, MAX_SIZE = 1.85;
    const display = filtered_tags.slice(0, 65)
      .sort((a, b) => a.t.localeCompare(b.t, 'he'));
    el.innerHTML = display.map(({t, c}) => {
      const size  = (MIN_SIZE + (c - minC) / range * (MAX_SIZE - MIN_SIZE)).toFixed(2);
      const alpha = (0.5 + (c - minC) / range * 0.5).toFixed(2);
      return `<button class="tag-pill-cloud" style="font-size:${size}rem;opacity:${alpha}"
        data-tag="${esc(t)}" title="${esc(t)} (${c.toLocaleString('he-IL')} מסמכים)"
        >${esc(t)}</button>`;
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

  function renderDist(id, obj) {
    const el = document.getElementById(id);
    if (!el) return;
    const entries = Object.entries(obj);
    if (!entries.length) return;
    const maxV = entries[0][1];
    el.innerHTML = entries.slice(0, 8).map(([label, count]) => {
      const pct = Math.round(count / maxV * 100);
      return `<div class="dist-row">
        <span class="dist-label" title="${esc(label)}">${esc(label)}</span>
        <div class="dist-bar-wrap"><div class="dist-bar" style="width:${pct}%"></div></div>
        <span class="dist-count">${count.toLocaleString('he-IL')}</span>
      </div>`;
    }).join('');
  }

  function renderCentury(obj) {
    const el = document.getElementById('dist-century');
    if (!el) return;
    const entries = Object.entries(obj).sort((a, b) => +a[0] - +b[0]);
    if (!entries.length) return;
    const maxV = Math.max(...entries.map(([, v]) => v));
    el.innerHTML = entries.map(([c, count]) => {
      const h = Math.round(count / maxV * 100);
      const label = +c >= 14 ? '14+' : `${c}`;
      const num = count >= 1000 ? (count / 1000).toFixed(1) + 'k' : count;
      return `<div class="century-col">
        <div class="century-bar" style="height:${h}%" title="${count.toLocaleString('he-IL')} מסמכים"></div>
        <span class="century-label">מ-${label}</span>
        <span class="century-count">${num}</span>
      </div>`;
    }).join('');
  }

  // ── Boot ──────────────────────────────────────────────────────────────────────
  function init() {
    initThumbObserver();
    wire();
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
