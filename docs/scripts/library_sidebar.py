"""Writes the Library sidebar, grouped by category (docs/src/lib/library-sidebar.json).

    python docs/scripts/library_sidebar.py           # write it
    python docs/scripts/library_sidebar.py --check   # fail if it is out of date

``astro.config.mjs`` reads the file and shows the components of ``library_data.py`` in one sidebar group per
category (Layout, Forms, System...), in the order of ``CATEGORIES``, each sorted by name. ``gen_library.py``
writes and checks it too, so a new component lands in its group with the rest of its page.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "src" / "lib" / "library-sidebar.json"
sys.path.insert(0, str(HERE))

import library_data  # noqa: E402


def groups() -> list:
    """``[{"key", "label": {"en", "es"}, "items": ["library/<slug>", ...]}]``, one per category in use."""
    out = []
    for key, label in library_data.CATEGORIES.items():
        entries = sorted((e for e in library_data.COMPONENTS if e["category"] == key),
                         key=lambda e: e["name"]["en"].casefold())
        if entries:
            out.append({"key": key, "label": dict(label), "items": [f"library/{e['slug']}" for e in entries]})
    return out


def render() -> str:
    return json.dumps(groups(), ensure_ascii=False, indent="\t") + "\n"


def stale() -> bool:
    return not OUT.exists() or OUT.read_text(encoding="utf-8") != render()


def write() -> None:
    OUT.write_text(render(), encoding="utf-8")


if __name__ == "__main__":
    if "--check" in sys.argv[1:]:
        if stale():
            print(f"{OUT.relative_to(HERE.parent.parent)} is out of date (run library_sidebar.py)")
            sys.exit(1)
        sys.exit(0)
    write()
    print(f"wrote {OUT.relative_to(HERE.parent.parent)}")
