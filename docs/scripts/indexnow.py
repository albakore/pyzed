"""Tells search engines which pages of the docs are new or changed, with IndexNow (https://www.indexnow.org).

Bing (which also feeds ChatGPT search, Copilot and DuckDuckGo), Yandex, Seznam, Naver and Yep share one endpoint,
so a submission reaches all of them and the pages are crawled within hours instead of weeks.

    python docs/scripts/indexnow.py changes docs/dist changed.txt   # after `npm run build`
    python docs/scripts/indexnow.py submit changed.txt              # after the site is deployed

``changes`` hashes every page listed in the sitemap, writes the hashes to ``dist/page-hashes.json`` (published
with the site) and lists the pages whose hash differs from the live site's copy: all of them the first time.
``submit`` posts that list. The key is public by design: ``docs/public/<KEY>.txt`` proves the site is ours.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

KEY = "1b7e9343147f62edacf0f8ff370c2707"
HOST = "albakore.github.io"
SITE = f"https://{HOST}/pyzed/"
ENDPOINT = "https://api.indexnow.org/indexnow"
HASHES = "page-hashes.json"


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "pyzed-docs-indexnow"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def page_hashes(dist: Path) -> dict[str, str]:
    """The sha256 of every page in the sitemap, by URL."""
    hashes = {}
    for sitemap in sorted(dist.glob("sitemap-*.xml")):
        if sitemap.name == "sitemap-index.xml":
            continue
        for url in re.findall(r"<loc>([^<]+)</loc>", sitemap.read_text(encoding="utf-8")):
            path = dist / url.removeprefix(SITE)
            page = path / "index.html" if url.endswith("/") else path
            if page.is_file():
                hashes[url] = hashlib.sha256(page.read_bytes()).hexdigest()
    return hashes


def changes(dist: Path, out: Path) -> None:
    hashes = page_hashes(dist)
    (dist / HASHES).write_text(json.dumps(hashes, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    try:
        live = json.loads(_get(SITE + HASHES))
    except (urllib.error.URLError, ValueError, TimeoutError):
        live = {}  # first deploy, or the site is down: every page is new
    changed = [url for url, digest in hashes.items() if live.get(url) != digest]
    out.write_text("".join(f"{url}\n" for url in changed), encoding="utf-8")
    print(f"indexnow: {len(changed)} of {len(hashes)} pages are new or changed")


def submit(listing: Path) -> None:
    urls = [line.strip() for line in listing.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not urls:
        print("indexnow: nothing to submit")
        return
    for start in range(0, len(urls), 10_000):  # the protocol's limit per request
        body = json.dumps({"host": HOST, "key": KEY, "keyLocation": f"{SITE}{KEY}.txt",
                           "urlList": urls[start:start + 10_000]}).encode()
        request = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                         headers={"Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(request, timeout=30) as response:
            print(f"indexnow: submitted {len(urls[start:start + 10_000])} URLs ({response.status})")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "changes":
        changes(Path(sys.argv[2]), Path(sys.argv[3]))
    elif len(sys.argv) == 3 and sys.argv[1] == "submit":
        submit(Path(sys.argv[2]))
    else:
        sys.exit(__doc__)
