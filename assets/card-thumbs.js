/* Geniza Explorer — manuscript thumbnails for prerendered card grids (/t/).
 *
 * The tag hubs render the same card markup the home page builds in search.js,
 * but they are static HTML, so nothing hydrates the thumbnails. This does the
 * one job search.js would have done: for each card that names an IIIF manifest,
 * fetch it when the card approaches the viewport and swap the image in.
 *
 * Lazy on purpose. A hub lists up to 100 documents, and firing a hundred
 * requests at the holding libraries on page load would be rude to them and slow
 * for the reader. Only cards that are actually scrolled to ever ask.
 *
 * Without JavaScript, or when a manifest fails, the card simply has no image —
 * every fact on it is already in the HTML. The privacy policy documents these
 * requests: they go to the holding library, not to this site.
 */
(function () {
  'use strict';

  const cards = document.querySelectorAll('.card-thumb[data-iu]');
  if (!cards.length || !('IntersectionObserver' in window)) return;

  function thumbFrom(manifest) {
    const canvas = manifest?.sequences?.[0]?.canvases?.[0];
    if (!canvas) return null;

    const fromManifest = manifest.thumbnail?.['@id'] || manifest.thumbnail;
    if (typeof fromManifest === 'string' && fromManifest.startsWith('http')) return fromManifest;

    const fromCanvas = canvas.thumbnail?.['@id'] || canvas.thumbnail;
    if (typeof fromCanvas === 'string' && fromCanvas.startsWith('http')) return fromCanvas;

    const resource = canvas.images?.[0]?.resource;
    const service = resource?.service?.['@id'] || resource?.service?.id;
    if (service) return service + '/full/400,/0/default.jpg';

    const id = resource?.['@id'];
    if (id) return id.replace('/full/full/', '/full/400,/').replace('/full/max/', '/full/400,/');
    return null;
  }

  const load = (img) => {
    const manifestUrl = img.dataset.iu;
    if (!manifestUrl) return;
    delete img.dataset.iu;

    fetch(manifestUrl, { mode: 'cors', cache: 'force-cache' })
      .then((r) => (r.ok ? r.json() : null))
      .then((m) => {
        const src = m && thumbFrom(m);
        if (!src) return;
        img.src = src;
        img.hidden = false;
      })
      .catch(() => { /* the card stands on its own without a picture */ });
  };

  const io = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      io.unobserve(entry.target);
      load(entry.target);
    }
  }, { rootMargin: '300px' });

  cards.forEach((img) => io.observe(img));
})();
