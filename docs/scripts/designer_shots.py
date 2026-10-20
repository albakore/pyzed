"""Screenshots of Pyzed Design's newer parts, rendered off-screen at 2x: the welcome window, the title bar
on every desktop, the menus, the settings dialogs, the Shader view (one image per node type), the
Component view and document windows.

    python docs/scripts/designer_shots.py               # every shot
    python docs/scripts/designer_shots.py welcome nodes # only the shots whose name contains a word

They go to docs/src/assets/editor/ and docs/src/assets/shading/ (node cards in shading/nodes/<type>.png),
so the pages import them and Astro serves them as WebP/AVIF. The designer runs with a throwaway settings
folder, so your own preferences (theme, docks, recent files) never leak into the images.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "docs" / "src" / "assets"
EDITOR = ASSETS / "editor"
SHADING = ASSETS / "shading"
NODES = SHADING / "nodes"
EXAMPLES = ROOT / "examples" / "designer"
TEMPLATES = ROOT / "python" / "pyzed" / "designer" / "templates" / "shaders"
SHOWCASE = ROOT / "examples" / "showcase" / "shaders"
SIZE = (1440, 900)
SCALE = 2
#: The time (seconds) shader previews are drawn at.
SHADER_TIME = 1.6

os.environ["PYZED_CONFIG_DIR"] = tempfile.mkdtemp(prefix="pyzed-shots-")

import pyzed as pz
from pyzed import _core, shading, ui
from pyzed.designer import dialogs, shader_editor
from pyzed.designer.app import Designer

ui.base.KEY_STYLE = "words"

SHOTS = {}


def shot(fn):
    SHOTS[fn.__name__] = fn
    return fn


def make(path=EXAMPLES / "login.pzform", theme=None, frame="gnome"):
    """A designer on ``path`` with the GNOME title bar (the same picture on every computer)."""
    app = Designer(path, language_servers=False)
    app.frame = frame
    if theme:
        app.theme = pz.themes.get(theme)
    app.toasts.clear()
    app.dialog = None
    app.shading.paused = SHADER_TIME  # shader previews drawn at a moment where they show something
    return app


def save(app, out, size=SIZE):
    out.parent.mkdir(parents=True, exist_ok=True)
    app.toasts.clear()
    app.screenshot(out, size=size, scale=SCALE)
    print("wrote", out.relative_to(ROOT))


def crop(path, box):
    """Crops ``path`` in place to ``box`` (logical pixels: left, top, right, bottom)."""
    from PIL import Image

    with Image.open(path) as im:
        im.crop(tuple(int(v * SCALE) for v in box)).save(path, optimize=True)


class Host(pz.App):
    """Shows ``build()`` as an app, to screenshot a part of the designer on its own."""

    def __init__(self, build, theme=None):
        self.build = build
        self.theme = theme

    def view(self):
        return self.build()


# -- the welcome window ----------------------------------------------------------------------------
@shot
def welcome():
    for theme, suffix in (("One Dark", ""), ("One Light", "-light")):
        app = make(None, theme)
        app.welcome.open()
        save(app, EDITOR / f"welcome{suffix}.png")
    app = make(None)
    app.welcome.open()
    app.welcome.category = "Games"
    save(app, EDITOR / "welcome-games.png")
    app.welcome.category = "Showcase"
    save(app, EDITOR / "welcome-showcase.png")
    from pyzed.designer import samples

    app.welcome.category = "All"
    app.welcome.folder = "/home/ada/Pyzed Projects"
    app.welcome.pick(next(s for s in samples.CATALOG if s.id == "snake"))
    save(app, EDITOR / "welcome-create.png")


# -- title bar, window frames and menus ------------------------------------------------------------
@shot
def title_bar():
    from pyzed.ui import frame as ui_frame

    for style in ("gnome", "windows", "macos", "kde", "ubuntu"):
        app = make(frame=style)
        out = EDITOR / f"title-bar-{style}.png"
        save(app, out)
        crop(out, (0, 0, SIZE[0], ui_frame.HEIGHTS[style] + 4))
    app = make(frame=None)
    save(app, EDITOR / "system-frame.png")


@shot
def menus():
    for name in ("file", "view", "help"):
        app = make()
        for recent in ("settings.pzform", "orders.pzform", "login.pzform"):
            app.prefs.remember(EXAMPLES / recent)
        app.toggle_app_menu(name)
        save(app, EDITOR / f"menu-{name}.png")


# -- the main views --------------------------------------------------------------------------------
@shot
def form_view():
    for theme, suffix in (("One Dark", ""), ("One Light", "-light"), ("Gruvbox Dark", "-gruvbox"),
                          ("Ayu Mirage", "-ayu")):
        app = make(theme=theme)
        app.doc.select("sign_in")
        app._selection_changed()
        save(app, EDITOR / f"form-view{suffix}.png")


@shot
def component_view():
    folder = EXAMPLES / "components"
    comps = sorted(folder.glob("*.pzcomp"))
    if not comps:
        print("no components in", folder)
        return
    for theme, suffix in (("One Dark", ""), ("One Light", "-light")):
        app = make(comps[0], theme)
        save(app, EDITOR / f"component-view{suffix}.png")


# -- settings --------------------------------------------------------------------------------------
class _NoScroll:
    """Stands in for ``_core`` while the settings dialog is built: its scrollable shows everything."""

    def __getattr__(self, name):
        return getattr(_core, name)

    @staticmethod
    def scrollable(content, **_):
        return content


@shot
def settings():
    app = make()
    app.open_settings()
    save(app, EDITOR / "settings.png")
    real = dialogs._core
    dialogs._core = _NoScroll()
    try:
        out = EDITOR / "settings-all.png"
        save(app, out, size=(1440, 1500))
        _crop_to_modal(out)
    finally:
        dialogs._core = real
    app.close_dialog()

    app.open_editor_settings()
    from pyzed.designer.code_panel import SETTINGS_SECTIONS

    for section in SETTINGS_SECTIONS:
        if section == "servers":
            continue
        app.assist.show_settings_section(section)
        save(app, EDITOR / f"editor-settings-{section}.png")
    # the language servers, running (ty and ruff come with the designer extra)
    live = Designer(EXAMPLES / "login.pzform")
    live.frame = "gnome"
    live.open_default_event("sign_in")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not all(s.ready for s in live.assist.intel.servers.values()):
        time.sleep(0.5)
    time.sleep(2)
    live.open_editor_settings()
    live.assist.show_settings_section("servers")
    save(live, EDITOR / "editor-settings-servers.png")
    live.close_dialog()
    live.assist.shutdown()
    app.close_dialog()
    keymap_editor(app)

    for provider in (None, "anthropic", "openrouter"):
        app.agent.provider_open = provider
        app.dialog = "agent_settings"
        save(app, EDITOR / f"agent-settings{'-' + provider if provider else ''}.png")
    app.dialog = None


def keymap_editor(app):
    """The keymap editor: a changed key, a conflict, and new keys being recorded."""
    from pyzed.designer import keymap

    km = keymap.get()
    [save_as] = km.bindings_for("workspace::save_as")
    km.change(save_as, "ctrl-alt-s")
    km.add("workspace::grid", "ctrl-d", "Canvas")  # Duplicate already has it: a conflict
    km.save()
    ke = app.keymap_editor
    app.open_keymap()
    ke.set_query("save")
    save(app, EDITOR / "keymap-editor.png")
    ke.set_query("")
    ke.set_filter("conflicts")
    save(app, EDITOR / "keymap-editor-conflicts.png")
    ke.set_filter("all")
    ke.set_query("go to")
    [goto] = km.bindings_for("code_panel::go_to_line")
    ke.start("code_panel::go_to_line", goto)
    ke.record("ctrl-k")
    ke.record("ctrl-g")
    save(app, EDITOR / "keymap-editor-recording.png")
    ke.cancel()
    km.reset_all()
    km.save()
    app.close_dialog()


def _crop_to_modal(path, width=560):
    """Crops a full-window shot to the centred modal of ``width``: its rows are the run of its own
    background color down a column just inside its left edge."""
    from PIL import Image

    with Image.open(path) as im:
        rgb = im.convert("RGB")
        w, h = rgb.size
        left = (w / SCALE - width) / 2
        x = int((left + 5) * SCALE)
        y0 = y1 = h // 2
        bg = rgb.getpixel((x, y0))

        def same(y):
            return sum(abs(a - b) for a, b in zip(rgb.getpixel((x, y)), bg)) < 10

        while y0 > 0 and same(y0 - 1):
            y0 -= 1
        while y1 < h - 1 and same(y1 + 1):
            y1 += 1
        pad = 16 * SCALE
        im.crop((int(left * SCALE) - pad, max(0, y0 - pad), int((left + width) * SCALE) + pad,
                 min(h, y1 + pad))).save(path, optimize=True)


# -- the Shader view -------------------------------------------------------------------------------
def shader_app(path, theme=None):
    app = make(path, theme)
    return app


def fitted(app, out, size=SIZE):
    """Renders once so the canvas knows its size, fits the whole graph, then saves the real shot."""
    tmp = Path(tempfile.mkdtemp()) / "fit.png"
    app.screenshot(tmp, size=size, scale=1)
    app.doc.fit(whole=True)
    app.doc.fit_pending = False
    save(app, out, size)


@shot
def shader_view():
    work = Path(tempfile.mkdtemp(prefix="pyzed-shaders-"))
    # every template and showcase graph, whole (a wider window, so the long ones fit at a readable zoom)
    for kind, folder in (("template", TEMPLATES), ("showcase", SHOWCASE)):
        for src in sorted(folder.glob("*.pzshad")):
            if src.stem == "blank":
                continue
            dst = work / kind / src.name
            dst.parent.mkdir(exist_ok=True)
            shutil.copy(src, dst)
            app = shader_app(dst)
            fitted(app, SHADING / "graphs" / f"{kind}-{src.stem}.png", size=(1920, 1080))
    shutil.copy(TEMPLATES / "glow_ring.pzshad", work / "glow_ring.pzshad")
    # the views and panels, on the glow ring
    dst = work / "glow_ring.pzshad"
    for theme, suffix in (("One Dark", ""), ("One Light", "-light")):
        app = shader_app(dst, theme)
        fitted(app, SHADING / f"shader-view{suffix}.png")
    app = shader_app(dst)
    doc = app.doc
    glow = next((n for n in doc.graph.nodes.values() if n.type == "glow"), None)
    if glow is not None:
        doc.select(glow.id)
        app.show_panel("properties")
        fitted(app, SHADING / "node-properties.png")
    doc.select(None)
    if doc.graph.variables:
        doc.select_variable(doc.graph.variables[0].name)
        save(app, SHADING / "variable-properties.png")
        doc.select_variable(None)
    shader_editor.set_tab(app, "preview")
    save(app, SHADING / "preview-tab.png")
    shader_editor.set_tab(app, "code")
    save(app, SHADING / "wgsl-tab.png")
    shader_editor.set_tab(app, "graph")
    app.shading.open_search((420.0, 160.0))
    app.shading.set_search("noi")
    save(app, SHADING / "node-search.png")
    app.shading.search = None
    if glow is not None:
        app.shading.menu = (glow.id, 520.0, 300.0)
        save(app, SHADING / "node-menu.png")
        app.shading.menu = None
    # the Shading sidebar with every category open
    app.shading.set_query("")
    save(app, SHADING / "sidebar.png", size=(1440, 1400))
    crop(SHADING / "sidebar.png", (0, 0, 340, 1400))
    # the New shader dialog
    here = os.getcwd()
    os.chdir(work)
    try:
        app.new("shader")
        templates = [p.stem for p in TEMPLATES.glob("*.pzshad")]
        if "plasma" in templates:
            app.set_new("template", "plasma")
        save(app, SHADING / "new-shader.png")
    finally:
        os.chdir(here)
        app.close_dialog()


# -- one picture per node type ---------------------------------------------------------------------
def _feed(g, node):
    """Wires a UV node into ``node`` when nothing of the pixel reaches it otherwise (no input reads the UV,
    the pixel or the time), so its preview shows a ramp instead of one flat color. Returns the UV node."""
    from pyzed.shading import layout as L

    inputs, _ = g.ports(node)
    if not inputs or not L.shows_preview(g, node):
        return None
    if any(isinstance(p.default, str) and p.default.startswith("@") for p in inputs):
        return None
    uv = g.add("uv", x=node.x - 260.0, y=node.y)
    first = inputs[0]
    for out in (("uv", "x") if first.type in ("vec2", "T") else ("x", "uv")):
        try:
            g.connect(uv, out, node.id, first.name)
            return uv
        except Exception:
            continue
    g.remove(uv.id)
    return None


@shot
def nodes():
    """One image per node type: the node as the graph draws it, with its live preview (fed by a UV
    node when it would otherwise be one flat color)."""
    from pyzed.shading import nodes as N

    work = Path(tempfile.mkdtemp(prefix="pyzed-nodes-"))
    NODES.mkdir(parents=True, exist_ok=True)
    path = shading.new("node").save(work / "node.pzshad")
    margin = 28.0
    done = 0
    for type_id in N.TYPES:
        app = make(path)
        doc = app.doc
        g = doc.graph
        for node_id in list(g.nodes):
            g.remove(node_id)
        try:
            ref = g.add(type_id, x=0.0, y=0.0)
        except Exception as error:  # some nodes need settings (a subgraph file, a variable)
            print(f"skipped {type_id}: {error}")
            continue
        node = g.nodes[ref.id]
        _feed(g, node)
        doc.zoom = 1.0
        x0, y0, bw, bh = doc.bounds()
        doc.pan = (margin - x0, margin - y0)
        width, height = bw + 2 * margin, bh + 2 * margin
        t = app.theme_obj

        def build(app=app, width=width, height=height, t=t):
            layers = [_core.canvas(shader_editor._grid_shapes(app.doc, width, height, t), width=width, height=height),
                      _core.canvas(shader_editor._wire_shapes(app, t), width=width, height=height)]
            for n in app.doc.graph.nodes.values():
                x, y = app.doc.to_view(n.x, n.y)
                layers.append(_core.pin(shader_editor.node_card(app, n, t), x=x, y=y))
            for n in app.doc.graph.nodes.values():
                layers.extend(shader_editor._ports(app, n, t))
            return _core.container(_core.stack(layers, width=width, height=height), width=width, height=height,
                                   bg=t.editor)

        out = NODES / f"{type_id}.png"
        pz.screenshot(Host(build, app.theme), out, size=(width, height), scale=SCALE, wait=0.05)
        done += 1
    print(f"wrote {done} node cards to {NODES.relative_to(ROOT)}")


# -- document windows ------------------------------------------------------------------------------
@shot
def windows():
    """A tab dragged out of the main window into a window of its own (two windows on a desktop)."""
    from PIL import Image, ImageDraw, ImageFilter

    work = Path(tempfile.mkdtemp(prefix="pyzed-windows-"))
    for name in ("login.pzform",):
        shutil.copy(EXAMPLES / name, work / name)
    shutil.copy(EXAMPLES / "login.py", work / "login.py")
    shutil.copy(TEMPLATES / "glow_ring.pzshad", work / "glow_ring.pzshad")
    app = make(work / "login.pzform")
    app.open_path(work / "glow_ring.pzshad")
    app.panes.detach_active()
    pane = app.panes.panes[-1]
    window = pane.window
    main_png = Path(tempfile.mkdtemp()) / "main.png"
    doc_png = Path(tempfile.mkdtemp()) / "doc.png"
    shader_doc = pane.docs[0]
    app.toasts.clear()
    app.panes.active = app.panes.here = app.panes.main
    app._selection_changed()
    app.screenshot(main_png, size=(1280, 800), scale=SCALE)

    class DocHost(pz.App):
        def __init__(self):
            self.frame = app.frame
            self.title = window.window_title()
            self.theme = app.theme

        def view(self):
            return window.view()

    app.panes.active = pane
    app.panes.here = pane
    app._selection_changed()
    pz.screenshot(DocHost(), doc_png, size=(900, 600), scale=1)  # the canvas learns its size
    shader_doc.fit(whole=True)
    shader_doc.fit_pending = False
    app.shading.mini = False
    pz.screenshot(DocHost(), doc_png, size=(900, 600), scale=SCALE)
    app.panes.active = app.panes.main
    with Image.open(main_png) as a, Image.open(doc_png) as b:
        W, H = int(1640 * SCALE), int(1000 * SCALE)
        desk = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        grad = Image.linear_gradient("L").resize((W, H))
        desk = Image.merge("RGB", (grad.point(lambda v: 24 + v // 10), grad.point(lambda v: 28 + v // 12),
                                    grad.point(lambda v: 40 + v // 6))).convert("RGBA")

        def paste(img, xy):
            shadow = Image.new("RGBA", (img.width + 80, img.height + 80), (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle((40, 50, img.width + 40, img.height + 40), 24,
                                                     fill=(0, 0, 0, 140))
            shadow = shadow.filter(ImageFilter.GaussianBlur(24))
            desk.alpha_composite(shadow, (xy[0] - 40, xy[1] - 40))
            mask = Image.new("L", img.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), 10 * SCALE, fill=255)
            desk.paste(img.convert("RGBA"), xy, mask)

        paste(a, (int(40 * SCALE), int(40 * SCALE)))
        paste(b, (int(700 * SCALE), int(360 * SCALE)))
        out = EDITOR / "tab-window.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        desk.convert("RGB").save(out, optimize=True)
        print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    wanted = sys.argv[1:]
    for name, fn in SHOTS.items():
        if not wanted or any(w in name for w in wanted):
            fn()
