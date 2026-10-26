"""Records the animated WebP illustrations of the drag and drop docs (docs/public/media/dnd/*.webp).

    python docs/scripts/dnd_shots.py              # every clip
    python docs/scripts/dnd_shots.py kanban wires # only the clips whose name contains a word
    python docs/scripts/dnd_shots.py --list

The apps are the examples in examples/dnd/ (and a few small scenes below), driven off-screen by
anim_webp.py: the pointer presses an item, glides through some points, holds still a moment so
the gap and the landing shadow show, and lets go.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "public" / "media" / "dnd"
EXAMPLES = ROOT / "examples" / "dnd"
os.environ.setdefault("PYZED_CONFIG_DIR", tempfile.mkdtemp(prefix="pyzed-dnd-shots-"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pyzed as pz  # noqa: E402
from anim_webp import Step, ease, images, leave, wait  # noqa: E402
from pyzed.recording import session  # noqa: E402
from pyzed.recording.encode import encode_webp  # noqa: E402
from pyzed import ui  # noqa: E402

#: Each clip should stay under this many bytes.
TARGET = 380_000


def example(name: str):
    """The app class of examples/dnd/<name>.py."""
    spec = importlib.util.spec_from_file_location(f"dnd_{name}", EXAMPLES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return next(v for v in vars(module).values()
                if isinstance(v, type) and issubclass(v, pz.App) and v is not pz.App)


def lift(start, *points, ms: float = 900, hold: float = 450, after: float = 650) -> Step:
    """Presses ``start``, glides through ``points`` (``ms`` for the whole way), waits ``hold`` ms
    over the last one and lets go."""

    def run(ctx):
        a = yield from ctx.resolve(start)
        if ctx.pointer is None:
            ctx.pointer = ctx.entry_point(a)
            yield ("move", *ctx.pointer)
        # The pointer comes to the item first.
        frames = max(1, round(0.35 * ctx.fps))
        b0 = ctx.pointer
        for i in range(1, frames + 1):
            t = ease(i / frames)
            ctx.pointer = (b0[0] + (a[0] - b0[0]) * t, b0[1] + (a[1] - b0[1]) * t)
            yield ("move", *ctx.pointer)
            yield from ctx.tick()
        ctx.pressed = True
        yield ("down", "left")
        yield from ctx.tick()
        per = max(1, round(ms / 1000 * ctx.fps / max(1, len(points))))
        for p in points:  # each one is found when the pointer heads there (a trash can shows up mid-drag)
            to = yield from ctx.resolve(p)
            fr = ctx.pointer
            for i in range(1, per + 1):
                t = ease(i / per)
                ctx.pointer = (fr[0] + (to[0] - fr[0]) * t, fr[1] + (to[1] - fr[1]) * t)
                yield ("move", *ctx.pointer)
                yield from ctx.tick()
        for _ in range(max(1, round(hold / 1000 * ctx.fps))):
            yield ("move", *ctx.pointer)
            yield from ctx.tick()
        ctx.pressed = False
        yield ("up", "left")
        for _ in range(max(1, round(after / 1000 * ctx.fps))):
            yield ("move", *ctx.pointer)
            yield from ctx.tick()

    return Step(run, f"lift({start!r})")


def press_key(name: str, mods: str = "", after: float = 400) -> Step:
    def run(ctx):
        yield ("key", name, mods)
        for _ in range(max(1, round(after / 1000 * ctx.fps))):
            yield ("move", *(ctx.pointer or (0, 0)))
            yield from ctx.tick()

    return Step(run, f"key({name!r})")


def card(text, t=None):
    t = t or pz.theme.current()
    return pz.container(ui.label(text), padding=10, width="fill").style(
        background=t.elevated, border_color=t.border, border_width=1, radius=8)


# -- small scenes ---------------------------------------------------------------------------------
class ToolsScene(pz.App):
    """A toolbar shape dropped on a canvas, and a card dropped on a trash can."""

    def __init__(self):
        self.shapes = [("Box", 330, 60)]
        self.cards = ["Invoice.pdf", "Notes.txt"]

    def drop(self, e):
        self.shapes.append((e.data, e.item_x, e.item_y))

    def view(self):
        t = pz.theme.current()
        tools = pz.column([
            ui.label("Tools", weight="bold"),
            pz.draggable(pz.container(pz.row([pz.icon("square"), ui.label("Box")], spacing=6), padding=8)
                         .style(background=t.element, radius=6), "new-box", data="Box", type="shape", source="keep"),
            pz.draggable(pz.container(pz.row([pz.icon("circle"), ui.label("Dot")], spacing=6), padding=8)
                         .style(background=t.element, radius=6), "new-dot", data="Dot", type="shape", source="keep"),
            pz.space(height=20),
            *[pz.draggable(card(c, t), c, type="file") for c in self.cards],
            pz.droppable(pz.container(pz.row([pz.icon("trash-2"), ui.label("Trash")], spacing=6), padding=12,
                                      width="fill").style(border_color=t.border, border_width=1, radius=8),
                         "trash", accepts="file", on_drop=lambda e: self.cards.remove(e.source)),
        ], spacing=8, width=170)
        shapes = [pz.pin(pz.container(ui.label(name, color="#ffffff"), width=110, height=70, align_x="center",
                                      align_y="center").style(background="#5c78e2" if name == "Box" else "#c678dd",
                                                              radius=8 if name == "Box" else 35), x=x, y=y)
                  for name, x, y in self.shapes]
        canvas = pz.droppable(pz.container(pz.stack([pz.space(width="fill", height="fill"), *shapes]),
                                           width="fill", height="fill").style(background=t.editor, radius=10),
                              "canvas", accepts="shape", snap=10, on_drop=self.drop)
        return pz.row([tools, canvas], spacing=16, padding=16)


class HandlesScene(pz.App):
    def __init__(self):
        self.rows = ["Name", "Email", "Phone", "Company"]

    def row(self, name):
        t = pz.theme.current()
        return pz.container(pz.row([pz.drag_handle(pz.icon("grip-vertical", color=t.text_muted)),
                                    ui.label(name), pz.space(width="fill"), ui.input("", None, placeholder=f"Your {name.lower()}",
                                                                       size="sm")],
                                   spacing=10, align="center"), padding=8, width="fill").style(
            background=t.elevated, radius=8, border_color=t.border, border_width=1)

    def view(self):
        return pz.container(pz.sortable(items=self.rows, item=self.row, key=str, id="rows", handle=True, spacing=8,
                                        on_reorder=lambda e: pz.dnd.move(self.rows, e)), padding=20, width=420)


class ConditionsScene(pz.App):
    def __init__(self):
        self.lists = {"backlog": ["Fix login", "Locked: legal", "New icons"], "sprint": ["API docs", "Tests"],
                      "review": ["Release"]}

    def column(self, name, title, **options):
        t = pz.theme.current()
        body = pz.sortable(items=self.lists[name], item=card, key=str, id=name, group="tasks", spacing=8,
                           height="fill", on_reorder=lambda e: pz.dnd.move(self.lists, e), **options)
        return pz.container(pz.column([ui.label(title, weight="bold"), body], spacing=10), padding=12, width=200,
                            height="fill").style(background=t.surface, radius=10)

    def view(self):
        return pz.row([
            self.column("backlog", "Backlog"),
            self.column("sprint", "Sprint (max 2)", max_items=2),
            self.column("review", "Review (no locked)", can_drop=lambda e: not str(e.data).startswith("Locked")),
        ], spacing=14, padding=16)


class PreviewsScene(pz.App):
    def __init__(self):
        self.lists = {"shadow": ["One", "Two", "Three", "Four"], "ghost": ["Red", "Green", "Blue", "Gray"],
                      "custom": ["Mon", "Tue", "Wed", "Thu"]}

    def column(self, name, title, **options):
        t = pz.theme.current()
        body = pz.sortable(items=self.lists[name], item=card, key=str, id=name, spacing=6,
                           on_reorder=lambda e: pz.dnd.move(self.lists[name], e), **options)
        return pz.container(pz.column([ui.muted(title), body], spacing=8), padding=12, width=190).style(
            background=t.surface, radius=10)

    def view(self):
        return pz.row([
            self.column("shadow", 'placeholder="shadow"'),
            self.column("ghost", 'placeholder="ghost"', placeholder="ghost"),
            self.column("custom", 'lift=1.08, opacity=0.85', lift=1.08, opacity=0.85, source="ghost",
                        placeholder="none"),
        ], spacing=14, padding=16)


class FoldersScene(pz.App):
    def __init__(self):
        self.files = [{"id": "notes.txt"}, {"id": "Photos", "folder": []}, {"id": "budget.xlsx"},
                      {"id": "Work", "folder": ["plan.md"]}, {"id": "todo.md"}]

    def drop(self, e):
        if e.combine is None:
            pz.dnd.move(self.files, e)
            return
        target = next(f for f in self.files if f["id"] == e.combine)
        if "folder" in target:
            target["folder"].append(self.files.pop(e.from_index)["id"])

    def row(self, f):
        t = pz.theme.current()
        folder = "folder" in f
        count = ui.badge(str(len(f["folder"])), size="sm") if folder and f["folder"] else pz.space()
        return pz.container(pz.row([pz.icon("folder" if folder else "file", color=t.accent if folder else t.text_muted),
                                    ui.label(f["id"]), pz.space(width="fill"), count], spacing=8, align="center"),
                            padding=10, width="fill").style(background=t.elevated, radius=8)

    def view(self):
        return pz.container(pz.sortable(items=self.files, item=self.row, id="files", spacing=6, combine=True,
                                        on_reorder=self.drop), padding=20, width=380)


# -- the clips ------------------------------------------------------------------------------------
def clips():
    kanban, sortables = example("kanban"), example("sortables")
    form, page = example("form_builder"), example("page_builder")
    design, nodes = example("design_canvas"), example("node_editor")
    return {
        "kanban": (kanban, (980, 560), [
            wait(300),
            lift("Crash when saving", ("Translate the docs", 0, -14)),
            lift("Write the API guide", ("Project setup", 0, 40)),
            lift("Dark mode icons", (490, 430), "Drop here to delete"),
            leave(), wait(500)]),
        "sortables": (sortables, (960, 470), [
            wait(300),
            lift("Buy milk", ("Book flights", 0, 8)),
            lift("main.py", ("README.md", 30, 0)),
            lift((480, 95), (700, 160)),
            lift("todo.md", ("Work", 0, 1)),
            leave(), wait(500)]),
        "draggable": (ToolsScene, (720, 360), [
            wait(300),
            lift("Box", (420, 230)),
            lift("Dot", (620, 120)),
            lift("Notes.txt", "Trash"),
            leave(), wait(500)]),
        "droppable": (ToolsScene, (720, 360), [
            wait(300),
            lift("Invoice.pdf", ("Trash", 40, -50), "Trash", hold=700),
            leave(), wait(500)]),
        "handles": (HandlesScene, (460, 260), [
            wait(300),
            lift("Email", ("Company", 0, 10)),
            lift(("Email", -35, 0), ("Company", -35, 10)),
            leave(), wait(500)]),
        "conditions": (ConditionsScene, (680, 300), [
            wait(300),
            lift("Fix login", ("Tests", 0, 30), hold=700),
            lift("Locked: legal", ("Release", 0, 30), hold=700),
            lift("New icons", ("Release", 0, 30)),
            leave(), wait(500)]),
        "previews": (PreviewsScene, (660, 260), [
            wait(300),
            lift("One", ("Three", 0, 10)),
            lift("Red", ("Blue", 0, 10)),
            lift("Mon", ("Wed", 0, 10)),
            leave(), wait(500)]),
        "canvas": (design, (1120, 600), [
            wait(300),
            lift("Headline", (560, 205), (700, 228), hold=600),
            lift((422, 301), (575, 330)),
            lift((248, 27), (720, 470)),
            leave(), wait(500)]),
        "design-canvas": (design, (1120, 600), [
            wait(300),
            lift("Headline", (560, 205), (700, 228), hold=600),
            lift((248, 27), (720, 470)),
            lift((90, 140), (90, 46)),
            leave(), wait(500)]),
        "combine": (FoldersScene, (420, 280), [
            wait(300),
            lift("todo.md", ("budget.xlsx", 0, -15)),
            lift("notes.txt", ("Photos", 0, 1), hold=600),
            leave(), wait(500)]),
        "wires": (nodes, (980, 420), [
            wait(300),
            lift((205, 285), (500, 330), (739, 331)),
            leave(), wait(500)]),
        "node-editor": (nodes, (980, 520), [
            wait(300),
            lift((205, 285), (500, 330), (739, 331)),
            lift("Time", (330, 380)),
            leave(), wait(500)]),
        "form-builder": (form, (1100, 560), [
            wait(300),
            lift("Number", (380, 140)),
            lift("Checkbox", (380, 80)),
            leave(), wait(500)]),
        "page-builder": (page, (1080, 560), [
            wait(300),
            lift("Quote", (600, 300)),
            lift("Image", (850, 200)),
            leave(), wait(500)]),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("names", nargs="*", help="only clips whose name contains one of these words")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    found = clips()
    if args.list:
        print("\n".join(found))
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (app, size, steps) in found.items():
        if args.names and not any(w in name for w in args.names):
            continue
        out = OUT / f"{name}.webp"
        scale = 1.0 if size[0] > 800 else 1.5
        take = session.record(app(), steps, size=size, scale=scale, fps=20, theme="Pyzed Dark")
        frames = images(take)
        # Flat UI colors compress well losslessly, and lossy frames leave smudges where the preview passed.
        data = encode_webp(frames, fps=20, lossless=True)
        if len(data) > TARGET:
            data = encode_webp(frames, fps=20, quality=90)
        out.write_bytes(data)
        print(f"{name}: {frames[0].size[0]}x{frames[0].size[1]}, {len(frames)} frames, {len(data) / 1000:.0f} KB")
        if len(data) > TARGET:
            print(f"  {name} is over {TARGET / 1000:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
