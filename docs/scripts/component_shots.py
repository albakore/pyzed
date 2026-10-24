"""Renders the illustrations of the Components pages (docs/src/assets/components/*.png).

    python docs/scripts/component_shots.py            # all of them
    python docs/scripts/component_shots.py tabs tree  # only some

They are drawn off-screen with ``App.screenshot`` (no window or GPU), in the Pyzed Dark theme.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pyzed as pz
from pyzed import ui

OUT = Path(__file__).resolve().parent.parent / "src" / "assets" / "components"
ui.base.KEY_STYLE = "words"
noop = lambda *a: None  # noqa: E731


def buttons():
    return pz.column([
        pz.row([
            ui.button("Filled", noop),
            ui.button("Ghost", noop, variant="ghost"),
            ui.button("Outline", noop, variant="outline"),
            ui.button("Solid", noop, variant="solid"),
            ui.button("Disabled", noop, disabled=True),
        ], spacing=8),
        pz.row([
            ui.button("Error", noop, variant="error", icon="trash-2"),
            ui.button("Warning", noop, variant="warning", icon="triangle-alert"),
            ui.button("Success", noop, variant="success", icon="check"),
            ui.button("Save", noop, icon="save", keys="ctrl-s"),
        ], spacing=8),
        pz.row([
            ui.button("xs", noop, size="xs"), ui.button("sm", noop, size="sm"),
            ui.button("md", noop, size="md"), ui.button("lg", noop, size="lg"),
            ui.icon_button("settings", noop, tooltip="Settings"),
            ui.icon_button("search", noop, variant="filled"),
            ui.icon_button("bell", noop, selected=True),
        ], spacing=8, align="center"),
    ], spacing=12)


def text():
    return pz.column([
        ui.heading("Heading 1"),
        ui.heading("Heading 2", level=2),
        ui.heading("Heading 3", level=3),
        ui.label("Normal label"),
        ui.muted("Muted text"),
        ui.label("Accent text", color="accent"),
        ui.label("def mono(): ...", mono=True, size="sm"),
    ], spacing=6)


def badges():
    return pz.column([
        pz.row([ui.badge("accent"), ui.badge("success", tint="success"), ui.badge("warning", tint="warning"),
                ui.badge("error", tint="error", icon="circle-x")], spacing=6),
        pz.row([ui.badge("solid", variant="solid"), ui.badge("outline", variant="outline"),
                ui.indicator(), ui.indicator("success"), ui.indicator("error"), ui.indicator("warning")],
               spacing=6, align="center"),
        pz.row([ui.kbd("ctrl-shift-p"), ui.kbd("cmd-k cmd-s"), ui.kbd("escape")], spacing=12),
        pz.row([ui.avatar("AL", index=0), ui.avatar("KV", index=1), ui.avatar("MZ", index=2),
                ui.avatar("JD", index=3, size=28)], spacing=6, align="center"),
    ], spacing=14)


def card():
    return ui.card(
        pz.column([
            ui.muted("Pyzed draws the UI with Iced, in Rust."),
            pz.row([pz.hspace(), ui.button("Cancel", noop, variant="ghost"),
                    ui.button("OK", noop, variant="solid")], spacing=8),
        ], spacing=12),
        title="Card",
        actions=[ui.icon_button("ellipsis", noop, size="sm")],
        width=380,
    )


def forms():
    return pz.column([
        ui.input("", noop, placeholder="Project name"),
        ui.search_input("comp", noop),
        ui.field("Autosave", ui.switch(True, noop), description="Saves when switching tabs"),
        ui.field("Format on save", ui.checkbox(False, noop)),
        ui.field("Font size", pz.container(ui.slider(0.6, noop), width=160)),
        ui.segmented(["Editor", "Terminal", "Both"], "Editor", noop),
        ui.progress(0.65),
    ], spacing=12, width=420)


def list_items():
    return pz.container(
        pz.column([
            ui.list_header("RECENT", end=ui.icon_button("plus", noop, size="xs")),
            ui.list_item("main.py", noop, icon="file-code", icon_color="#3572a5", selected=True, inset=True),
            ui.list_item("README.md", noop, icon="file-text", inset=True, end=ui.badge("M", tint="warning")),
            ui.list_item("Cargo.toml", noop, icon="file-cog", inset=True, end=ui.kbd("ctrl-1", size="xs")),
            ui.list_item("old.txt", noop, icon="file", inset=True, disabled=True),
        ], width=300),
        padding=4,
    )


def tree():
    nodes = ui.TreeNode.from_paths(
        ["src/main.rs", "src/app.rs", "src/ui/button.rs", "src/ui/mod.rs", "tests/app.rs", "Cargo.toml", "README.md"],
        status={"src/app.rs": "modified", "src/ui/button.rs": "created", "README.md": "modified"},
    )
    return pz.container(ui.tree(nodes, expanded={"src", "src/ui"}, selected="src/app.rs", on_toggle=noop,
                                on_select=noop), width=260)


def menu():
    return ui.menu([
        ui.MenuItem("New file", noop, icon="file-plus", keys="ctrl-n"),
        ui.MenuItem("New folder", noop, icon="folder-plus"),
        ui.SEPARATOR,
        "EDITAR",
        ui.MenuItem("Copy path", noop, keys="ctrl-alt-c"),
        ui.MenuItem("Soft wrap", noop, checked=True),
        ui.SEPARATOR,
        ui.MenuItem("Delete", noop, icon="trash-2", danger=True),
    ])


def tabs():
    return pz.column([
        ui.tab_bar(
            [ui.Tab.for_file("src/main.rs"), ui.Tab.for_file("src/app.rs", dirty=True, status="modified"),
             ui.Tab.for_file("README.md", preview=True)],
            "src/main.rs", on_select=noop, on_close=noop,
            start=[ui.icon_button("arrow-left", noop, size="sm"), ui.icon_button("arrow-right", noop, size="sm")],
            end=[ui.icon_button("plus", noop, size="sm"), ui.icon_button("columns-2", noop, size="sm")],
        ),
        ui.toolbar(
            [ui.breadcrumbs([("file-code", "src"), "main.rs", "fn main"])],
            [ui.icon_button("search", noop, size="sm"), ui.icon_button("sparkles", noop, size="sm")],
        ),
    ], width=640)


def workspace():
    t = pz.theme.current()
    files = ui.TreeNode.from_paths(["src/main.py", "src/ui.py", "README.md"], status={"src/ui.py": "modified"})
    return ui.workspace(
        pz.column([
            ui.tab_bar([ui.Tab.for_file("src/main.py")], "src/main.py", on_close=noop),
            ui.editor("ws-main", 'import pyzed as pz\n\n\ndef main():\n    pz.run(App)\n', path="main.py"),
        ]),
        title_bar=ui.title_bar([ui.title_button("pyzed", chevron=True), ui.title_button("main", icon="git-branch", muted=True)],
                               [ui.icon_button("bell", noop, size="sm"), ui.avatar("KV")]),
        left=pz.column([ui.panel_header("Project", [ui.icon_button("plus", noop, size="xs")]),
                        ui.tree(files, expanded={"src"}, selected="src/main.py")]),
        bottom=pz.column([ui.panel_header("Terminal", icon="terminal"),
                          ui.terminal("$ python main.py\n\x1b[32m✓\x1b[0m done")]),
        status_bar=ui.status_bar([ui.status_item("0", icon="circle-x"), ui.status_item("1", icon="triangle-alert")],
                                 [ui.status_item("Ln 4, Col 8"), ui.status_item("Python")]),
        left_width=200,
        bottom_height=110,
        theme=t,
    )


def palette():
    commands = [
        ui.PaletteItem("editor: toggle soft wrap", noop, keys="alt-z"),
        ui.PaletteItem("theme selector: toggle", noop, keys="ctrl-k ctrl-t"),
        ui.PaletteItem("workspace: toggle left dock", noop, keys="ctrl-b"),
        ui.PaletteItem("terminal panel: toggle", noop, keys="ctrl-j"),
    ]
    return ui.command_palette("tog", noop, commands, selected=0, width=520)


def modal():
    return ui.modal(
        ui.muted("main.py has unsaved changes. Save them before closing?"),
        title="Save changes?",
        on_close=noop,
        footer=[ui.button("Don't save", noop, variant="ghost"), ui.button("Cancel", noop),
                ui.button("Save", noop, variant="solid")],
        width=420,
    )


def toasts():
    return pz.column([
        ui.toast("Saved", "main.py was saved.", kind="success", on_dismiss=noop),
        ui.toast("Update available", "Pyzed 0.2 is on PyPI.", kind="info",
                 actions=[ui.button("What's new", noop, size="sm")], on_dismiss=noop),
        ui.toast("Could not connect", kind="error", on_dismiss=noop),
    ], spacing=8)


def editor():
    code = '''import pyzed as pz
from pyzed import ui


class Counter(pz.App):
    def __init__(self):
        self.count = 0  # estado

    def view(self):
        return ui.button(f"Clicks: {self.count}", self.increment)
'''
    return pz.container(ui.editor("doc-editor", code, path="counter.py", markers={6: "modified", 7: "created", 10: "created"}),
                        width=560, height=250)


FEATURES_CODE = '''import pyzed as pz
from pyzed import ui


class Counter(pz.App):
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1

    def view(self):
        return ui.button(f"Clicks: {self.count}", self.increment)


def main():
    pz.run(Counter())
'''


def editor_features():
    # `__init__` (line 6) and `increment` (line 9) start folded (see START).
    return pz.container(ui.editor("doc-editor-features", FEATURES_CODE, path="counter.py", minimap=True,
                                  annotations={5: "1 reference"}),
                        width=560, height=250)


MULTI_CODE = """prices = {
    "apple": 3,
    "pear": 5,
    "fig": 8,
}


def total(prices):
    return sum(prices.values())
"""


def editor_multicursor():
    # Three cursors (Alt+Shift+Down) and the search results for `prices` (see START).
    return pz.container(ui.editor("doc-editor-multi", MULTI_CODE, path="prices.py",
                                  highlights=[(1, 1, 1, 7), (8, 11, 8, 17), (9, 16, 9, 22)]),
                        width=560, height=250)


def terminal():
    out = ("$ pytest -q\n\x1b[32m........................\x1b[0m\n\x1b[32m24 passed\x1b[0m in 1.21s\n"
           "$ maturin develop --release\n\x1b[2m   Compiling pyzed v0.1.0\x1b[0m\n\x1b[32m✓\x1b[0m Installed pyzed-0.1.0\n$ ")
    return pz.container(ui.terminal(out), width=520, height=170)


def controls():
    return pz.column([
        pz.row([
            ui.select(["Python", "Rust", "TypeScript"], "Rust", noop, width=160),
            ui.number_field(14, noop, min=8, max=32, suffix="px"),
            ui.split_button("Run", noop, noop, icon="play"),
        ], spacing=10, align="center"),
        pz.row([
            ui.radio_group([("a", "Spaces"), ("b", "Tabs")], "a", noop, horizontal=True),
            pz.hspace(),
            ui.toggle_group([("l", "align-left"), ("c", "align-center"), ("r", "align-right")], "c", noop),
        ], spacing=10, align="center"),
        pz.row([
            ui.chip("python", icon="tag", selected=True),
            ui.chip("rust", on_remove=noop),
            ui.chip("iced", on_press=noop),
        ], spacing=6),
        ui.disclosure("Advanced options", ui.muted("Collapsible content."), open=True, on_toggle=noop),
    ], spacing=14)


def feedback():
    return pz.column([
        ui.callout("A new version is out", "Pyzed 0.2 adds windows, async and canvas.", tint="info",
                   actions=[ui.button("What's new", noop, size="sm")], on_dismiss=noop),
        ui.callout("Could not save", "The file is read-only.", tint="error"),
        pz.row([
            ui.spinner(), ui.count_badge(7), ui.count_badge(120, tint="error"),
            ui.facepile(["Ana", "Luis", "Kev", "Marta"]),
            ui.diff_stat(42, 9),
            ui.keybinding_hint("Open palette", "ctrl-shift-p"),
        ], spacing=14, align="center"),
    ], spacing=12)


def table():
    rows = [
        {"name": "render.rs", "lang": "Rust", "lines": 1840},
        {"name": "app.py", "lang": "Python", "lines": 512},
        {"name": "theme.py", "lang": "Python", "lines": 730},
        {"name": "docs.yml", "lang": "YAML", "lines": 64},
    ]
    return ui.table(
        [ui.Column("File", "name"), ui.Column("Language", "lang", width=120),
         ui.Column("Lines", "lines", width=80, align="end")],
        rows, sort_by="Lines", descending=True, on_sort=noop, selected=rows[1], striped=True,
    )


def charts():
    return pz.row([
        pz.column([
            ui.stat("Users", "1.284", delta=12.5, trend=[3, 5, 4, 6, 8, 7, 9]),
            ui.stat("Errors", "37", delta=-8.0),
        ], spacing=10, width=200),
        ui.bar_chart([12, 19, 8, 15, 22, 17], labels=["L", "M", "X", "J", "V", "S"], width=260, height=150),
        pz.column([ui.donut([60, 25, 15], label="60%"), ui.sparkline([1, 4, 2, 6, 3, 7, 5, 8])],
                  spacing=12, align="center"),
    ], spacing=20)


def empty():
    return pz.row([
        ui.card(ui.empty_state("No results", "Try another search.", icon="search",
                               actions=[ui.button("Clear filters", noop, size="sm")]), padding=12),
        ui.settings_group("Editor", [
            ui.field("Font size", ui.number_field(14, noop, suffix="px")),
            ui.field("Soft wrap", ui.switch(True, noop)),
        ], description="Editor preferences."),
    ], spacing=16)


def content():
    md = "## Markdown\n\nText with **bold**, *italic*, `code` and [links](https://iced.rs).\n\n- Lists\n- And more"
    return pz.row([
        pz.column([
            pz.markdown(md, width=300),
            pz.rich_text([
                pz.span("rich_text "), pz.span("mixes ", color="#e5c07b"),
                pz.span("styles", weight="bold", underline=True), pz.span(" on one line", italic=True),
            ]),
        ], spacing=12, width=320),
        pz.column([
            pz.qr_code("https://albakore.github.io/pyzed/", cell_size=4),
            ui.muted("pz.qr_code", size="sm"),
        ], spacing=6, align="center"),
    ], spacing=24)


def media():
    img = str(Path(__file__).resolve().parents[2] / "docs" / "screenshots" / "zed-dark.png")
    return pz.row([
        pz.image(img, width=240, height=140, content_fit="contain"),
        pz.image(img, width=160, height=140, content_fit="contain", opacity=0.5),
        pz.image(img, width=120, height=140, content_fit="contain", filter="nearest"),
    ], spacing=16, align="center")


def split():
    t = pz.themes.PYZED_DARK
    pane = lambda title, color: pz.container(ui.label(title), padding=12, width="fill", height="fill", bg=color)
    return ui.split(pane("Left", t.panel), ui.split(pane("Top", t.editor), pane("Bottom", t.background),
                                                         vertical=True), ratio=0.4, on_resize=noop)


def widgets():
    t = pz.themes.PYZED_DARK
    return pz.column([
        pz.row([
            pz.button("pz.button", noop, bg=t.accent, color=t.background, radius=4, padding=(6, 12)),
            pz.checkbox(True, "checkbox", on_toggle=noop),
            pz.toggler(True, "toggler", on_toggle=noop),
            pz.radio("radio", True, noop),
        ], spacing=16, align="center"),
        pz.row([
            pz.container(pz.text_input("text_input", on_input=noop), width=200),
            pz.pick_list(["pick_list", "option"], "pick_list", noop, width=140),
        ], spacing=16, align="center"),
        pz.row([pz.container(pz.slider(0, 100, 60, on_change=noop), width=200),
                pz.container(pz.progress_bar(0.6), width=200)], spacing=16, align="center"),
        pz.rule(),
        pz.row([pz.icon("sparkles", size=18, color=t.accent), pz.text("pz.text with an icon", color=t.text)],
               spacing=8, align="center"),
    ], spacing=14)


def canvas():
    from pyzed import draw
    shapes = [
        draw.rect(10, 10, 120, 80, fill="#74ade8", radius=8),
        draw.circle(200, 50, 40, fill="#a1c181"),
        draw.arc(300, 50, 40, 0, 270, stroke="#e5c07b", width=8, cap="round"),
        draw.polygon([(360, 90), (400, 10), (440, 90)], fill="#d07277"),
        draw.line(10, 120, 440, 120, stroke="#5d636f", width=2, dash=[6, 4]),
        draw.text(225, 150, "pz.canvas + pyzed.draw", color="#dce0e5", size=16, align_x="center"),
    ]
    return pz.canvas(shapes, width=450, height=170)


def popover():
    base = pz.container(ui.muted("Right-click anywhere"), width="fill", height="fill", padding=12)
    menu = ui.menu([
        ui.MenuItem("Copy", noop, icon="copy", keys="ctrl-c"),
        ui.MenuItem("Paste", noop, icon="clipboard", keys="ctrl-v"),
        ui.MenuItem("Delete", noop, icon="trash-2", danger=True),
    ], width=200)
    return ui.popover(ui.card(base, padding=0), menu, x=120, y=40, on_dismiss=noop)


def picker():
    files = ["src/app.rs", "src/render.rs", "python/pyzed/app.py", "python/pyzed/theme.py", "README.md"]
    items = ui.fuzzy_filter("app", [ui.PaletteItem(f, noop) for f in files], key=lambda i: i.label)
    return ui.picker("app", noop, items, selected=0, placeholder="Search files…", width=480)


def dialogs():
    base = pz.container(ui.muted("main.py"), width="fill", height="fill", padding=12)
    return pz.row([
        pz.container(ui.dialog_layer(base, ui.confirm("Delete main.py? This can't be undone.", noop, noop,
                                                      title="Delete file", danger=True, width=300)),
                     width=340, height=200),
        pz.container(ui.dialog_layer(base, ui.prompt("Rename", "main.py", noop, noop, noop, width=300)),
                     width=340, height=200),
    ], spacing=16)


def accordion():
    rows = lambda *items: pz.column([ui.field(k, ui.switch(v, noop)) for k, v in items], spacing=8)
    return pz.container(ui.accordion([
        ("editor", "Editor", rows(("Soft wrap", True), ("Minimap", False))),
        ("files", "Files", rows(("Autosave", True))),
        ("git", "Git", ui.muted("Collapsed sections only show their header.")),
    ], open={"editor", "files"}, on_toggle=noop, icons={"editor": "file-code", "files": "folder", "git": "git-branch"}),
        width=380)


def console():
    log = ui.Log()
    log.write("info", "Loaded ui/main.pzform")
    log.write("event", "button1.click")
    log.write("stdout", "Saving 3 files…")
    log.write("warning", "settings.json not found, using defaults")
    log.write("error", "ValueError: invalid literal for int()")
    return pz.container(ui.console(log.entries, on_clear=noop, on_copy=noop, on_query=noop), width=560, height=200)


def shortcuts():
    return pz.container(ui.shortcuts([
        ("File", [("Save", "ctrl-s"), ("Open file", "ctrl-p")]),
        ("View", [("Command palette", "ctrl-shift-p"), ("Toggle left dock", "ctrl-b")]),
    ], on_query=noop, height=200), width=380)


def about():
    return ui.about("Notes", "1.2.0", "A small notes app built with Pyzed.", icon="notebook-pen",
                    details=[("Python", "3.12"), ("Pyzed", "0.3")], links=[("Website", noop), ("GitHub", noop)])


def color_picker():
    return pz.row([
        ui.ColorPicker(value="#3b82f6cc", on_change=noop),
        pz.column([ui.color_swatch(c, size=28) for c in ["#3b82f6", "#a1c181aa", pz.Gradient(["#f97316", "#7c3aed"], angle=90)]],
                  spacing=8),
    ], spacing=16)


SHOTS = {
    "buttons": (buttons, (600, 150)),
    "text": (text, (320, 230)),
    "badges": (badges, (420, 170)),
    "card": (card, (420, 150)),
    "forms": (forms, (460, 290)),
    "list": (list_items, (340, 170)),
    "tree": (tree, (300, 250)),
    "menu": (menu, (290, 230)),
    "tabs": (tabs, (680, 100)),
    "workspace": (workspace, (820, 460)),
    "palette": (palette, (560, 220)),
    "modal": (modal, (460, 170)),
    "toasts": (toasts, (380, 270)),
    "editor": (editor, (600, 290)),
    "editor-features": (editor_features, (600, 290)),
    "editor-multicursor": (editor_multicursor, (600, 290)),
    "terminal": (terminal, (560, 210)),
    "controls": (controls, (600, 210)),
    "feedback": (feedback, (640, 210)),
    "table": (table, (480, 190)),
    "charts": (charts, (640, 240)),
    "empty": (empty, (680, 240)),
    "content": (content, (520, 210)),
    "media": (media, (620, 180)),
    "split": (split, (520, 260)),
    "widgets": (widgets, (520, 225)),
    "canvas": (canvas, (490, 210)),
    "popover": (popover, (420, 220)),
    "picker": (picker, (520, 200)),
    "dialogs": (dialogs, (736, 240)),
    "accordion": (accordion, (420, 230)),
    "console": (console, (600, 180)),
    "shortcuts": (shortcuts, (420, 250)),
    "about": (about, (420, 320)),
    "color-picker": (color_picker, (420, 450)),
}


#: Commands run before a shot is drawn.
START = {
    "editor-features": lambda: pz.Command.batch([pz.Command.fold_line("doc-editor-features", n) for n in (6, 9)]),
    "editor-multicursor": lambda: pz.Command.batch([
        pz.Command.select_editor_ranges("doc-editor-multi", [(4, 10, 4, 10), (2, 12, 2, 12), (3, 11, 3, 11)]),
        pz.Command.focus("doc-editor-multi")]),
}


class Shot(pz.App):
    def __init__(self, build, full=False, start=None):
        self.build, self.full, self.start = build, full, start

    def on_start(self):
        return self.start() if self.start else None

    def view(self):
        if self.full:
            return self.build()
        return pz.container(self.build(), padding=20, width="fill", height="fill", bg=self.resolved_theme().background)


def main(names):
    OUT.mkdir(parents=True, exist_ok=True)
    for name in names or SHOTS:
        build, size = SHOTS[name]
        Shot(build, full=name in ("workspace", "split"), start=START.get(name)).screenshot(OUT / f"{name}.png", size=size, scale=2)
        print(f"wrote {name}.png")


if __name__ == "__main__":
    main(sys.argv[1:])
