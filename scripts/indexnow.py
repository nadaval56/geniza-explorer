#!/usr/bin/env python3
"""
indexnow.py — tell Bing, Yandex, Naver and Seznam which pages just changed.

Google finds changes through sitemap.xml and its own schedule. The IndexNow
engines take a push instead: one POST with a list of URLs, and the pages are
recrawled within hours. Bing's index also serves DuckDuckGo, Ecosia and the
search behind several AI assistants, so this is the cheapest reach the site has.

Runs in CI after every deploy (.github/workflows/deploy.yml). It reads the LIVE
sitemaps, not the build output, so it only ever announces what is actually
published, and it announces each (URL, lastmod) pair once: the pairs already
sent are kept in a state file that CI carries between runs with actions/cache.
Without that, every push of a rewrite batch would re-announce the same pages
until the lastmod manifest is next committed — the pattern IndexNow asks sites
not to produce.

The key is the 32-hex file at the site root (<key>.txt). IndexNow verifies
ownership by fetching it, so it must stay published and must not change.

    python3 scripts/indexnow.py --dry-run
    python3 scripts/indexnow.py --state .cache/indexnow-state.json
"""

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENDPOINT = "https://api.indexnow.org/indexnow"
NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
BATCH = 10_000          # the protocol's per-request maximum
FIRST_RUN_DAYS = 30     # with no state yet, announce only the recent changes


def site_base():
    cname = ROOT / "CNAME"
    host = cname.read_text().strip() if cname.exists() else ""
    if not host:
        sys.exit("CNAME missing — IndexNow needs the site's own host")
    return f"https://{host}/"


def site_key():
    keys = [p for p in ROOT.glob("*.txt") if re.fullmatch(r"[0-9a-f]{32}\.txt", p.name)]
    if len(keys) != 1:
        sys.exit(f"expected one <32-hex>.txt key file at the root, found {len(keys)}")
    return keys[0].stem


def fetch(url):
    # A cache-busting query: GitHub Pages sits behind a CDN, and right after a
    # deploy the old sitemap can still be served from its edge.
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(f"{url}{sep}t={int(time.time())}",
                                 headers={"User-Agent": "geniza-explorer-indexnow"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def live_urls(base):
    index = ET.fromstring(fetch(base + "sitemap.xml"))
    children = [e.text.strip() for e in index.findall("sm:sitemap/sm:loc", NS)]
    pairs = {}
    for child in children:
        tree = ET.fromstring(fetch(child))
        for u in tree.findall("sm:url", NS):
            loc = u.findtext("sm:loc", default="", namespaces=NS).strip()
            mod = u.findtext("sm:lastmod", default="", namespaces=NS).strip()
            if loc:
                pairs[loc] = mod
    return pairs


def submit(base, key, urls):
    host = base.split("/")[2]
    body = json.dumps({"host": host, "key": key,
                       "keyLocation": f"{base}{key}.txt",
                       "urlList": urls}).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--state", default=".cache/indexnow-state.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base, key = site_base(), site_key()
    state_path = pathlib.Path(args.state)
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    first_run = not state

    pairs = live_urls(base)
    if state:
        todo = [u for u, m in pairs.items() if state.get(u) != m]
    else:
        since = (dt.date.today() - dt.timedelta(days=FIRST_RUN_DAYS)).isoformat()
        todo = [u for u, m in pairs.items() if m >= since]
    print(f"{len(pairs):,} live URLs, {len(todo):,} to announce")
    if args.dry_run or not todo:
        for u in todo[:10]:
            print("  ", u, pairs[u])
        return 0

    sent = 0
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        try:
            status = submit(base, key, chunk)
        except Exception as e:  # noqa: BLE001 — urlopen raises on 4xx/5xx
            print(f"  batch {i // BATCH + 1}: failed — {e}")
            break
        print(f"  batch {i // BATCH + 1}: {len(chunk):,} URLs → HTTP {status}")
        if status not in (200, 202):
            break
        for u in chunk:
            state[u] = pairs[u]
        sent += len(chunk)

    # On the first run only the last FIRST_RUN_DAYS were announced. Everything
    # older is recorded as known, or the second run would announce all 36,000.
    if first_run and sent == len(todo):
        for u, m in pairs.items():
            state.setdefault(u, m)
    # Pages that left the site leave the state too, so it does not grow forever.
    state = {u: m for u, m in state.items() if u in pairs}
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, sort_keys=True))
    print(f"announced {sent:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
