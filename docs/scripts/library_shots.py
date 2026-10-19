"""Renders the previews of the component library (docs/src/assets/library/*.png).

    python docs/scripts/library_shots.py                 # every component, both themes
    python docs/scripts/library_shots.py button tree     # only some slugs
    python docs/scripts/library_shots.py --theme dark    # only one theme

Each component in ``library_data.py`` has a ``preview`` snippet and optional ``examples``. The
snippet that is shown on the page is the code that draws the image: it runs with ``pz``, ``ui``
and ``draw`` imported, and every other free name (``on_save``, ``open_file``...) is a do-nothing
callback. Its last expression is the widget. Images are drawn off-screen with ``App.screenshot``
at scale 2, centered on the theme background, as ``<slug>.dark.png`` / ``<slug>.light.png``
(examples: ``<slug>-<n>.<theme>.png``, ``n`` from 1), plus ``<slug>.thumb.<theme>.png``: the preview
cropped to its content for the gallery cards.

``main_view()`` stands for the app's own view (a small editor) in overlay and dialog snippets.
The snippets run with the working directory set to a temporary folder that holds ``photo.png`` and
``logo.svg``, so image examples can use those names.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE.parent / "src" / "assets" / "library"
sys.path.insert(0, str(HERE))

import pyzed as pz  # noqa: E402
from pyzed import draw, ui  # noqa: E402

import library_data  # noqa: E402

ui.base.KEY_STYLE = "words"
THEMES = {"dark": "One Dark", "light": "One Light"}
PREVIEW_SIZE = (720, 360)
EXAMPLE_SIZE = (720, 200)


def noop(*_args, **_kwargs):
    return None


MAIN_CODE = '''import pyzed as pz
from pyzed import ui


class Notes(pz.App):
    def __init__(self):
        self.notes = []

    def view(self):
        return ui.list_item("New note", self.add, icon="plus")
'''


def main_view():
    """Stands for "your app's view" in overlay snippets: a small editor filling the space."""
    return pz.container(ui.editor("library-main-view", MAIN_CODE, path="notes.py"), width="fill", height="fill")


def run_snippet(code: str):
    """Runs a library snippet and returns the value of its last expression (the widget)."""
    tree = ast.parse(code)
    ns: dict = {"pz": pz, "ui": ui, "draw": draw, "Path": Path, "main_view": main_view}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in ns and not hasattr(builtins, node.id):
            ns[node.id] = noop  # a callback the reader would write; assignments overwrite it
    *body, last = tree.body
    if not isinstance(last, ast.Expr):
        raise ValueError("a library snippet must end with an expression (the widget)")
    exec(compile(ast.Module(body=body, type_ignores=[]), "<snippet>", "exec"), ns)
    return eval(compile(ast.Expression(last.value), "<snippet>", "eval"), ns)


class Shot(pz.App):
    def __init__(self, code: str, theme: str, fill: bool = False, start: str | None = None):
        self.code, self.fill, self.start = code, fill, start
        self.theme = pz.themes.get(theme)

    def on_start(self):
        return run_snippet(self.start) if self.start else None

    def view(self):
        t = self.resolved_theme()
        widget = run_snippet(self.code)
        if self.fill:
            return pz.container(widget, width="fill", height="fill", bg=t.background)
        return pz.container(widget, center=True, padding=24, width="fill", height="fill", bg=t.editor)


def thumbnail(src: Path, dst: Path, margin: int = 48) -> None:
    """Crops a preview to its content (plus a margin) at a 2:1 ratio, for the gallery cards."""
    from PIL import Image, ImageChops

    image = Image.open(src).convert("RGB")
    background = Image.new("RGB", image.size, image.getpixel((2, 2)))
    box = ImageChops.difference(image, background).point(lambda v: 255 if v > 12 else 0).getbbox()
    if not box:
        image.save(dst)
        return
    left, top, right, bottom = box
    w, h = right - left + 2 * margin, bottom - top + 2 * margin
    w, h = max(w, 2 * h, 480), max(h, w // 2)
    w, h = min(w, image.width), min(h, image.height)
    cx, cy = (left + right) // 2, (top + bottom) // 2
    x = min(max(cx - w // 2, 0), image.width - w)
    y = min(max(cy - h // 2, 0), image.height - h)
    image.crop((x, y, x + w, y + h)).save(dst, optimize=True)


def shots(entry: dict):
    """``(file stem, snippet, size, fill, start)`` for a component's preview and examples."""
    preview = entry["preview"]
    yield (entry["slug"], preview["code"], tuple(preview.get("size", PREVIEW_SIZE)), preview.get("fill", False),
           preview.get("start"))
    for i, ex in enumerate(entry.get("examples", ()), start=1):
        if ex.get("shot", True):
            yield (f"{entry['slug']}-{i}", ex["code"], tuple(ex.get("size", EXAMPLE_SIZE)), ex.get("fill", False),
                   ex.get("start"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("slugs", nargs="*", help="only these components (default: all)")
    parser.add_argument("--theme", choices=sorted(THEMES), help="only this theme (default: both)")
    args = parser.parse_args()

    entries = library_data.COMPONENTS
    if args.slugs:
        known = {e["slug"] for e in entries}
        unknown = set(args.slugs) - known
        if unknown:
            parser.error(f"unknown slugs: {', '.join(sorted(unknown))}")
        entries = [e for e in entries if e["slug"] in args.slugs]

    OUT.mkdir(parents=True, exist_ok=True)
    sandbox = Path(tempfile.mkdtemp(prefix="pyzed-library-"))
    shutil.copy(ROOT / "docs" / "screenshots" / "zed-one-dark.png", sandbox / "photo.png")
    shutil.copy(HERE.parent / "src" / "assets" / "logo.svg", sandbox / "logo.svg")
    cwd = os.getcwd()
    os.chdir(sandbox)
    count = 0
    try:
        for entry in entries:
            for stem, code, size, fill, start in shots(entry):
                run_snippet(code)  # fail here: inside the app an error is drawn instead of raised
                for key in [args.theme] if args.theme else THEMES:
                    Shot(code, THEMES[key], fill, start).screenshot(OUT / f"{stem}.{key}.png", size=size, scale=2)
                    count += 1
                    if stem == entry["slug"]:
                        thumbnail(OUT / f"{stem}.{key}.png", OUT / f"{stem}.thumb.{key}.png")
            print(f"rendered {entry['slug']}")
    finally:
        os.chdir(cwd)
        shutil.rmtree(sandbox, ignore_errors=True)
    print(f"wrote {count} images to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
