/* Geniza Explorer — progressive image hydration for prerendered document pages.
 *
 * The pages under /d/ are complete without JavaScript: every fact, the
 * description, the tags and the link out to the holding library are already in
 * the HTML. The one thing that cannot be prerendered is the manuscript
 * thumbnail, because its URL only exists inside the institution's IIIF
 * manifest. This fetches that manifest and swaps the image in when it resolves;
 * if it fails, or if JS is off, the page keeps the static placeholder and the
 * link to the digital library.
 */
(function () {
  'use strict';

  const img = document.getElementById('fragment-img');
  if (!img) return;
  const manifestUrl = img.dataset.iiif;
  if (!manifestUrl) return;

  const placeholder = document.querySelector('.image-placeholder');

  function thumbFrom(manifest) {
    const canvas = manifest?.sequences?.[0]?.canvases?.[0];
    if (!canvas) return null;

    const fromManifest = manifest.thumbnail?.['@id'] || manifest.thumbnail;
    if (typeof fromManifest === 'string' && fromManifest.startsWith('http')) return fromManifest;

    const fromCanvas = canvas.thumbnail?.['@id'] || canvas.thumbnail;
    if (typeof fromCanvas === 'string' && fromCanvas.startsWith('http')) return fromCanvas;

    const resource = canvas.images?.[0]?.resource;
    const service = resource?.service?.['@id'] || resource?.service?.id;
    if (service) return service + '/full/500,/0/default.jpg';

    const id = resource?.['@id'];
    if (id) return id.replace('/full/full/', '/full/500,/').replace('/full/max/', '/full/500,/');
    return null;
  }

  const show = (src) => {
    img.src = src;
    img.alt = document.querySelector('.fragment-shelfmark')?.textContent || 'תצלום המסמך';
    img.hidden = false;
    if (placeholder) placeholder.hidden = true;
  };

  const load = () => {
    fetch(manifestUrl, { mode: 'cors', cache: 'force-cache' })
      .then((r) => (r.ok ? r.json() : null))
      .then((m) => {
        const src = m && thumbFrom(m);
        if (src) show(src);
      })
      .catch(() => { /* keep the static placeholder */ });
  };

  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) { io.disconnect(); load(); }
    }, { rootMargin: '200px' });
    io.observe(img.parentElement || img);
  } else {
    load();
  }
})();
