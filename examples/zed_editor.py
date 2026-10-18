"""A recreation of the Zed editor written with Pyzed.

    python examples/zed_editor.py [folder]

Real features: project panel over the folder's files, tabs, a syntax-highlighted
editor (edit, undo, save with ctrl-s), git status colors, an outline panel, theme
switching, the command palette (ctrl-shift-p) and the file finder (ctrl-p).
The terminal panel shows static sample output; it does not run a shell.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pyzed as pz
from pyzed import Command, ui

IGNORED_SUFFIXES = (".so", ".pyd", ".dll", ".dylib", ".pyc")
IGNORED = {".git", "target", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache", "dist", ".mypy_cache"}
MAX_FILES = 3000

TERMINAL_SAMPLE = (
    "\x1b[32m~/pyzed\x1b[0m \x1b[34mmain\x1b[0m $ maturin develop --release\n"
    "🔗 Found pyo3 bindings with abi3 support\n"
    "\x1b[32m   Compiling\x1b[0m pyzed v0.1.0 (~/pyzed)\n"
    "\x1b[32m    Finished\x1b[0m `release` profile [optimized] target(s) in 41.20s\n"
    "📦 Built wheel for abi3 Python ≥ 3.9\n"
    "🛠 Installed pyzed-0.1.0\n"
    "\x1b[32m~/pyzed\x1b[0m \x1b[34mmain\x1b[0m $ python examples/zed_editor.py\n"
)


# ---------------------------------------------------------------------------
# Project helpers
# ---------------------------------------------------------------------------


def scan(root: Path) -> List[str]:
    files: List[str] = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in IGNORED for part in rel.parts) or path.suffix in IGNORED_SUFFIXES or not path.is_file():
            continue
        files.append(rel.as_posix())
        if len(files) >= MAX_FILES:
            break
    return files


def git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def git_status(root: Path) -> Dict[str, str]:
    status = {}
    for line in git(root, "status", "--porcelain").splitlines():
        code, path = line[:2], line[3:].strip()
        if "D" in code:
            status[path] = "deleted"
        elif "?" in code or "A" in code:
            status[path] = "created"
        elif code.strip():
            status[path] = "modified"
    return status


def git_markers(root: Path, path: str) -> Dict[int, str]:
    markers: Dict[int, str] = {}
    for hunk in re.finditer(r"^@@ -\d+(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", git(root, "diff", "-U0", "--", path), re.M):
        removed, start, added = int(hunk.group(1) or 1), int(hunk.group(2)), int(hunk.group(3) or 1)
        if added == 0:
            markers[max(start, 1)] = "deleted"
        for line in range(start, start + added):
            markers[line] = "created" if removed == 0 else "modified"
    return markers


SYMBOLS = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?P<kind>fn|struct|enum|trait|impl|mod|def|class)\s+(?P<name>[A-Za-z_]\w*)",
)


def outline(text: str) -> List[Tuple[int, str, str]]:
    out = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = SYMBOLS.match(line)
        if match:
            out.append((number, match["kind"], match["name"].strip()))
    return out


# ---------------------------------------------------------------------------
# The app
# ---------------------------------------------------------------------------


class Zed(pz.App):
    title = "Pyzed — a Zed-like editor in Python"
    size = (1440, 900)
    min_size = (800, 500)

    def __init__(self, root: str = ".", *, status: Optional[Dict[str, str]] = None):
        self.root = Path(root).resolve()
        self.files = scan(self.root)
        self.status = git_status(self.root) if status is None else status
        self.nodes = [ui.TreeNode(self.root.name, children=ui.TreeNode.from_paths(self.files, self.status), id="")]
        self.expanded = {""}
        self.selected: Optional[str] = None
        self.tabs: List[str] = []
        self.active: Optional[str] = None
        self.texts: Dict[str, str] = {}
        self.markers: Dict[str, Dict[int, str]] = {}
        self.dirty: set = set()
        self.cursor = (1, 1)
        self.show_left, self.show_bottom, self.show_right = True, False, False
        self.palette: Optional[str] = None  # "commands" | "files"
        self.query, self.choice = "", 0
        self.notices: List[Tuple[str, str]] = []
        self.theme = pz.themes.ONE_DARK

    def on_start(self):
        commands = []
        if self.active and self.cursor != (1, 1):
            commands.append(Command.set_editor_cursor(self.active, *self.cursor))
        if self.palette:
            commands.append(Command.focus("palette"))
        return commands

    # -- files -------------------------------------------------------------
    def open_file(self, path: str):
        if path not in self.texts:
            try:
                self.texts[path] = (self.root / path).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                self.notify("Can't open binary file", "warning")
                return
            self.markers.setdefault(path, git_markers(self.root, path))
        if path not in self.tabs:
            self.tabs.append(path)
        self.active = self.selected = path
        parts = path.split("/")
        self.expanded.update("/".join(parts[:i]) for i in range(1, len(parts)))
        self.cursor = (1, 1)

    def close_tab(self, path: str):
        if path in self.tabs:
            index = self.tabs.index(path)
            self.tabs.remove(path)
            if self.active == path:
                self.active = self.tabs[min(index, len(self.tabs) - 1)] if self.tabs else None

    def edited(self, path: str, text: str):
        self.texts[path] = text
        self.dirty.add(path)

    def save(self):
        if self.active:
            (self.root / self.active).write_text(self.texts[self.active], encoding="utf-8")
            self.dirty.discard(self.active)
            self.notify(f"Saved {self.active}", "success")

    def toggle_folder(self, folder: str):
        self.expanded.symmetric_difference_update({folder})
        self.selected = folder

    def notify(self, text: str, kind: str = "info"):
        self.notices = (self.notices + [(text, kind)])[-3:]

    # -- palette -----------------------------------------------------------
    def commands(self) -> List[ui.PaletteItem]:
        def run(action):
            def handler():
                self.palette = None
                return action()
            return handler

        def set_theme(theme):
            return run(lambda: setattr(self, "theme", theme))

        return [
            ui.PaletteItem("file finder: toggle", run(self.open_finder), keys="ctrl-p"),
            ui.PaletteItem("workspace: toggle left dock", run(self.toggle_left), keys="ctrl-b"),
            ui.PaletteItem("workspace: toggle bottom dock", run(self.toggle_bottom), keys="ctrl-j"),
            ui.PaletteItem("workspace: toggle right dock", run(self.toggle_right), keys="ctrl-alt-b"),
            ui.PaletteItem("workspace: save", run(self.save), keys="ctrl-s"),
            ui.PaletteItem("pane: close active item", run(lambda: self.active and self.close_tab(self.active)), keys="ctrl-w"),
            ui.PaletteItem("theme selector: one dark", set_theme(pz.themes.ONE_DARK)),
            ui.PaletteItem("theme selector: one light", set_theme(pz.themes.ONE_LIGHT)),
            ui.PaletteItem("theme selector: gruvbox dark", set_theme(pz.themes.GRUVBOX_DARK)),
            ui.PaletteItem("terminal panel: toggle focus", run(self.toggle_bottom), keys="ctrl-`"),
            ui.PaletteItem("outline panel: toggle", run(self.toggle_right)),
            ui.PaletteItem("zed: about", run(lambda: self.notify("Pyzed 0.1 · Iced 0.14 · Python " + sys.version.split()[0]))),
            ui.PaletteItem("zed: quit", run(Command.exit), keys="ctrl-q"),
        ]

    def palette_matches(self):
        if self.palette == "files":
            items = [
                ui.PaletteItem(path, (lambda p=path: self.pick_file(p)), icon=pz.icons.for_file(path)[0])
                for path in self.files
            ]
            return ui.fuzzy_filter(self.query, items, key=lambda i: i.label)[:200]
        return ui.fuzzy_filter(self.query, self.commands(), key=lambda i: i.label)

    def pick_file(self, path: str):
        self.palette = None
        self.open_file(path)

    def open_palette(self, kind: str = "commands"):
        self.palette, self.query, self.choice = kind, "", 0
        return Command.focus("palette")

    def open_finder(self):
        return self.open_palette("files")

    def set_query(self, query: str):
        self.query, self.choice = query, 0

    def submit(self):
        matches = self.palette_matches()
        if matches:
            return matches[min(self.choice, len(matches) - 1)][0].on_press()

    def toggle_left(self):
        self.show_left = not self.show_left

    def toggle_bottom(self):
        self.show_bottom = not self.show_bottom

    def toggle_right(self):
        self.show_right = not self.show_right

    def on_key(self, combo: str):
        combo = combo.replace("cmd-", "ctrl-")
        if combo == "ctrl-shift-p":
            if self.palette == "commands":
                self.palette = None
                return None
            return self.open_palette()
        if combo == "ctrl-p":
            return self.open_finder()
        if self.palette:
            if combo == "escape":
                self.palette = None
            elif combo in ("down", "ctrl-n"):
                self.choice += 1
            elif combo in ("up", "ctrl-p"):
                self.choice = max(0, self.choice - 1)
            return None
        actions = {
            "ctrl-b": self.toggle_left,
            "ctrl-j": self.toggle_bottom,
            "ctrl-`": self.toggle_bottom,
            "ctrl-alt-b": self.toggle_right,
            "ctrl-s": self.save,
            "ctrl-w": lambda: self.active and self.close_tab(self.active),
            "ctrl-q": Command.exit,
        }
        if combo in actions:
            return actions[combo]()

    # -- view --------------------------------------------------------------
    def view(self):
        t = self.theme
        layout = ui.workspace(
            self.center(),
            title_bar=ui.title_bar(
                [
                    ui.title_button(self.root.name, chevron=True),
                    ui.title_button("main", icon="git-branch", muted=True),
                ],
                [
                    ui.icon_button("bell", tooltip="Notifications"),
                    ui.icon_button("sparkles", tooltip="Agent Panel"),
                    pz.space(width=4),
                    ui.avatar("KV", index=0),
                    pz.space(width=4),
                ],
            ),
            left=self.project_panel() if self.show_left else None,
            right=self.outline_panel() if self.show_right else None,
            bottom=self.terminal_panel() if self.show_bottom else None,
            status_bar=self.status_bar(),
            left_width=250,
            right_width=260,
        )
        if self.notices:
            layout = ui.toasts(layout, [
                ui.toast(text, kind=kind, on_dismiss=(lambda i=i: self.notices.pop(i)))
                for i, (text, kind) in enumerate(self.notices)
            ])
        if self.palette:
            matches = self.palette_matches()
            self.choice = min(self.choice, max(len(matches) - 1, 0))
            overlay = ui.picker(
                self.query,
                self.set_query,
                matches,
                selected=self.choice,
                input_id="palette",
                on_submit=self.submit,
                placeholder="Execute a command…" if self.palette == "commands" else "Search project files…",
            )
            layout = ui.layer(layout, overlay, on_dismiss=lambda: setattr(self, "palette", None),
                              backdrop=pz.theme.alpha("#000000", 0.12 if t.is_dark else 0.04))
        return layout

    def project_panel(self):
        return pz.scrollable(
            pz.container(
                ui.tree(self.nodes, expanded=self.expanded, selected=self.selected,
                        on_toggle=self.toggle_folder, on_select=self.open_file),
                padding=(4, 0),
            ),
            height="fill",
            scroller=self.theme.scrollbar,
            scrollbar_width=6,
        )

    def outline_panel(self):
        symbols = outline(self.texts.get(self.active or "", ""))
        rows = [
            ui.list_item(
                pz.row([ui.label(kind, color=self.theme.syntax["keyword"], size="sm", mono=True),
                        ui.label(name, mono=True, size="sm")], spacing=6),
                lambda: None,
                height=24,
                indent=8,
            )
            for _, kind, name in symbols
        ]
        return pz.column([
            ui.panel_header("Outline", [ui.icon_button("x", self.toggle_right, size="sm")], icon="list-tree"),
            pz.scrollable(pz.column(rows or [ui.muted("No symbols", size="sm")], padding=(0, 0, 8, 0)), height="fill"),
        ])

    def terminal_panel(self):
        tabs = pz.row([
            pz.container(
                pz.row([pz.icon("terminal", size=14), ui.label("zsh", size="sm")], spacing=6, align="center"),
                padding=(3, 10), bg=self.theme.editor, radius=self.theme.radius_sm,
            ),
            pz.hspace(),
            ui.icon_button("plus", size="sm"),
            ui.icon_button("maximize-2", size="sm"),
            ui.icon_button("x", self.toggle_bottom, size="sm"),
        ], align="center", padding=(4, 6))
        return pz.column([tabs, ui.terminal(TERMINAL_SAMPLE)])

    def center(self):
        if not self.active:
            return self.welcome()
        symbols = outline(self.texts.get(self.active, ""))
        scope = [f"{kind} {name}" for line, kind, name in symbols if line <= self.cursor[0]][-1:]
        tabs = ui.tab_bar(
            [ui.Tab.for_file(p, dirty=p in self.dirty, status=self.status.get(p)) for p in self.tabs],
            self.active,
            on_select=self.select_tab,
            on_close=self.close_tab,
            start=[ui.icon_button("arrow-left", size="sm"), ui.icon_button("arrow-right", size="sm")],
            end=[ui.icon_button("plus", size="sm"), ui.icon_button("columns-2", size="sm")],
        )
        toolbar = ui.toolbar(
            [ui.breadcrumbs([self.active, *scope])],
            [
                ui.icon_button("sparkles", size="sm", tooltip="Inline Assist"),
                ui.icon_button("text-search", size="sm", tooltip="Buffer Search"),
                ui.icon_button("ellipsis", size="sm"),
            ],
        )
        editor = ui.editor(
            self.active,
            self.texts[self.active],
            path=self.active,
            markers=self.markers.get(self.active),
            on_change=lambda text, p=self.active: self.edited(p, text),
            on_cursor=self.move_cursor,
        )
        return pz.column([tabs, toolbar, editor])

    def select_tab(self, path: str):
        self.active = self.selected = path

    def move_cursor(self, line: int, column: int):
        self.cursor = (line, column)

    def welcome(self):
        rows = [
            ("Open a File", "file", "ctrl-p", self.open_finder),
            ("Command Palette", "command", "ctrl-shift-p", self.open_palette),
            ("Toggle Project Panel", "panel-left", "ctrl-b", self.toggle_left),
            ("Toggle Terminal", "terminal", "ctrl-j", self.toggle_bottom),
        ]
        return pz.center(
            pz.column(
                [
                    pz.row([pz.icon("zap", size=30, color=self.theme.accent), ui.heading("Pyzed")], spacing=10, align="center"),
                    ui.muted("Code at the speed of thought — now in Python"),
                    pz.space(height=18),
                    *[
                        ui.button(label, action, icon=icon, variant="ghost", full_width=True, keys=keys)
                        for label, icon, keys, action in rows
                    ],
                ],
                spacing=4,
                width=340,
                align="center",
            )
        )

    def status_bar(self):
        language = pz.icons.language_for(self.active) if self.active else None
        return ui.status_bar(
            [
                ui.status_item(icon="panel-left", on_press=self.toggle_left, selected=self.show_left,
                               tooltip="Project Panel", keys="ctrl-b"),
                ui.status_item(icon="git-branch", on_press=lambda: None),
                ui.status_item(icon="search", on_press=self.open_finder, tooltip="File Finder", keys="ctrl-p"),
                pz.space(width=6),
                ui.status_item("0", icon="circle-x", on_press=lambda: None),
                ui.status_item("0", icon="triangle-alert", on_press=lambda: None),
            ],
            [
                ui.status_item(f"{self.cursor[0]}:{self.cursor[1]}", on_press=lambda: None) if self.active else None,
                ui.status_item(language, on_press=lambda: None) if language else None,
                ui.status_item(icon="sparkles", on_press=lambda: None),
                ui.status_item(icon="bell", on_press=lambda: None),
                ui.status_item(icon="panel-bottom", on_press=self.toggle_bottom, selected=self.show_bottom,
                               tooltip="Terminal", keys="ctrl-j"),
                ui.status_item(icon="panel-right", on_press=self.toggle_right, selected=self.show_right,
                               tooltip="Outline", keys="ctrl-alt-b"),
            ],
        )


if __name__ == "__main__":
    Zed(sys.argv[1] if len(sys.argv) > 1 else ".").run()
