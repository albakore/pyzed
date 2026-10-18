"""Rewrite relative links in README.md as absolute GitHub URLs.

PyPI renders the README outside the repository, so relative paths such as
``docs/screenshots/counter.png`` show up as broken images there. The release
workflow runs this right before building, so the published description points
at the files of the released tag:

    python scripts/pypi_readme.py v0.3.0

Images go to raw.githubusercontent.com and other files to github.com/blob.
Absolute URLs, anchors (``#...``) and ``mailto:`` links are left as they are.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = "albakore/pyzed"
README = Path(__file__).resolve().parent.parent / "README.md"
IMAGE = re.compile(r"\.(png|jpe?g|gif|svg|webp)$", re.IGNORECASE)
MARKDOWN_LINK = re.compile(r"(!?\[[^\]]*\]\()([^)\s]+)((?:\s+\"[^\"]*\")?\))")
HTML_ATTR = re.compile(r"""((?:src|href)=["'])([^"']+)(["'])""")


def absolute(url: str, ref: str) -> str:
    if re.match(r"^[a-z][a-z0-9+.-]*:", url, re.IGNORECASE) or url.startswith(("#", "//")):
        return url
    path, _, anchor = url.partition("#")
    path = path.removeprefix("./").lstrip("/")
    if IMAGE.search(path):
        new = f"https://raw.githubusercontent.com/{REPO}/{ref}/{path}"
    else:
        new = f"https://github.com/{REPO}/blob/{ref}/{path}"
    return new + (f"#{anchor}" if anchor else "")


def rewrite(text: str, ref: str) -> str:
    text = MARKDOWN_LINK.sub(lambda m: m[1] + absolute(m[2], ref) + m[3], text)
    return HTML_ATTR.sub(lambda m: m[1] + absolute(m[2], ref) + m[3], text)


def main(argv: list[str]) -> int:
    ref = argv[1] if len(argv) > 1 else "main"
    README.write_text(rewrite(README.read_text(encoding="utf-8"), ref), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
