"""Renders the previews of the component library (docs/src/assets/library/*.png).

    python docs/scripts/library_shots.py                 # every component, both themes
    python docs/scripts/library_shots.py button tree     # only some slugs
    python docs/scripts/library_shots.py --theme dark    # only one theme
    python docs/scripts/library_shots.py --variants      # only the variant shots (fast)
    python docs/scripts/library_shots.py --prune         # also delete PNGs no entry uses any more

Each component in ``library_data.py`` has a ``preview`` snippet and optional ``examples`` and
``variants``. The snippet that is shown on the page is the code that draws the image: it runs with
``pz``, ``ui`` and ``draw`` imported, and every other free name (``on_save``, ``open_file``...) is a
do-nothing callback. Its last expression is the widget. Images are drawn off-screen with
``App.screenshot`` at scale 2, centered on the theme background, as ``<slug>.dark.png`` /
``<slug>.light.png`` (examples: ``<slug>-<n>.<theme>.png``, ``n`` from 1), plus
``<slug>.thumb.<theme>.png``: the preview cropped to its content for the gallery cards.

Variants are drawn one by one on a small canvas and cropped tightly to their content plus a margin,
as ``<slug>-v<group>-<n>.<theme>.png`` (both from 1). The page shows them at their natural size, so
a button looks like a button, not like a poster of one. A variant that touches the edge of its
canvas is reported (and the script exits with 1): give it a bigger ``size``.

``main_view()`` stands for the app's own view (a small editor) in overlay and dialog snippets.
The snippets run with the working directory set to a temporary folder that holds ``photo.png`` and
``logo.svg``, so image examples can use those names.

Run ``docs/scripts/optimize_images.py`` afterwards: these PNGs are written quickly, not small.
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
VARIANT_SIZE = (480, 160)
#: Margin around a cropped variant, in image pixels (the shots are 2x, so 20 CSS px).
VARIANT_MARGIN = 40


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


def shown_tooltip(content, text: str, keys: str | None = None, position: str = "bottom"):
    """``content`` with its ``ui.tooltip`` drawn open, as the pointer would show it (for ``draw`` snippets)."""
    t = pz.theme.current()
    tip = pz.container(
        pz.row([pz.text(text, size=12.5, color=t.text, wrap=False), ui.kbd(keys, size="xs") if keys else None],
               spacing=8, align="center"),
        padding=(4, 8), bg=t.elevated, border_color=t.border, border_width=1.0, radius=t.radius,
        shadow=(t.shadow, (0, 2), 8),
    )
    if position in ("top", "bottom"):
        return pz.column([tip, content] if position == "top" else [content, tip], spacing=6, align="center")
    return pz.row([tip, content] if position == "left" else [content, tip], spacing=6, align="center")


def run_snippet(code: str):
    """Runs a library snippet and returns the value of its last expression (the widget)."""
    tree = ast.parse(code)
    ns: dict = {"pz": pz, "ui": ui, "draw": draw, "Path": Path, "main_view": main_view,
                "shown_tooltip": shown_tooltip}
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


def crop_variant(path: Path, margin: int = VARIANT_MARGIN) -> bool:
    """Crops a variant shot to its content plus ``margin``; False when the content touches the edge."""
    from PIL import Image, ImageChops

    image = Image.open(path).convert("RGB")
    background = Image.new("RGB", image.size, image.getpixel((1, 1)))
    box = ImageChops.difference(image, background).point(lambda v: 255 if v > 10 else 0).getbbox()
    if not box:
        raise ValueError(f"{path.name} is blank")
    left, top, right, bottom = box
    clipped = left <= 2 or top <= 2 or right >= image.width - 2 or bottom >= image.height - 2
    left, top = max(left - margin, 0), max(top - margin, 0)
    right, bottom = min(right + margin, image.width), min(bottom + margin, image.height)
    # An even size keeps the 1x version (half the pixels) sharp.
    right -= (right - left) % 2
    bottom -= (bottom - top) % 2
    image.crop((left, top, right, bottom)).save(path, optimize=True)
    return not clipped


def variant_stems(entry: dict):
    """``(file stem, item)`` for every variant of an entry, in page order."""
    for g, group in enumerate(entry.get("variants", ()), start=1):
        for i, item in enumerate(group["items"], start=1):
            yield f"{entry['slug']}-v{g}-{i}", item


def shots(entry: dict, variants: bool = True, others: bool = True):
    """``(file stem, snippet, size, fill, start, kind)`` for a component's preview, examples and variants."""
    if others:
        preview = entry["preview"]
        yield (entry["slug"], preview["code"], tuple(preview.get("size", PREVIEW_SIZE)), preview.get("fill", False),
               preview.get("start"), "preview")
        for i, ex in enumerate(entry.get("examples", ()), start=1):
            if ex.get("shot", True):
                yield (f"{entry['slug']}-{i}", ex["code"], tuple(ex.get("size", EXAMPLE_SIZE)), ex.get("fill", False),
                       ex.get("start"), "example")
    if variants:
        for stem, item in variant_stems(entry):
            fill = item.get("fill", False)
            yield (stem, item.get("draw") or item["code"], tuple(item.get("size") or VARIANT_SIZE), fill,
                   item.get("start"), "framed" if fill else "variant")


def expected_files(entries) -> set:
    """Every PNG name the library uses, in both themes."""
    names = set()
    for entry in entries:
        for stem, *_ in shots(entry):
            names |= {f"{stem}.{key}.png" for key in THEMES}
        names |= {f"{entry['slug']}.thumb.{key}.png" for key in THEMES}
    return names


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("slugs", nargs="*", help="only these components (default: all)")
    parser.add_argument("--theme", choices=sorted(THEMES), help="only this theme (default: both)")
    parser.add_argument("--variants", action="store_true", help="only the variant shots")
    parser.add_argument("--prune", action="store_true", help="delete PNGs that no entry uses")
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
    count, clipped = 0, []
    try:
        for entry in entries:
            for stem, code, size, fill, start, kind in shots(entry, others=not args.variants):
                run_snippet(code)  # fail here: inside the app an error is drawn instead of raised
                for key in [args.theme] if args.theme else THEMES:
                    path = OUT / f"{stem}.{key}.png"
                    Shot(code, THEMES[key], fill, start).screenshot(path, size=size, scale=2)
                    count += 1
                    if kind == "preview":
                        thumbnail(path, OUT / f"{stem}.thumb.{key}.png")
                    elif kind == "variant" and not crop_variant(path) and stem not in clipped:
                        clipped.append(stem)
            print(f"rendered {entry['slug']}")
    finally:
        os.chdir(cwd)
        shutil.rmtree(sandbox, ignore_errors=True)
    print(f"wrote {count} images to {OUT}")
    for stem in clipped:
        print(f"warning: {stem} touches the edge of its canvas (give it a bigger size)")
    if args.prune:
        keep = expected_files(library_data.COMPONENTS)
        stale = [p for p in OUT.glob("*.png") if p.name not in keep]
        for p in stale:
            p.unlink()
        print(f"pruned {len(stale)} unused images")
    return 1 if clipped else 0


if __name__ == "__main__":
    sys.exit(main())
