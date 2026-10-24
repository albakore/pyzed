"""A tour of the ready-made components in ``pyzed.ui``.

    python examples/gallery.py
"""

import pyzed as pz
from pyzed import ui

SNIPPET = '''from pyzed import ui

def view(self):
    return ui.button("Deploy", self.deploy)
'''


class Gallery(pz.App):
    title = "Pyzed components"
    size = (1440, 900)

    def __init__(self, theme=pz.themes.PYZED_DARK):
        self.theme = theme
        self.name = "Pyzed"
        self.query = ""
        self.format_on_save = True
        self.vim_mode = False
        self.telemetry = True
        self.font_size = 0.55
        self.view_mode = "Split"
        self.active_tab = "main.py"
        self.selected_file = "src/app.py"
        self.expanded = {"src"}
        self.language = "Python"
        self.size_choice = "Medium"
        self.tab_size = 4
        self.tags = {"rust", "python", "ui"}
        self.advanced_open = True
        self.sort_by = "Size"
        self.descending = True
        self.selected_row = None

    def set(self, field):
        return lambda value: setattr(self, field, value)

    def section(self, title, *children, spacing=10):
        return ui.card(pz.column(list(children), spacing=spacing), title=title, width="fill")

    def view(self):
        t = self.theme
        buttons = self.section(
            "Buttons",
            pz.row([
                ui.button("Filled", lambda: None),
                ui.button("Ghost", lambda: None, variant="ghost"),
                ui.button("Outline", lambda: None, variant="outline"),
                ui.button("Solid", lambda: None, variant="solid"),
                ui.button("Disabled", disabled=True),
            ], spacing=8),
            pz.row([
                ui.button("Error", lambda: None, variant="error", icon="circle-x"),
                ui.button("Warning", lambda: None, variant="warning", icon="triangle-alert"),
                ui.button("Success", lambda: None, variant="success", icon="circle-check"),
                ui.button("Save", lambda: None, icon="save", keys="ctrl-s"),
            ], spacing=8),
            pz.row([
                ui.button("XS", lambda: None, size="xs"),
                ui.button("Small", lambda: None, size="sm"),
                ui.button("Medium", lambda: None, size="md"),
                ui.button("Large", lambda: None, size="lg", icon="rocket", variant="solid"),
            ], spacing=8, align="center"),
            pz.row([
                ui.icon_button("files", lambda: None, tooltip="Project"),
                ui.icon_button("search", lambda: None, selected=True),
                ui.icon_button("git-branch", lambda: None),
                ui.icon_button("bug", lambda: None),
                ui.icon_button("settings", lambda: None, variant="filled"),
                pz.space(width=12),
                ui.avatar("KV", index=0), ui.avatar("AL", index=3), ui.avatar("MZ", index=7),
                pz.space(width=12),
                ui.indicator("success"), ui.indicator("warning"), ui.indicator("error"),
            ], spacing=6, align="center"),
        )

        badges = self.section(
            "Badges & key bindings",
            pz.row([
                ui.badge("New"),
                ui.badge("Beta", tint="warning"),
                ui.badge("Stable", tint="success", icon="check"),
                ui.badge("Deprecated", tint="error", variant="outline"),
                ui.badge("v0.1.0", tint="accent", variant="solid"),
            ], spacing=6),
            pz.row([ui.kbd("ctrl-shift-p"), ui.kbd("ctrl-k ctrl-s"), ui.kbd("alt-enter"), ui.kbd("escape")],
                   spacing=12, align="center"),
        )

        inputs = self.section(
            "Inputs",
            ui.input(self.name, self.set("name"), placeholder="Project name"),
            ui.search_input(self.query, self.set("query"), placeholder="Search symbols…"),
            ui.field("Format on save", ui.switch(self.format_on_save, self.set("format_on_save")),
                     description="Run the formatter whenever a buffer is saved"),
            ui.field("Vim mode", ui.switch(self.vim_mode, self.set("vim_mode"))),
            ui.checkbox(self.telemetry, self.set("telemetry"), label="Send anonymous usage data"),
            pz.row([ui.label("Font size", size="sm", color="text_muted"),
                    ui.slider(self.font_size, self.set("font_size"))], spacing=12, align="center"),
            pz.row([ui.label("Indexing", size="sm", color="text_muted"), ui.progress(0.68)],
                   spacing=12, align="center"),
            ui.segmented(["Unified", "Split", "Inline"], self.view_mode, self.set("view_mode")),
            spacing=12,
        )

        menu = self.section(
            "Context menu",
            ui.menu([
                ui.MenuItem("Cut", lambda: None, icon="scissors", keys="ctrl-x"),
                ui.MenuItem("Copy", lambda: None, icon="copy", keys="ctrl-c"),
                ui.MenuItem("Paste", lambda: None, icon="clipboard", keys="ctrl-v"),
                ui.SEPARATOR,
                ui.MenuItem("Soft wrap", lambda: None, checked=True),
                ui.MenuItem("Show minimap", lambda: None, checked=False),
                ui.SEPARATOR,
                ui.MenuItem("Delete file", lambda: None, icon="trash-2", danger=True),
            ], width=280),
        )

        files = ui.TreeNode.from_paths(
            ["src/app.py", "src/views/editor.py", "src/views/panel.py", "tests/test_app.py", "pyproject.toml", "README.md"],
            {"src/app.py": "modified", "tests/test_app.py": "created"},
        )
        tree = self.section(
            "Tree & list",
            ui.tree(files, expanded=self.expanded, selected=self.selected_file,
                    on_toggle=lambda f: self.expanded.symmetric_difference_update({f}),
                    on_select=self.set("selected_file")),
            ui.divider(),
            ui.list_item("Recent projects", icon="history", end=ui.badge("3"), on_press=lambda: None),
            ui.list_item("Extensions", icon="blocks", end=ui.kbd("ctrl-shift-x"), on_press=lambda: None),
            spacing=6,
        )

        tabs = self.section(
            "Tabs, breadcrumbs & editor",
            pz.container(
                pz.column([
                    ui.tab_bar(
                        [ui.Tab.for_file("main.py"), ui.Tab.for_file("theme.rs", dirty=True),
                         ui.Tab.for_file("README.md", preview=True)],
                        self.active_tab,
                        on_select=self.set("active_tab"),
                        on_close=lambda _: None,
                        end=[ui.icon_button("plus", lambda: None, size="sm")],
                    ),
                    ui.toolbar([ui.breadcrumbs(["examples", self.active_tab, "def view"])]),
                    pz.container(ui.editor("gallery-snippet", SNIPPET, language="py"), height=150),
                ]),
                border_color=t.border, border_width=1, radius=t.radius, clip=True,
            ),
        )

        toasts = self.section(
            "Notifications",
            ui.toast("Update available", "Pyzed 0.2 is ready to install.", kind="info",
                     actions=[ui.button("Restart", lambda: None, size="sm", variant="solid"),
                              ui.button("Later", lambda: None, size="sm", variant="ghost")], width=None),
            ui.toast("Saved 3 files", kind="success", on_dismiss=lambda: None, width=None),
            ui.toast("Language server crashed", "rust-analyzer exited with code 101.", kind="error",
                     on_dismiss=lambda: None, width=None),
        )

        forms = self.section(
            "Forms",
            ui.field("Language", ui.select(["Python", "Rust", "TypeScript", "Go"], self.language,
                                           self.set("language"), width=160)),
            ui.field("Tab size", ui.number_field(self.tab_size, self.set("tab_size"), min=1, max=8)),
            ui.radio_group(["Small", "Medium", "Large"], self.size_choice, self.set("size_choice"), horizontal=True),
            pz.row([ui.chip(tag, on_remove=lambda tag=tag: self.tags.discard(tag)) for tag in sorted(self.tags)],
                   spacing=6),
            ui.disclosure("Advanced", ui.muted("Settings that most people never need."), open=self.advanced_open,
                          on_toggle=lambda: setattr(self, "advanced_open", not self.advanced_open)),
            pz.row([ui.split_button("Run", lambda: None, lambda: None, icon="play"),
                    ui.toggle_group([("list", "list"), ("grid", "layout-grid")], "list", lambda v: None)],
                   spacing=8),
        )
        feedback = self.section(
            "Feedback",
            ui.callout("Update available", "Pyzed 0.2 is ready.", tint="info",
                       actions=[ui.button("Update", lambda: None, size="sm", variant="solid")]),
            ui.callout("Build failed", "3 errors in src/main.rs", tint="error"),
            pz.row([ui.count_badge(3), ui.count_badge(128, tint="error"), ui.facepile(["KV", "AL", "MZ", "JD", "RS", "TT"]),
                    ui.diff_stat(42, 7)], spacing=12, align="center"),
            ui.keybinding_hint("Open file", "ctrl-p"),
        )
        files = [dict(name="main.rs", size=1200, lang="Rust"), dict(name="app.py", size=840, lang="Python"),
                 dict(name="README.md", size=310, lang="Markdown"), dict(name="theme.json", size=96, lang="JSON")]

        def sort(column):
            self.descending = not self.descending if self.sort_by == column else False
            self.sort_by = column

        data = self.section(
            "Data",
            ui.table([ui.Column("Name", "name"), ui.Column("Size", "size", width=70, align="end"),
                      ui.Column("Language", "lang")], files, sort_by=self.sort_by, descending=self.descending,
                     on_sort=sort, on_row_press=self.set("selected_row"), selected=self.selected_row, height=156),
            pz.row([ui.stat("Requests", "12.4k", delta=4.2, trend=[3, 5, 4, 6, 8, 7, 9]),
                    ui.donut([5, 3, 2], label="62%", size=88)], spacing=12, align="center"),
            ui.bar_chart([4, 8, 6, 9, 3], labels=["Mon", "Tue", "Wed", "Thu", "Fri"], width=300, height=120),
        )

        theme_picker = ui.select(pz.themes.names(), t.name, lambda name: setattr(self, "theme", pz.themes.get(name)),
                                 width=200)
        header = pz.row([
            pz.icon("layers", size=22, color=t.accent),
            ui.heading("Pyzed components", level=2),
            pz.hspace(),
            theme_picker,
        ], spacing=10, align="center")

        grid = pz.row([
            pz.column([buttons, badges, menu], spacing=16, width="fill"),
            pz.column([inputs, tree], spacing=16, width="fill"),
            pz.column([tabs, toasts], spacing=16, width="fill"),
        ], spacing=16)
        more = pz.row([
            pz.column([forms], width="fill"),
            pz.column([feedback], width="fill"),
            pz.column([data], width="fill"),
        ], spacing=16)

        return pz.container(
            pz.scrollable(pz.column([header, grid, more], spacing=20, padding=24), height="fill"),
            width="fill",
            height="fill",
            bg=t.background if not t.is_dark else t.editor,
            color=t.text,
        )


if __name__ == "__main__":
    pz.run(Gallery)
