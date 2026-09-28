#!/usr/bin/env python3
"""
og_images.py — the image behind each document's share preview.

A link to d/<id>.html shared on WhatsApp, Telegram or Facebook shows whatever
the page's og:image points at. For every document with a photograph that should
be the manuscript, not the site's logo card. The catch is that what the data
holds for a photograph (iiif_urls) is a IIIF *manifest* — a JSON description of
the item — and not an image. The image lives behind the IIIF Image API service
the manifest names for each page.

This script reads each manifest once, takes the service of the first page, and
writes PGPID → service to data/og_images.json. prerender.py turns a service
into `<service>/full/!1200,630/0/default.jpg`. It is kept out of the build on
purpose: 31,000 requests to a dozen library servers on every deploy would make
the site's publication hostage to the slowest of them. A workflow runs it on
demand and monthly (.github/workflows/og-images.yml) and commits the result.

Resumable: a document already in the file is not fetched again unless
--refresh. A manifest that cannot be read is simply left out, and its page
keeps the site's own preview card.

    python3 scripts/og_images.py --limit 50
    python3 scripts/og_images.py --workers 16
"""

import argparse
import json
import pathlib
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "data" / "docs"
OUT = ROOT / "data" / "og_images.json"
UA = "geniza-explorer-og-images (+https://geniza.co.il/)"
# An image URL given instead of a manifest (the National Library of Israel does
# this for one document): the service is everything before /full/…
IMAGE_URL = re.compile(r"^(https?://.+?)/full/[^/]+/[^/]+/default\.(?:jpg|png)$")


def first(x):
    return x[0] if isinstance(x, list) and x else x


def service_id(svc):
    svc = first(svc)
    if isinstance(svc, dict):
        return svc.get("@id") or svc.get("id")
    return None


def first_page_service(manifest):
    """IIIF Presentation 2 or 3 → the Image API service of the first canvas."""
    # Presentation 2: sequences → canvases → images → resource.service
    seq = first(manifest.get("sequences"))
    if isinstance(seq, dict):
        canvas = first(seq.get("canvases"))
        if isinstance(canvas, dict):
            image = first(canvas.get("images"))
            if isinstance(image, dict):
                sid = service_id((image.get("resource") or {}).get("service"))
                if sid:
                    return sid
    # Presentation 3: items → items (AnnotationPage) → items (Annotation) → body.service
    canvas = first(manifest.get("items"))
    if isinstance(canvas, dict):
        page = first(canvas.get("items"))
        if isinstance(page, dict):
            anno = first(page.get("items"))
            if isinstance(anno, dict):
                body = first(anno.get("body"))
                if isinstance(body, dict):
                    sid = service_id(body.get("service"))
                    if sid:
                        return sid
    return None


def resolve(url, timeout=30):
    m = IMAGE_URL.match(url)
    if m:
        return m.group(1)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                manifest = json.loads(r.read().decode("utf-8", "replace"))
            sid = first_page_service(manifest)
            return sid.rstrip("/") if sid else None
        except (json.JSONDecodeError, ValueError):
            return None          # not a manifest (a viewer page, for one)
        except Exception:        # noqa: BLE001 — network: retry, then give up
            time.sleep(2 * (attempt + 1))
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--refresh", action="store_true", help="re-resolve documents already known")
    ap.add_argument("--max-minutes", type=float, default=0,
                    help="stop taking new manifests after this long; what was resolved is kept")
    args = ap.parse_args()

    known = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    live, todo = set(), []
    for path in DOCS_DIR.glob("*.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        url = (doc.get("iiif_urls") or [None])[0]
        if not url:
            continue
        live.add(doc["id"])
        if args.refresh or doc["id"] not in known:
            todo.append((doc["id"], url))
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(live):,} documents with a photograph, {len(known):,} known, {len(todo):,} to resolve")

    lock = threading.Lock()
    done = found = 0

    def save():
        # Documents that left the collection leave the file too.
        data = {k: v for k, v in known.items() if k in live}
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=0, sort_keys=True) + "\n",
                       encoding="utf-8")

    # A time budget, so a slow library cannot run the job into the workflow's
    # timeout — a killed job never reaches the commit step and loses everything.
    # Work not started when the budget runs out is skipped, and the next run,
    # which only fetches what the file lacks, picks it up.
    deadline = time.time() + args.max_minutes * 60 if args.max_minutes else None

    def job(url):
        if deadline and time.time() > deadline:
            return None, True
        return resolve(url), False

    skipped = 0
    with ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(job, url): doc_id for doc_id, url in todo}
        for fut in as_completed(futs):
            doc_id = futs[fut]
            sid, late = fut.result()
            if late:
                skipped += 1
                continue
            with lock:
                done += 1
                if sid:
                    known[doc_id] = sid
                    found += 1
                elif args.refresh:
                    known.pop(doc_id, None)
                if done % 1000 == 0:
                    save()
                    print(f"  {done:,}/{len(todo):,}  resolved {found:,}", flush=True)
    save()
    print(f"resolved {found:,} of {len(todo) - skipped:,} tried"
          + (f", {skipped:,} left for the next run (time budget)" if skipped else "")
          + f"; {len({k for k in known if k in live}):,} in the file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
