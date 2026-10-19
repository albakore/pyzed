"""Every designer command in one table: the menus, the command palette, the keyboard and the shortcut list read it.

An ``Action`` names a command, its group (the menu it is in), icon and key binding,
and what it does to a ``Designer``. Adding a row here makes the command show up
everywhere at once.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple

from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: Menu order.
GROUPS = ("File", "Edit", "View", "Run", "Help")


def _always(_d: "Designer") -> bool:
    return True


@dataclass(frozen=True)
class Action:
    id: str
    #: The English label; ``label`` is the one in the designer's language.
    text: str
    group: str
    run: Callable[["Designer"], Any]
    icon: Optional[str] = None
    keys: Optional[str] = None
    enabled: Callable[["Designer"], bool] = _always
    #: For toggles: whether the option is on (shown as a check mark).
    checked: Optional[Callable[["Designer"], bool]] = None
    #: Keys that work anywhere (also while typing in the code editor).
    global_keys: bool = False
    #: Hidden from menus (still in the palette and the shortcut list).
    menu: bool = True

    @property
    def label(self) -> str:
        """The command's text in the designer's language."""
        return tr(self.text)


def _has_selection(d: "Designer") -> bool:
    return bool(d.doc.selection)


ACTIONS: Tuple[Action, ...] = (
    # File
    Action("new", "New form…", "File", lambda d: d.new(), "file-plus", "ctrl-n", global_keys=True),
    Action("new_component", "New component…", "File", lambda d: d.new_component(), "component", "ctrl-shift-n",
           global_keys=True),
    Action("open", "Open…", "File", lambda d: d.open_dialog(), "folder-open", "ctrl-o", global_keys=True),
    Action("save", "Save", "File", lambda d: d.save(), "save", "ctrl-s", global_keys=True),
    Action("save_as", "Save as…", "File", lambda d: d.show_save_as(), "save-all", "ctrl-shift-s", global_keys=True),
    Action("settings", "Settings…", "File", lambda d: d.open_settings(), "settings", "ctrl-,", global_keys=True),
    # Edit
    Action("undo", "Undo", "Edit", lambda d: d.undo(), "undo-2", "ctrl-z", lambda d: d.doc.history.can_undo),
    Action("redo", "Redo", "Edit", lambda d: d.redo(), "redo-2", "ctrl-shift-z", lambda d: d.doc.history.can_redo),
    Action("cut", "Cut", "Edit", lambda d: d.cut(), "scissors", "ctrl-x", _has_selection),
    Action("copy", "Copy", "Edit", lambda d: d.copy(), "copy", "ctrl-c", _has_selection),
    Action("paste", "Paste", "Edit", lambda d: d.paste(), "clipboard", "ctrl-v", lambda d: bool(d.doc.clipboard)),
    Action("duplicate", "Duplicate", "Edit", lambda d: d.duplicate(), "copy-plus", "ctrl-d", _has_selection),
    Action("delete", "Delete", "Edit", lambda d: d.delete(), "trash-2", "delete", _has_selection),
    Action("select_all", "Select all", "Edit", lambda d: d.select_all(), "box-select", "ctrl-a"),
    Action("add_control", "Add control…", "Edit", lambda d: d.open_add_child(None), "plus", "ctrl-shift-a",
           global_keys=True),
    Action("group_row", "Group in a row", "Edit", lambda d: d.wrap("row"), "columns-3", None, _has_selection),
    Action("group_column", "Group in a column", "Edit", lambda d: d.wrap("column"), "rows-3", None, _has_selection),
    Action("group_grid", "Group in a grid", "Edit", lambda d: d.wrap("grid"), "layout-grid", None, _has_selection),
    # View
    Action("palette", "Command palette…", "View", lambda d: d.open_palette(), "search", "ctrl-shift-p",
           global_keys=True),
    Action("left_dock", "Left dock", "View", lambda d: d.toggle_dock("left"), "panel-left", "ctrl-b",
           checked=lambda d: d.dock_visible("left"), global_keys=True),
    Action("right_dock", "Right dock", "View", lambda d: d.toggle_dock("right"), "panel-right", "ctrl-alt-b",
           checked=lambda d: d.dock_visible("right"), global_keys=True),
    Action("bottom_dock", "Bottom dock", "View", lambda d: d.toggle_dock("bottom"), "panel-bottom", "ctrl-j",
           checked=lambda d: d.dock_visible("bottom"), global_keys=True),
    Action("console", "Console", "View", lambda d: d.show_panel("console"), "terminal", "ctrl-shift-y",
           global_keys=True),
    Action("toolbar", "Toolbar", "View", lambda d: d.toggle_pref("show_toolbar"), "wrench",
           checked=lambda d: d.prefs.show_toolbar),
    Action("status_bar", "Status bar", "View", lambda d: d.toggle_pref("show_status_bar"), "panel-bottom-close",
           checked=lambda d: d.prefs.show_status_bar),
    Action("grid", "Grid", "View", lambda d: d.toggle_pref("show_grid"), "grid-3x3", "g",
           checked=lambda d: d.show_grid),
    Action("snap", "Snap to grid", "View", lambda d: d.toggle_pref("snap"), "magnet", checked=lambda d: d.snap),
    Action("guides", "Smart guides", "View", lambda d: d.toggle_pref("smart_guides"), "ruler",
           checked=lambda d: d.smart_guides),
    Action("hidden", "Show hidden controls", "View", lambda d: d.toggle_pref("show_hidden"), "eye",
           checked=lambda d: d.show_hidden),
    Action("reset_layout", "Reset panel layout", "View", lambda d: d.reset_layout(), "layout-dashboard"),
    # Run
    Action("run", "Run", "Run", lambda d: d.run_form(), "play", "f5", global_keys=True),
    Action("stop", "Stop", "Run", lambda d: d.stop_form(), "square", "shift-f5", global_keys=True),
    Action("code_file", "Edit code file", "Run", lambda d: d.edit_whole_file(), "code", "f7", global_keys=True),
    # Help
    Action("shortcuts", "Keyboard shortcuts", "Help", lambda d: d.open_dialog_named("shortcuts"), "keyboard", "f1",
           global_keys=True),
    Action("docs", "Documentation", "Help", lambda d: d.open_docs(), "book-open"),
    Action("issue", "Report a problem", "Help", lambda d: d.open_url(ISSUES_URL), "bug"),
    Action("about", "About Pyzed Designer", "Help", lambda d: d.open_dialog_named("about"), "info"),
)

DOCS_URL = "https://albakore.github.io/pyzed/guides/designer/"
ISSUES_URL = "https://github.com/albakore/pyzed/issues"

#: Shortcuts that are not commands of their own, for the reference list.
EXTRA_SHORTCUTS: Tuple[Tuple[str, Sequence[Tuple[str, str]]], ...] = (
    ("Canvas", (("Move by one pixel", "left"), ("Move by one grid step", "shift-left"),
                ("Open the main event", "enter"), ("Cancel the current gesture", "escape"))),
    ("Code", (("Show completions", "ctrl-space"), ("Accept completion", "enter"), ("Close completions", "escape"))),
)

BY_ID: Dict[str, Action] = {a.id: a for a in ACTIONS}


def run(action_id: str, d: "Designer") -> Any:
    """Runs the command ``action_id`` on designer ``d`` if it is enabled; returns its result or ``None``."""
    action = BY_ID[action_id]
    return action.run(d) if action.enabled(d) else None


def by_keys(combo: str, *, global_only: bool = False) -> Optional[Action]:
    """Returns the command bound to key ``combo`` (``cmd-`` also matches ``ctrl-`` for global keys).

    With ``global_only``, only commands whose keys work anywhere are considered.
    """
    for action in ACTIONS:
        if action.keys == combo and (action.global_keys or not global_only):
            return action
        if action.keys and combo == action.keys.replace("ctrl-", "cmd-") and action.global_keys:
            return action
    return None


def groups() -> List[Tuple[str, List[Action]]]:
    """Returns the commands of each menu, in menu order, as ``(group, actions)`` pairs."""
    return [(g, [a for a in ACTIONS if a.group == g]) for g in GROUPS]


def shortcut_groups() -> List[Tuple[str, List[Tuple[str, str]]]]:
    """Returns the keyboard shortcut reference as ``(title, [(label, keys), ...])`` groups, translated,
    with the extra non-command shortcuts and without empty groups.
    """
    out = [(tr(g), [(a.label.rstrip("…"), a.keys) for a in items if a.keys]) for g, items in groups()]
    out += [(tr(title), [(tr(label), keys) for label, keys in items]) for title, items in EXTRA_SHORTCUTS]
    return [(g, items) for g, items in out if items]
