/* Geniza Explorer — Index page: search, filter, era/type browse, pagination */
(function () {
  'use strict';

  const PAGE_SIZE = 48;

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
      if (fHas === 'tr'  && !d.tr)  return false;
      if (fHas === 'tl'  && !d.tl)  return false;
      if (fEra) {
        if (!d.c) return false;
        if (fEra === 14 ? d.c < 14 : d.c !== fEra) return false;
      }
      if (q) {
        const hay = norm([d.s||'',d.th||'',d.lh||'',d.or||'',d.dt||'',d.lib||''].join(' '));
        return q.split(/\s+/).filter(Boolean).every(w => hay.includes(w));
      }
      return true;
    });
    page = 1;
    updateResetVisibility();
    render();
  }

  function hasActiveFilter() {
    return !!(query || fType || fLang || fLib || fHas || fEra);
  }

  function resetAll() {
    query = ''; fType = ''; fLang = ''; fLib = ''; fHas = ''; fEra = 0;
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

  // ── Card HTML ─────────────────────────────────────────────────────────────────
  function cardHTML(doc) {
    const cls  = TYPE_CLASS[doc.th] || 'badge-type-other';
    const icons = [
      doc.img ? '<span class="card-icon" title="תמונה">🖼</span>' : '',
      doc.tr  ? '<span class="card-icon" title="תמלול">📝</span>' : '',
      doc.tl  ? '<span class="card-icon" title="תרגום">🌐</span>'  : '',
    ].join('');

    const langBadge = doc.lh
      ? `<span class="badge badge-lang">${esc(doc.lh.split('؛')[0].trim())}</span>` : '';

    const dateLine   = doc.dt ? `<span class="card-date">${esc(doc.dt)}</span>` : '';
    const originLine = doc.or ? `<span class="card-origin">${esc(doc.or)}</span>` : '';
    const libLine    = doc.lib ? `<span class="card-lib">${esc(doc.lib)}</span>` : '';
    const descLine   = doc.d
      ? `<p class="card-description"><span class="card-desc-label">תיאור: </span>${esc(doc.d)}…</p>`
      : '';

    return `
      <a href="fragment.html?id=${esc(doc.id)}" class="card" role="listitem"
         aria-label="${esc(doc.s||'מסמך')}">
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
    if (total > 0) grid.innerHTML = slice.map(cardHTML).join('');

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
      query = ''; searchInput.value = ''; clearBtn.hidden = true; applyFilters();
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

  // ── Boot ──────────────────────────────────────────────────────────────────────
  function init() {
    wire();
    fetch('data/search.json')
      .then(r => { if(!r.ok) throw new Error(r.status); return r.json(); })
      .then(data => {
        allDocs = filtered = data;
        loadingEl.hidden = true;
        populateFilters(data);
        render();
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
