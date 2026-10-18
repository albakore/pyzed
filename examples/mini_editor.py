"""A small Zed-like editor in ~150 lines: project tree, tabs, code editor, save, docks and command palette.

    python examples/mini_editor.py [folder]

Walkthrough: https://albakore.github.io/pyzed/tutorials/zed-like-editor/
For a fuller version see examples/zed_editor.py.
"""

import os
import sys
from pathlib import Path

import pyzed as pz
from pyzed import Command, icons, ui

IGNORED = {".git", "target", "node_modules", "__pycache__", ".venv", "dist"}


class MiniEditor(pz.App):
    size = (1100, 700)

    def __init__(self, root="."):
        self.root = Path(root).resolve()
        self.nodes = ui.TreeNode.from_paths(self.scan()[:2000])
        self.expanded = set()
        self.open_tabs = []      # paths, in tab order
        self.active = None
        self.texts = {}          # path -> current text
        self.dirty = set()
        self.cursor = (1, 1)
        self.show_left = True
        self.palette_open = False
        self.query = ""

    def scan(self):
        files = []
        for folder, dirs, names in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in IGNORED]
            rel = Path(folder).relative_to(self.root)
            files += [(rel / n).as_posix() for n in names]
        return files

    def title(self):
        name = self.active or "sin archivos"
        return f"{name} — {self.root.name}"

    # -- files ------------------------------------------------------------------
    def open_file(self, path):
        if path not in self.texts:
            try:
                self.texts[path] = (self.root / path).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                return
        if path not in self.open_tabs:
            self.open_tabs.append(path)
        self.active = path

    def close_tab(self, path):
        index = self.open_tabs.index(path)
        self.open_tabs.remove(path)
        if self.active == path:
            self.active = self.open_tabs[min(index, len(self.open_tabs) - 1)] if self.open_tabs else None

    def edited(self, text):
        self.texts[self.active] = text
        self.dirty.add(self.active)

    def save(self):
        if self.active in self.dirty:
            (self.root / self.active).write_text(self.texts[self.active], encoding="utf-8")
            self.dirty.discard(self.active)

    def toggle_folder(self, folder):
        self.expanded ^= {folder}

    # -- commands & keys ----------------------------------------------------------
    def toggle_left(self):
        self.show_left = not self.show_left

    def toggle_theme(self):
        self.theme = pz.themes.ONE_LIGHT if self.theme.is_dark else pz.themes.ONE_DARK

    def commands(self):
        return [
            ui.PaletteItem("workspace: save", self.save, keys="ctrl-s", icon="save"),
            ui.PaletteItem("workspace: toggle left dock", self.toggle_left, keys="ctrl-b", icon="panel-left"),
            ui.PaletteItem("theme: toggle light/dark", self.toggle_theme, icon="sun-moon"),
            ui.PaletteItem("pane: close active item", lambda: self.active and self.close_tab(self.active),
                           keys="ctrl-w", icon="x"),
        ]

    def run_first_match(self):
        matches = ui.fuzzy_filter(self.query, self.commands(), key=lambda c: c.label)
        self.palette_open = False
        if matches:
            return matches[0][0].on_press()

    def on_key(self, combo):
        combo = combo.replace("cmd-", "ctrl-")
        if combo == "ctrl-shift-p":
            self.palette_open, self.query = True, ""
            return Command.focus("command-palette")
        if combo == "escape":
            self.palette_open = False
        elif combo == "ctrl-s":
            self.save()
        elif combo == "ctrl-b":
            self.toggle_left()
        elif combo == "ctrl-w" and self.active:
            self.close_tab(self.active)

    # -- view -----------------------------------------------------------------------
    def center(self):
        if not self.active:
            return pz.center(pz.column([ui.heading("Mini editor", level=2),
                                        ui.muted("Abre un archivo del panel de proyecto."),
                                        ui.kbd("ctrl-shift-p")], spacing=8, align="center"))
        tabs = [ui.Tab.for_file(p, dirty=p in self.dirty) for p in self.open_tabs]
        return pz.column([
            ui.tab_bar(tabs, self.active, on_select=lambda p: setattr(self, "active", p), on_close=self.close_tab),
            ui.toolbar([ui.breadcrumbs(self.active.split("/"))]),
            ui.editor(self.active, self.texts[self.active], path=self.active, on_change=self.edited,
                      on_cursor=lambda line, col: setattr(self, "cursor", (line, col))),
        ])

    def view(self):
        project = pz.column([
            ui.panel_header(self.root.name, [ui.icon_button("chevrons-down-up", lambda: self.expanded.clear(),
                                                            size="xs", tooltip="Plegar todo")]),
            pz.scrollable(ui.tree(self.nodes, expanded=self.expanded, selected=self.active,
                                  on_toggle=self.toggle_folder, on_select=self.open_file), height="fill"),
        ])
        line, col = self.cursor
        layout = ui.workspace(
            self.center(),
            title_bar=ui.title_bar([ui.title_button(self.root.name, chevron=True)],
                                   [ui.icon_button("sun-moon", self.toggle_theme, size="sm", tooltip="Tema")]),
            left=project if self.show_left else None,
            status_bar=ui.status_bar(
                [ui.status_item(icon="panel-left", on_press=self.toggle_left, selected=self.show_left,
                                tooltip="Panel de proyecto", keys="ctrl-b")],
                [ui.status_item(f"Ln {line}, Col {col}") if self.active else None,
                 ui.status_item(icons.language_for(self.active)) if self.active else None],
            ),
        )
        palette = None
        if self.palette_open:
            palette = ui.command_palette(self.query, lambda q: setattr(self, "query", q), self.commands(),
                                         on_submit=self.run_first_match)
        return ui.layer(layout, palette, on_dismiss=lambda: setattr(self, "palette_open", False))


if __name__ == "__main__":
    pz.run(MiniEditor(sys.argv[1] if len(sys.argv) > 1 else "."))
