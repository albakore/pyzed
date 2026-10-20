"""Records the animated previews of the component library (docs/public/library/*.webp).

    python docs/scripts/library_shots.py                 # every component, both themes
    python docs/scripts/library_shots.py button tree     # only some slugs
    python docs/scripts/library_shots.py --theme dark    # only one theme
    python docs/scripts/library_shots.py --variants      # only the variant clips
    python docs/scripts/library_shots.py --no-variants   # only the previews and examples
    python docs/scripts/library_shots.py --only select-v1-1 select-v2-3  # only some clips
    python docs/scripts/library_shots.py --jobs 4        # in 4 processes
    python docs/scripts/library_shots.py --probe button  # print what the scripts can aim at
    python docs/scripts/library_shots.py --prune         # also delete files no entry uses any more

Each component in ``library_data.py`` has a ``preview`` snippet and optional ``examples`` and
``variants``. The snippet shown on the page is the code that draws the clip: it runs with ``pz``,
``ui`` and ``draw`` imported, and every other free name (``on_save``, ``open_file``...) is a
do-nothing callback. Its last expression is the widget.

Clips are recorded off-screen with ``anim_webp.py`` (a scripted pointer, keyboard and clock; see
``docs/src/content/docs/contributing/docs.md``, "Animated captures"), at scale 2:

* ``<slug>.<theme>.webp``: the preview, playing the component's script from ``library_anim.py``
  (hover, press, type, drag...) with the pointer drawn. ``<slug>-<n>.<theme>.webp``: the examples.
* ``<slug>.thumb.<theme>.webp``: the preview cropped to its content (2:1) for the gallery cards.
* ``<slug>-v<group>-<n>.<theme>.webp``: each variant on a small canvas, cropped to its content plus
  a margin, hovered and pressed (or clicked and typed into, when it has a text field). When what it
  draws reaches the edge (an open menu), it is recorded again on a bigger canvas before the crop.

A clip in which nothing changes (a label, a badge) plays a theme cycle instead: the same widget in
four themes. Every clip also gets a still first frame, ``*.still.webp``, shown when the reader asks
for reduced motion. ``manifest.json`` lists every file with its size, for the page's width/height.

The snippets are made stateful while they are recorded: the value a ``ui.switch``, ``ui.input``,
``ui.slider``, ``ui.select``... is given is replaced by the last value its callback received
(``LiveUI``), so a click toggles the switch and typed text shows up, as in a real app.

``main_view()`` stands for the app's own view (a small editor) in overlay and dialog snippets.
The snippets run with the working directory set to a temporary folder that holds ``photo.png`` and
``logo.svg``, so image examples can use those names.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import inspect
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE.parent / "public" / "library"
MANIFEST = OUT / "manifest.json"
sys.path.insert(0, str(HERE))

import anim_webp as aw
import library_anim
import library_data
import pyzed as pz
from pyzed import draw, ui

ui.base.KEY_STYLE = "words"
THEMES = {"dark": "One Dark", "light": "One Light"}
CYCLE = {"dark": aw.DARK_THEMES, "light": aw.LIGHT_THEMES}
PREVIEW_SIZE = (720, 360)
EXAMPLE_SIZE = (720, 200)
VARIANT_SIZE = (480, 160)
#: Margin around a cropped variant, in image pixels (the clips are 2x, so 20 CSS px).
VARIANT_MARGIN = 40
#: How much a variant's canvas grows (logical pixels) when what it draws reaches the edge, and how often.
GROW_STEP = (240, 160)
GROW_TRIES = 3
PREVIEW_FPS = 20
VARIANT_FPS = 15
THUMB_SIZE = (480, 240)


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


# -- stateful snippets -----------------------------------------------------------------------------
#: ``ui`` functions whose value comes back through a callback: (value parameter, callback, how).
#: "set" stores what the callback receives; "member" toggles it in a set (accordion, tree).
STATEFUL = {
    "switch": [("checked", "on_toggle", "set")],
    "checkbox": [("checked", "on_toggle", "set")],
    "slider": [("value", "on_change", "set")],
    "input": [("value", "on_input", "set")],
    "search_input": [("value", "on_input", "set")],
    "number_field": [("value", "on_change", "set")],
    "select": [("selected", "on_select", "set")],
    "radio_group": [("selected", "on_select", "set")],
    "segmented": [("selected", "on_select", "set")],
    "toggle_group": [("selected", "on_select", "set")],
    "disclosure": [("open", "on_toggle", "set")],
    "tab_bar": [("active", "on_select", "set")],
    "prompt": [("value", "on_input", "set")],
    "picker": [("query", "on_query", "set")],
    "command_palette": [("query", "on_query", "set")],
    "shortcuts": [("query", "on_query", "set")],
    "console": [("query", "on_query", "set"), ("hidden", "on_toggle_level", "member")],
    "accordion": [("open", "on_toggle", "member")],
    "split": [("ratio", "on_resize", "set")],
    "tree": [("expanded", "on_toggle", "member"), ("selected", "on_select", "set")],
}


class LiveUI:
    """``pyzed.ui`` with the stateful widgets above remembering their value between views.

    Widgets are told apart by the order they are built in (the n-th ``ui.switch`` of the view),
    which is stable for a snippet. ``reset()`` starts a view.
    """

    def __init__(self):
        self.store: dict = {}
        self.counts: dict = {}

    def reset(self):
        self.counts = {}

    def __getattr__(self, name):
        real = getattr(ui, name)
        rules = STATEFUL.get(name)
        if not rules:
            return real
        signature = inspect.signature(real)

        def live(*args, **kwargs):
            n = self.counts.get(name, 0)
            self.counts[name] = n + 1
            bound = signature.bind_partial(*args, **kwargs)
            for value_name, callback_name, how in rules:
                key = (name, n, value_name)
                if key in self.store:
                    bound.arguments[value_name] = self.store[key]
                original = bound.arguments.get(callback_name)
                if original is None:
                    continue
                current = bound.arguments.get(value_name)

                def callback(*args, _key=key, _how=how, _orig=original, _current=current):
                    if _how == "member":
                        members = set(self.store.get(_key, _current) or ())
                        members ^= {args[0]}
                        self.store[_key] = members
                    elif args:
                        self.store[_key] = args[0]
                    else:  # a toggle that passes nothing (ui.disclosure): flip it
                        self.store[_key] = not self.store.get(_key, _current)
                    return _orig(*args)

                bound.arguments[callback_name] = callback
            return real(*bound.args, **bound.kwargs)

        return live


def run_snippet(code: str, live: LiveUI | None = None):
    """Runs a library snippet and returns the value of its last expression (the widget)."""
    tree = ast.parse(code)
    ns: dict = {"pz": pz, "ui": live if live is not None else ui, "draw": draw, "Path": Path,
                "main_view": main_view, "shown_tooltip": shown_tooltip, "clip_time": aw.clip_time}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in ns and not hasattr(builtins, node.id):
            ns[node.id] = noop  # a callback the reader would write; assignments overwrite it
    *body, last = tree.body
    if not isinstance(last, ast.Expr):
        raise ValueError("a library snippet must end with an expression (the widget)")
    # Named like a reader's file, so the error cards and dialogs drawn from a snippet say "app.py:3".
    exec(compile(ast.Module(body=body, type_ignores=[]), "app.py", "exec"), ns)
    return eval(compile(ast.Expression(last.value), "app.py", "eval"), ns)


class Shot(pz.App):
    def __init__(self, code: str, theme: str, fill: bool = False, start: str | None = None):
        self.code, self.fill, self.start = code, fill, start
        self.theme = pz.themes.get(theme)
        self.live = LiveUI()

    def on_start(self):
        return run_snippet(self.start) if self.start else None

    def view(self):
        t = self.resolved_theme()
        self.live.reset()
        widget = run_snippet(self.code, self.live)
        if self.fill:
            return pz.container(widget, width="fill", height="fill", bg=t.background)
        return pz.container(widget, center=True, padding=24, width="fill", height="fill", bg=t.editor)


# -- clips -----------------------------------------------------------------------------------------
def theme_cycle(key: str, hold: float = 1000) -> list:
    """Steps that show the widget in four themes (for clips in which nothing else moves)."""
    names = CYCLE[key]
    steps = [aw.wait(hold)]
    for name in names[1:]:
        steps += [aw.theme(name), aw.wait(hold)]
    return steps


def auto_variant():
    """A variant's default script: click its text field and type, or hover and press it."""

    def run(ctx):
        found = yield from ctx.probe()
        if any(f[0] == "input" for f in found):
            steps = [aw.wait(300), aw.press("input"), aw.type_text("Pyzed", cps=10), aw.wait(500), aw.leave()]
        else:
            steps = [aw.wait(300), aw.hover("center", hold=500), aw.press(hold=200, after=400), aw.leave(), aw.wait(300)]
        for step in steps:
            yield from step.run(ctx)

    return aw.Step(run, "auto_variant()")


def thumbnail_box(image, margin: int = 48) -> tuple[int, int, int, int]:
    """The preview cropped to its content (plus a margin) at a 2:1 ratio, for the gallery cards."""
    box = aw.content_box(image, threshold=12)
    if not box:
        return (0, 0, image.width, image.height)
    left, top, right, bottom = box
    w, h = right - left + 2 * margin, bottom - top + 2 * margin
    w, h = max(w, 2 * h, 480), max(h, w // 2)
    w, h = min(w, image.width), min(h, image.height)
    cx, cy = (left + right) // 2, (top + bottom) // 2
    x = min(max(cx - w // 2, 0), image.width - w)
    y = min(max(cy - h // 2, 0), image.height - h)
    return (x, y, x + w, y + h)


def variant_stems(entry: dict):
    """``(file stem, item)`` for every variant of an entry, in page order."""
    for g, group in enumerate(entry.get("variants", ()), start=1):
        for i, item in enumerate(group["items"], start=1):
            yield f"{entry['slug']}-v{g}-{i}", item


def shots(entry: dict, variants: bool = True, others: bool = True):
    """``(file stem, snippet, size, fill, start, kind, steps)`` for a component's clips."""
    script = library_anim.SCRIPTS.get(entry["slug"], {})
    if others:
        preview = entry["preview"]
        yield (entry["slug"], script.get("code", preview["code"]), tuple(preview.get("size", PREVIEW_SIZE)),
               preview.get("fill", False), preview.get("start"), "preview", script.get("steps"))
        for i, ex in enumerate(entry.get("examples", ()), start=1):
            if ex.get("shot", True):
                steps = library_anim.EXAMPLES.get(f"{entry['slug']}-{i}")
                yield (f"{entry['slug']}-{i}", ex["code"], tuple(ex.get("size", EXAMPLE_SIZE)), ex.get("fill", False),
                       ex.get("start"), "example", steps)
    if variants:
        for stem, item in variant_stems(entry):
            fill = item.get("fill", False)
            yield (stem, item.get("draw") or item["code"], tuple(item.get("size") or VARIANT_SIZE), fill,
                   item.get("start"), "framed" if fill else "variant", library_anim.VARIANTS.get(stem))


def files_for(stem: str, kind: str) -> list[str]:
    names = []
    for key in THEMES:
        names += [f"{stem}.{key}.webp", f"{stem}.{key}.still.webp"]
        if kind == "preview":
            names += [f"{stem}.thumb.{key}.webp", f"{stem}.thumb.{key}.still.webp"]
    return names


def expected_files(entries) -> set:
    """Every file name the library uses, in both themes."""
    names = set()
    for entry in entries:
        for stem, _code, _size, _fill, _start, kind, _steps in shots(entry):
            names |= set(files_for(stem, kind))
    return names


def grown(frames, size: tuple) -> tuple:
    """``size`` made bigger by ``GROW_STEP`` along each axis where what is drawn reaches the canvas edge."""
    w, h = frames[0].size
    boxes = [b for b in (aw.content_box(f) for f in frames) if b]
    cw, ch = size
    if any(b[0] <= 2 or b[2] >= w - 2 for b in boxes):
        cw += GROW_STEP[0]
    if any(b[1] <= 2 or b[3] >= h - 2 for b in boxes):
        ch += GROW_STEP[1]
    return (cw, ch)


def film(stem, code, size, fill, start, kind, steps, key) -> tuple[dict, list[str]]:
    """Records one clip in one theme; returns its manifest entries and warnings."""
    warnings = []
    small = kind in ("variant", "framed")
    fps = VARIANT_FPS if small else library_anim.SCRIPTS.get(stem, {}).get("fps", PREVIEW_FPS)
    pointer = not small
    if steps is None:
        steps = [auto_variant()] if small else [aw.hover("center"), aw.press(), aw.wait(600), aw.leave()]
    if callable(steps):
        steps = steps(key)
    ctx = aw.record_frames(Shot(code, THEMES[key], fill, start), steps, size=size, fps=fps)
    raw = aw.images(ctx, pointer=False)
    if aw.changes(raw) <= 1:
        ctx = aw.record_frames(Shot(code, THEMES[key], fill, start), theme_cycle(key), size=size, fps=fps)
        raw = aw.images(ctx, pointer=False)
    frames = aw.images(ctx, pointer=pointer) if pointer else raw
    out = {}

    def write(name, clip, rate=fps, quality=80):
        data = aw.encode_webp(clip, OUT / f"{name}.{key}.webp", fps=rate, quality=quality)
        aw.save_poster(clip[0], OUT / f"{name}.{key}.still.webp")
        unique = aw.changes(clip)
        out[f"{name}.{key}"] = {"width": clip[0].width, "height": clip[0].height, "bytes": len(data),
                                "frames": unique, "ms": round(len(clip) * 1000 / rate)}
        if unique <= 1:
            warnings.append(f"{name}.{key}: nothing moves")

    if kind == "variant":
        # An open menu (a select's list, a split button's menu) can reach past the small canvas:
        # record again on a bigger one until everything fits, then crop to the content as usual.
        for _ in range(GROW_TRIES):
            if not aw.touches_edge(raw):
                break
            size = grown(raw, size)
            ctx = aw.record_frames(Shot(code, THEMES[key], fill, start), steps, size=size, fps=fps)
            raw = frames = aw.images(ctx, pointer=False)
        if aw.touches_edge(raw):
            warnings.append(f"{stem}: touches the edge of its canvas (give it a bigger size)")
        box = aw.crop_box(raw, VARIANT_MARGIN)
        frames = [f.crop(box) for f in frames]
    write(stem, frames)
    if kind == "preview":
        box = thumbnail_box(raw[0])
        # Cards are small and many share a page: half the frame rate keeps them light.
        thumbs = [aw.fit_image(f.crop(box), THUMB_SIZE) for f in frames[::2]]
        write(f"{stem}.thumb", thumbs, rate=fps / 2, quality=75)
    return out, warnings


def render_entry(args) -> tuple[str, dict, list[str], float]:
    slug, themes, variants, others, only = args
    entry = next(e for e in library_data.COMPONENTS if e["slug"] == slug)
    started = time.time()
    manifest, warnings = {}, []
    for stem, code, size, fill, start, kind, steps in shots(entry, variants=variants, others=others):
        if only and stem not in only:
            continue
        run_snippet(code)  # fail here: inside the app an error is drawn instead of raised
        for key in themes:
            try:
                got, warned = film(stem, code, size, fill, start, kind, steps, key)
            except LookupError as err:  # a target the script aims at is not in the view
                got, warned = film(stem, code, size, fill, start, kind, None, key)
                warned.append(f"{stem}.{key}: {err}; recorded the default script instead")
            manifest.update(got)
            warnings += warned
    return slug, manifest, warnings, time.time() - started


def sandbox() -> Path:
    folder = Path(tempfile.mkdtemp(prefix="pyzed-library-"))
    shutil.copy(ROOT / "docs" / "screenshots" / "zed-one-dark.png", folder / "photo.png")
    shutil.copy(HERE.parent / "src" / "assets" / "logo.svg", folder / "logo.svg")
    return folder


def _worker_init(folder: str) -> None:
    os.chdir(folder)


def probe(slug: str) -> None:
    """Prints the texts and fields of a component's preview, to aim its script at them."""
    entry = next(e for e in library_data.COMPONENTS if e["slug"] == slug)
    preview = entry["preview"]
    code = library_anim.SCRIPTS.get(slug, {}).get("code", preview["code"])
    found = []

    def grab(ctx):
        found.extend((yield ("probe",)))
        yield from ctx.tick()

    aw.record_frames(Shot(code, "One Dark", preview.get("fill", False), preview.get("start")), [aw.Step(grab)],
                     size=tuple(preview.get("size", PREVIEW_SIZE)))
    for kind, text, x, y, w, h in found:
        if kind != "container":
            print(f"{kind:10} {text[:40]!r:44} center=({x + w / 2:.0f}, {y + h / 2:.0f}) size={w:.0f}x{h:.0f}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("slugs", nargs="*", help="only these components (default: all)")
    parser.add_argument("--theme", choices=sorted(THEMES), help="only this theme (default: both)")
    parser.add_argument("--variants", action="store_true", help="only the variant clips")
    parser.add_argument("--no-variants", action="store_true", help="only the previews and examples")
    parser.add_argument("--only", nargs="+", metavar="STEM", help="only these clips (select-v1-1...)")
    parser.add_argument("--jobs", type=int, default=1, help="processes to record in")
    parser.add_argument("--probe", action="store_true", help="print what each preview's script can aim at")
    parser.add_argument("--prune", action="store_true", help="delete files that no entry uses")
    args = parser.parse_args()

    entries = library_data.COMPONENTS
    if args.slugs:
        known = {e["slug"] for e in entries}
        unknown = set(args.slugs) - known
        if unknown:
            parser.error(f"unknown slugs: {', '.join(sorted(unknown))}")
        entries = [e for e in entries if e["slug"] in args.slugs]

    OUT.mkdir(parents=True, exist_ok=True)
    folder = sandbox()
    cwd = os.getcwd()
    os.chdir(folder)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    warnings: list[str] = []
    try:
        if args.probe:
            for entry in entries:
                print(f"## {entry['slug']}")
                probe(entry["slug"])
            return 0
        themes = [args.theme] if args.theme else list(THEMES)
        only = set(args.only or ())
        if only:
            entries = [e for e in entries if any(stem in only for stem, *_ in shots(e))]
        jobs = [(e["slug"], themes, not args.no_variants, not args.variants, only) for e in entries]
        if args.jobs > 1:
            import multiprocessing

            with multiprocessing.get_context("spawn").Pool(args.jobs, _worker_init, (str(folder),)) as pool:
                results = pool.imap_unordered(render_entry, jobs)
                for slug, got, warned, seconds in results:
                    manifest.update(got)
                    warnings += warned
                    print(f"recorded {slug} ({len(got)} clips, {seconds:.0f}s)", flush=True)
        else:
            for job in jobs:
                slug, got, warned, seconds = render_entry(job)
                manifest.update(got)
                warnings += warned
                print(f"recorded {slug} ({len(got)} clips, {seconds:.0f}s)", flush=True)
    finally:
        os.chdir(cwd)
        shutil.rmtree(folder, ignore_errors=True)
    keep = expected_files(library_data.COMPONENTS)
    manifest = {k: manifest[k] for k in sorted(manifest) if f"{k}.webp" in keep}
    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    total = sum(v["bytes"] for v in manifest.values())
    print(f"{len(manifest)} clips in {MANIFEST.relative_to(ROOT)}, {total / 1e6:.1f} MB of animated WebP")
    for warning in warnings:
        print(f"warning: {warning}")
    if args.prune:
        stale = [p for p in OUT.glob("*.webp") if p.name not in keep]
        for p in stale:
            p.unlink()
        print(f"pruned {len(stale)} unused files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
