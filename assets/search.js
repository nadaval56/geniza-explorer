/* Geniza Explorer — Index page search + filter + pagination */
(function () {
  'use strict';

  const PAGE_SIZE = 48;

  // ── State ────────────────────────────────────────────────────────────────────
  let allDocs = [];
  let filtered = [];
  let currentPage = 1;
  let query = '';
  let filterType = '';
  let filterLang = '';
  let filterLib = '';
  let filterHas = '';

  // ── DOM refs ─────────────────────────────────────────────────────────────────
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

  // ── Badge class ───────────────────────────────────────────────────────────────
  const TYPE_BADGE = {
    'מכתב':             'badge-type-letter',
    'Letter':           'badge-type-letter',
    'מסמך משפטי':       'badge-type-legal',
    'Legal document':   'badge-type-legal',
    'טקסט ספרותי':      'badge-type-lit',
    'Literary text':    'badge-type-lit',
    'טקסט דתי':         'badge-type-rel',
    'Religious text':   'badge-type-rel',
    'טקסט פרא-ספרותי':  'badge-type-para',
    'Paraliterary text':'badge-type-para',
  };
  function typeBadgeClass(type) {
    return TYPE_BADGE[type] || 'badge-type-other';
  }

  // ── Helpers ───────────────────────────────────────────────────────────────────
  function esc(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function normalize(str) {
    return (str || '').toLowerCase().replace(/[־‐\-]/g, ' ');
  }

  // ── Populate filter dropdowns ─────────────────────────────────────────────────
  function populateFilters(docs) {
    const types = new Set();
    const langs = new Set();
    const libs  = new Set();

    docs.forEach(d => {
      if (d.th)  types.add(d.th);
      if (d.lh)  (d.lh.split('؛')).forEach(l => { const t = l.trim(); if (t) langs.add(t); });
      if (d.lib) libs.add(d.lib);
    });

    const fill = (sel, items) => {
      const first = sel.options[0].outerHTML;
      sel.innerHTML = first;
      [...items].sort().forEach(v => {
        const o = document.createElement('option');
        o.value = v; o.textContent = v;
        sel.appendChild(o);
      });
    };

    fill(selType, types);
    fill(selLang, langs);
    fill(selLib, libs);
  }

  // ── Filter + search ───────────────────────────────────────────────────────────
  function applyFilters() {
    const q = normalize(query);

    filtered = allDocs.filter(d => {
      if (filterType && d.th !== filterType) return false;
      if (filterLang && !d.lh.includes(filterLang)) return false;
      if (filterLib  && d.lib !== filterLib) return false;
      if (filterHas === 'img' && !d.img) return false;
      if (filterHas === 'tr'  && !d.tr)  return false;
      if (filterHas === 'tl'  && !d.tl)  return false;

      if (q) {
        const haystack = normalize(
          [d.s||'', d.th||'', d.lh||'', d.or||'', d.dt||'', d.lib||'', d.d||''].join(' ')
        );
        // All words must appear
        const words = q.split(/\s+/).filter(Boolean);
        return words.every(w => haystack.includes(w));
      }
      return true;
    });

    currentPage = 1;
    render();
  }

  // ── Card HTML ─────────────────────────────────────────────────────────────────
  function cardHTML(doc) {
    const badgeClass = typeBadgeClass(doc.th || '');
    const icons = [
      doc.img ? '<span class="card-icon" title="תמונה זמינה">🖼</span>' : '',
      doc.tr  ? '<span class="card-icon" title="תמלול זמין">📝</span>' : '',
      doc.tl  ? '<span class="card-icon" title="תרגום זמין">🌐</span>' : '',
    ].join('');

    const langBadge = doc.lh
      ? `<span class="badge badge-lang">${esc(doc.lh.split('؛')[0].trim())}</span>`
      : '';

    const datePart   = doc.dt ? `<span class="card-date">${esc(doc.dt)}</span>` : '';
    const originPart = doc.or ? `<span class="card-origin">${esc(doc.or)}</span>` : '';
    const description = doc.d ? `<p class="card-description">${esc(doc.d)}</p>` : '';

    return `
      <a href="fragment.html?id=${esc(doc.id)}" class="card" role="listitem"
         aria-label="${esc(doc.s)}">
        <div class="card-top">
          <span class="card-shelfmark">${esc(doc.s) || 'PGPID ' + esc(doc.id)}</span>
          <span class="card-icons" aria-hidden="true">${icons}</span>
        </div>
        <div class="card-meta">
          <span class="badge ${badgeClass}">${esc(doc.th)}</span>
          ${langBadge}
        </div>
        ${datePart || originPart
          ? `<div class="card-meta">${datePart}${originPart}</div>` : ''}
        ${description}
        <div class="card-footer">${esc(doc.lib || '')}</div>
      </a>`;
  }

  // ── Render ────────────────────────────────────────────────────────────────────
  function render() {
    const total = filtered.length;
    const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    currentPage = Math.min(currentPage, pages);

    const start = (currentPage - 1) * PAGE_SIZE;
    const slice = filtered.slice(start, start + PAGE_SIZE);

    // Results bar
    if (total === allDocs.length && !query && !filterType && !filterLang && !filterLib && !filterHas) {
      resultsBar.innerHTML = `מציג <strong>${allDocs.length.toLocaleString('he')}</strong> מסמכים`;
    } else {
      resultsBar.innerHTML = `נמצאו <strong>${total.toLocaleString('he')}</strong> מסמכים`;
    }

    // Cards
    emptyEl.hidden = total > 0;
    grid.hidden = total === 0;

    if (total > 0) {
      grid.innerHTML = slice.map(cardHTML).join('');
    }

    // Pagination
    renderPagination(pages);
  }

  function renderPagination(pages) {
    if (pages <= 1) { pagination.innerHTML = ''; return; }

    const p = currentPage;
    let html = '';

    // Previous
    html += `<button class="page-btn" ${p === 1 ? 'disabled' : ''} data-page="${p-1}" aria-label="עמוד קודם">→</button>`;

    // Page numbers: always show first, last, and ±2 around current
    const shown = new Set();
    [1, 2, p-2, p-1, p, p+1, p+2, pages-1, pages].forEach(n => {
      if (n >= 1 && n <= pages) shown.add(n);
    });
    let prev = 0;
    [...shown].sort((a,b)=>a-b).forEach(n => {
      if (prev && n > prev + 1) html += '<span class="page-btn" style="pointer-events:none;opacity:.3">…</span>';
      html += `<button class="page-btn ${n === p ? 'active' : ''}" data-page="${n}">${n}</button>`;
      prev = n;
    });

    // Next
    html += `<button class="page-btn" ${p === pages ? 'disabled' : ''} data-page="${p+1}" aria-label="עמוד הבא">←</button>`;

    pagination.innerHTML = html;
  }

  // ── Event wiring ─────────────────────────────────────────────────────────────
  function wireEvents() {
    let debounceTimer;
    searchInput.addEventListener('input', () => {
      query = searchInput.value;
      clearBtn.hidden = !query;
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(applyFilters, 220);
    });

    clearBtn.addEventListener('click', () => {
      searchInput.value = '';
      query = '';
      clearBtn.hidden = true;
      applyFilters();
    });

    selType.addEventListener('change', () => { filterType = selType.value; applyFilters(); });
    selLang.addEventListener('change', () => { filterLang = selLang.value; applyFilters(); });
    selLib.addEventListener('change',  () => { filterLib  = selLib.value;  applyFilters(); });
    selHas.addEventListener('change',  () => { filterHas  = selHas.value;  applyFilters(); });

    pagination.addEventListener('click', e => {
      const btn = e.target.closest('[data-page]');
      if (!btn || btn.disabled) return;
      currentPage = +btn.dataset.page;
      render();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  // ── Bootstrap ─────────────────────────────────────────────────────────────────
  function init() {
    wireEvents();
    fetch('data/search.json')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(data => {
        allDocs = data;
        filtered = data;
        loadingEl.hidden = true;
        populateFilters(data);
        render();
      })
      .catch(err => {
        loadingEl.hidden = true;
        grid.innerHTML = `
          <div style="grid-column:1/-1;text-align:center;padding:3rem;color:var(--text-3)">
            <p style="font-size:2rem;margin-bottom:.5rem">⚠️</p>
            <p>לא ניתן לטעון את הנתונים.</p>
            <p style="font-size:.85rem;margin-top:.5rem">
              הריצו תחילה: <code>python build.py</code>
            </p>
          </div>`;
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
