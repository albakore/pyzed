"""The designer's key bindings, like Zed's keymap: every action of the designer and its code editor, the keys
that run it and the context where they work, with the user's changes saved in ``keymap.json``.

The file sits next to ``designer.json`` (see ``settings.config_dir``) and has Zed's format: a list of blocks,
each with a ``context`` and its ``bindings`` from keys to an action, or to ``null`` to take a default key
away (``//`` comments and trailing commas are allowed)::

    [
      {"context": "Workspace", "bindings": {"ctrl-alt-s": "workspace::SaveAs"}},
      {"context": "Editor", "bindings": {"ctrl-shift-d": "editor::DuplicateLineDown", "ctrl-d": null}}
    ]

A key is looked up from the deepest context that has the keyboard to the outermost one (``Editor``, then
``CodePanel``, then ``Workspace``), and in each context the last binding wins, so the user's beat the defaults.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ..ui.editor import DEFAULT_KEYS
from ..ui.editor import _keystroke as _stroke
from . import commands as _commands
from .settings import config_dir

#: The contexts, from the outermost, with what has the keyboard in each.
CONTEXTS: Dict[str, str] = {
    "Workspace": "Anywhere in the designer",
    "Canvas": "The form canvas",
    "ProjectPanel": "The project tree",
    "CodePanel": "The code panel",
    "Editor": "The code editor",
}
#: What the user's ``keymap.json`` starts with when it is created.
HEADER = ("// Pyzed Design key bindings, in Zed's format: each block has a context (Workspace, Canvas,\n"
          "// ProjectPanel, CodePanel or Editor) and its bindings from keys to an action, or to null to\n"
          "// take a default key away. Your bindings win over the defaults; see File → Keymap editor.\n")


@dataclass(frozen=True)
class ActionInfo:
    #: ``"namespace::snake_name"``, such as ``"workspace::save_as"``.
    id: str
    #: The English label (``tr`` translates it).
    label: str
    #: The group it is listed in (a menu, ``"Canvas"``, ``"Lines"``...).
    category: str
    #: Where new keys for it work unless another context is chosen.
    context: str

    @property
    def title(self) -> str:
        """The label in the designer's language, without a trailing "…"."""
        from .locale import tr

        return tr(self.label).rstrip("…")

    @property
    def name(self) -> str:
        """The name written in ``keymap.json``, like Zed's: ``"workspace::SaveAs"``."""
        return display_name(self.id)


@dataclass(frozen=True)
class Binding:
    #: Normalized keys: ``"ctrl-shift-k"`` or a chord such as ``"ctrl-k ctrl-c"``.
    keys: str
    #: The action id, or ``None`` for a key bound to nothing (it removes the defaults).
    action: Optional[str]
    context: str
    #: From the user's ``keymap.json`` (else a default binding).
    user: bool = False


# -- the actions -------------------------------------------------------------------------------------------

_CANVAS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    ("nudge_left", "Move left by one pixel", ("left",)),
    ("nudge_right", "Move right by one pixel", ("right",)),
    ("nudge_up", "Move up by one pixel", ("up",)),
    ("nudge_down", "Move down by one pixel", ("down",)),
    ("nudge_grid_left", "Move left by one grid step", ("shift-left",)),
    ("nudge_grid_right", "Move right by one grid step", ("shift-right",)),
    ("nudge_grid_up", "Move up by one grid step", ("shift-up",)),
    ("nudge_grid_down", "Move down by one grid step", ("shift-down",)),
    ("open_main_event", "Open the main event", ("enter",)),
)
#: Commands that also have a second key on the canvas.
_CANVAS_EXTRA = (("ctrl-y", "workspace::redo"), ("backspace", "workspace::delete"))

#: The project tree's actions, by Zed's names.
_PROJECT_PANEL: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    ("open", "Open", ("enter",)),
    ("open_with_system", "Open in Default App", ("ctrl-shift-enter",)),
    ("new_file", "New file", ("ctrl-n",)),
    ("new_directory", "New folder", ("alt-n",)),
    ("rename", "Rename", ("f2",)),
    ("cut", "Cut", ("ctrl-x",)),
    ("copy", "Copy", ("ctrl-c",)),
    ("paste", "Paste", ("ctrl-v",)),
    ("duplicate", "Duplicate", ("ctrl-d",)),
    ("undo", "Undo", ("ctrl-z",)),
    ("redo", "Redo", ("ctrl-shift-z", "ctrl-y")),
    ("trash", "Move to the trash", ("delete",)),
    ("delete", "Delete", ("ctrl-delete",)),
    ("reveal_in_file_manager", "Reveal in File Manager", ("ctrl-alt-r",)),
    ("copy_path", "Copy Path", ("alt-shift-c",)),
    ("copy_relative_path", "Copy Relative Path", ("ctrl-alt-shift-c",)),
    ("expand_selected_entry", "Expand folder", ("right",)),
    ("collapse_selected_entry", "Collapse folder", ("left",)),
    ("select_previous", "Previous entry", ("up",)),
    ("select_next", "Next entry", ("down",)),
    ("cancel", "Forget the cut or copied file", ("escape",)),
)

#: The code panel's own actions (around the editor: completions, search, go to line, wrapping).
_CODE_PANEL: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    ("show_completions", "Show completions", ("ctrl-space",)),
    ("find", "Find", ("ctrl-f",)),
    ("replace", "Find and replace", ("ctrl-h",)),
    ("go_to_line", "Go to line", ("ctrl-g",)),
    ("toggle_soft_wrap", "Toggle soft wrap", ("alt-z",)),
)

#: The code editor's actions by group (their keys are ``ui.editor.DEFAULT_KEYS``).
_EDITOR: Tuple[Tuple[str, Tuple[Tuple[str, str], ...]], ...] = (
    ("Editing", (("undo", "Undo"), ("redo", "Redo"), ("copy", "Copy"), ("cut", "Cut"),
                 ("delete_to_previous_word_start", "Delete the previous word"),
                 ("delete_to_next_word_end", "Delete the next word"), ("toggle_comments", "Toggle comment"),
                 ("convert_to_upper_case", "Upper case"), ("convert_to_lower_case", "Lower case"),
                 ("sort_lines_case_sensitive", "Sort lines"))),
    ("Multiple cursors", (("select_next", "Select the next match"),
                          ("select_previous", "Select the previous match"),
                          ("select_all_matches", "Select every match"), ("add_selection_above", "Add a cursor above"),
                          ("add_selection_below", "Add a cursor below"),
                          ("split_selection_into_lines", "A cursor on each selected line"),
                          ("undo_selection", "Undo the last cursor change"), ("cancel", "Back to one cursor"))),
    ("Lines", (("select_line", "Select line"), ("move_line_up", "Move line up"),
               ("move_line_down", "Move line down"), ("duplicate_line_up", "Duplicate line up"),
               ("duplicate_line_down", "Duplicate line down"),
               ("duplicate_selection", "Duplicate selection"), ("delete_line", "Delete line"),
               ("join_lines", "Join lines"), ("newline_below", "New line below"),
               ("newline_above", "New line above"), ("indent", "Indent"), ("outdent", "Outdent"))),
    ("Moving", (("move_to_enclosing_bracket", "Go to matching bracket"),
                ("move_to_beginning_of_line", "Go to the start of the line"),
                ("select_to_beginning_of_line", "Select to the start of the line"),
                ("line_up", "Scroll up one line"), ("line_down", "Scroll down one line"))),
    ("Folding", (("fold", "Fold"), ("unfold_lines", "Unfold"), ("toggle_fold", "Toggle fold"),
                 ("fold_all", "Fold everything"), ("unfold_all", "Unfold everything"))),
)

#: Keys that are not actions of their own, for the shortcut reference (they cannot be changed).
FIXED: Tuple[Tuple[str, Tuple[Tuple[str, str], ...]], ...] = (
    ("Canvas", (("Cancel the current gesture", "escape"),)),
    ("Code panel", (("Accept completion", "enter"), ("Close completions", "escape"),
                    ("Next and previous match", "f3"), ("Bigger, smaller and default font", "ctrl-="))),
    ("Multiple cursors", (("Add a cursor", "alt-click"),)),
)

_ACTIONS: Optional[Dict[str, ActionInfo]] = None


def actions() -> Dict[str, ActionInfo]:
    """Every action that keys can run, by id, in the order the keymap editor lists them."""
    global _ACTIONS
    if _ACTIONS is None:
        out: Dict[str, ActionInfo] = {}

        def add(info: ActionInfo) -> None:
            out[info.id] = info

        for a in _commands.ACTIONS:
            add(ActionInfo(f"workspace::{a.id}", a.text, a.group,
                           "Workspace" if a.global_keys or not a.keys else "Canvas"))
        for name, label, _ in _CANVAS:
            add(ActionInfo(f"canvas::{name}", label, "Canvas", "Canvas"))
        for name, label, _ in _PROJECT_PANEL:
            add(ActionInfo(f"project_panel::{name}", label, "Project tree", "ProjectPanel"))
        for name, label, _ in _CODE_PANEL:
            add(ActionInfo(f"code_panel::{name}", label, "Code panel", "CodePanel"))
        for category, items in _EDITOR:
            for name, label in items:
                add(ActionInfo(f"editor::{name}", label, category, "Editor"))
        _ACTIONS = out
    return _ACTIONS


def default_bindings() -> List[Binding]:
    """The bindings the designer ships with."""
    out = []
    for a in _commands.ACTIONS:
        if a.keys:
            out.append(Binding(a.keys, f"workspace::{a.id}", "Workspace" if a.global_keys else "Canvas"))
    out += [Binding(keys, action, "Canvas") for keys, action in _CANVAS_EXTRA]
    for namespace, context, table in (("canvas", "Canvas", _CANVAS), ("project_panel", "ProjectPanel", _PROJECT_PANEL),
                                      ("code_panel", "CodePanel", _CODE_PANEL)):
        out += [Binding(keys, f"{namespace}::{name}", context) for name, _, all_keys in table for keys in all_keys]
    for _, items in _EDITOR:
        out += [Binding(keys, f"editor::{name}", "Editor") for name, _ in items for keys in DEFAULT_KEYS.get(name, ())]
    return out


def display_name(action_id: str) -> str:
    """``"workspace::save_as"`` -> ``"workspace::SaveAs"`` (Zed's way of writing actions)."""
    namespace, _, name = action_id.partition("::")
    return f"{namespace}::{''.join(part.capitalize() for part in name.split('_'))}"


def action_id(name: str) -> Optional[str]:
    """The id of the action written ``name`` (``"workspace::SaveAs"``, ``"workspace::save_as"``, or just
    ``"save_as"`` when one action has that name), or ``None``."""
    name = name.strip()
    namespace, sep, rest = name.rpartition("::")
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", rest).lower()
    known = actions()
    if sep:
        candidate = f"{namespace.lower()}::{snake}"
        return candidate if candidate in known else None
    found = [a for a in known if a.split("::", 1)[1] == snake]
    return found[0] if len(found) == 1 else None


# -- keys --------------------------------------------------------------------------------------------------

def normalize(keys: str, context: str = "Workspace") -> Optional[str]:
    """Normalizes ``keys`` (``"Ctrl+Shift+K"`` -> ``"ctrl-shift-k"``, ``"ctrl-k ctrl-s"``; Cmd counts as Ctrl),
    also the designer's ``"ctrl- "`` for Ctrl+Space; ``None`` if they are not keys. A chord has two keys, and
    in the ``Editor`` context it must start with Ctrl+K like the editor's own."""
    if keys.endswith(" ") and (len(keys) == 1 or keys[-2] in "-+"):
        keys = keys[:-1] + "space"
    strokes = [_stroke(part) for part in keys.split()]
    if not strokes or len(strokes) > 2 or None in strokes:
        return None
    if context == "Editor" and len(strokes) == 2 and strokes[0] != "ctrl-k":
        return None
    return " ".join(strokes)  # type: ignore[arg-type]


def _strip_comments(text: str) -> str:
    """Removes ``//`` comments and trailing commas (outside strings) so ``json`` can read Zed's keymaps."""
    out, i, in_string = [], 0, False
    while i < len(text):
        c = text[i]
        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 1
            elif c == '"':
                in_string = False
        elif c == '"':
            in_string = True
            out.append(c)
        elif text.startswith("//", i):
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        else:
            out.append(c)
        i += 1
    return re.sub(r",(\s*[\]}])", r"\1", "".join(out))


def _context_name(text: str) -> Optional[str]:
    return next((c for c in CONTEXTS if c.lower() == text.strip().lower()), None)


# -- the keymap --------------------------------------------------------------------------------------------

class Keymap:
    """The defaults plus the user's bindings from ``path`` (reloaded when the file changes)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.defaults = default_bindings()
        self.user: List[Binding] = []
        #: Problems found in the file, to show in the keymap editor.
        self.errors: List[str] = []
        self._stamp: Optional[float] = None
        self._checked = 0.0
        self._active: Optional[List[Binding]] = None
        self.load()

    # -- the file ------------------------------------------------------------------------------------------
    def _mtime(self) -> Optional[float]:
        try:
            return self.path.stat().st_mtime
        except OSError:
            return None

    def load(self) -> None:
        """Reads the user's bindings from the file (none if it is missing), noting what is wrong in it."""
        self._stamp = self._mtime()
        self._active = None
        self.user, self.errors = [], []
        try:
            text = self.path.read_text(encoding="utf-8")
        except OSError:
            return
        try:
            data = json.loads(_strip_comments(text) or "[]")
        except ValueError as err:
            self.errors.append(f"keymap.json: {err}")
            return
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            self.errors.append("keymap.json: expected a list of blocks with a context and bindings")
            return
        for block in data:
            if not isinstance(block, dict) or not isinstance(block.get("bindings", {}), dict):
                self.errors.append("keymap.json: each block needs a \"bindings\" object")
                continue
            context = _context_name(str(block.get("context") or "Workspace"))
            if context is None:
                self.errors.append(f"Unknown context {block.get('context')!r} (use {', '.join(CONTEXTS)})")
                continue
            for keys, value in block.get("bindings", {}).items():
                binding = self._parse(keys, value, context)
                if binding is not None:
                    self.user.append(binding)

    def _parse(self, keys: str, value: object, context: str) -> Optional[Binding]:
        normalized = normalize(keys, context)
        if normalized is None:
            self.errors.append(f"{keys!r}: not keys this context understands" if context == "Editor"
                               else f"{keys!r}: not valid keys")
            return None
        if isinstance(value, list) and value:  # Zed's ["action", {arguments}]
            value = value[0]
        if value is None or value in ("", "NoAction", "zed::NoAction"):
            return Binding(normalized, None, context, True)
        found = action_id(value) if isinstance(value, str) else None
        if found is None:
            self.errors.append(f"{keys!r}: unknown action {value!r}")
            return None
        return Binding(normalized, found, context, True)

    def refresh(self) -> bool:
        """Reloads the file if it changed since it was read (checked at most twice a second)."""
        now = time.monotonic()
        if now - self._checked < 0.5:
            return False
        self._checked = now
        if self._mtime() == self._stamp:
            return False
        self.load()
        return True

    def save(self) -> Optional[Path]:
        """Writes the user's bindings, grouped by context in Zed's format; ``None`` if it could not."""
        blocks: List[Dict[str, object]] = []
        for b in self.user:
            current = blocks[-1] if blocks else None
            if current is None or current["context"] != b.context or b.keys in current["bindings"]:  # type: ignore
                current = {"context": b.context, "bindings": {}}
                blocks.append(current)
            current["bindings"][b.keys] = display_name(b.action) if b.action else None  # type: ignore[index]
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(HEADER + json.dumps(blocks, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError as err:
            self.errors = [f"keymap.json: {err}"]
            return None
        self._stamp = self._mtime()
        self._active = None
        self.errors = []
        return self.path

    def ensure_file(self) -> Path:
        """Creates the file (with no bindings) if it is missing, to open it as text; returns its path."""
        if not self.path.exists():
            self.save()
        return self.path

    # -- looking keys up ------------------------------------------------------------------------------------
    @property
    def active(self) -> List[Binding]:
        """The bindings in force: the defaults then the user's, without the ones a ``null`` took away."""
        if self._active is None:
            out: List[Binding] = []
            for b in [*self.defaults, *self.user]:
                if b.action is None:
                    out = [o for o in out if (o.context, o.keys) != (b.context, b.keys)]
                else:
                    out.append(b)
            self._active = out
        return self._active

    def resolve(self, keys: str, contexts: Sequence[str]) -> Optional[str]:
        """The action ``keys`` run with ``contexts`` (deepest first) having the keyboard, or ``None``."""
        for context in contexts:
            for b in reversed(self.active):
                if b.context == context and b.keys == keys:
                    return b.action
        return None

    def is_prefix(self, keys: str, contexts: Iterable[str]) -> bool:
        """Whether ``keys`` starts a chord bound in one of ``contexts``."""
        contexts = set(contexts)
        return any(b.context in contexts and b.keys.startswith(keys + " ") for b in self.active)

    def bindings_for(self, action: str) -> List[Binding]:
        """The bindings in force for ``action``."""
        return [b for b in self.active if b.action == action]

    def keys_for(self, action: str) -> Optional[str]:
        """The first keys of ``action`` (for menus and the palette), or ``None``."""
        found = self.bindings_for(action)
        return found[0].keys if found else None

    def conflicts(self) -> Dict[Tuple[str, str], List[Binding]]:
        """The keys bound to more than one action in the same context: ``{(context, keys): bindings}``; the
        last binding is the one that runs."""
        groups: Dict[Tuple[str, str], List[Binding]] = {}
        for b in self.active:
            groups.setdefault((b.context, b.keys), []).append(b)
        return {k: v for k, v in groups.items() if len({b.action for b in v}) > 1}

    def is_changed(self, action: str) -> bool:
        """Whether the user changed the keys of ``action``."""
        removed = {(b.context, b.keys) for b in self.user if b.action is None}
        return any(b.action == action for b in self.user) or any(
            (b.context, b.keys) in removed for b in self.defaults if b.action == action)

    # -- changing it ------------------------------------------------------------------------------------------
    def check(self, action: str, keys: str, context: str) -> Tuple[Optional[str], Optional[str]]:
        """Validates new ``keys`` for ``action`` in ``context``: ``(normalized, error)``."""
        if context not in CONTEXTS:
            return None, f"Unknown context {context!r}"
        normalized = normalize(keys, context)
        if normalized is None:
            return None, ("In the editor a chord must start with ctrl-k" if context == "Editor" and len(keys.split()) == 2
                          else "Not valid keys")
        return normalized, None

    def add(self, action: str, keys: str, context: Optional[str] = None) -> Optional[str]:
        """Binds ``keys`` to ``action`` (in its usual context by default); returns an error or ``None``."""
        context = context or actions()[action].context
        normalized, error = self.check(action, keys, context)
        if normalized is None:
            return error
        self.user.append(Binding(normalized, action, context, True))
        self._active = None
        return None

    def change(self, binding: Binding, keys: str, context: Optional[str] = None) -> Optional[str]:
        """Changes the keys (and context) of ``binding``: a user binding is edited in place, a default one is
        taken away and bound again. Returns an error or ``None``."""
        context = context or binding.context
        assert binding.action is not None
        normalized, error = self.check(binding.action, keys, context)
        if normalized is None:
            return error
        if (normalized, context) == (binding.keys, binding.context):
            return None
        new = Binding(normalized, binding.action, context, True)
        if binding.user and binding in self.user:
            self.user[self.user.index(binding)] = new
        else:
            self.user += [Binding(binding.keys, None, binding.context, True), new]
        self._active = None
        return None

    def remove(self, binding: Binding) -> None:
        """Takes ``binding`` away (a default one with a ``null`` in the user's file)."""
        if binding.user and binding in self.user:
            self.user.remove(binding)
        else:
            self.user.append(Binding(binding.keys, None, binding.context, True))
        self._active = None

    def reset(self, action: str) -> None:
        """Puts back the default keys of ``action``, dropping the user's bindings for it."""
        defaults = {(b.context, b.keys) for b in self.defaults if b.action == action}
        self.user = [b for b in self.user if b.action != action
                     and not (b.action is None and (b.context, b.keys) in defaults)]
        self._active = None

    def reset_all(self) -> None:
        """Drops every user binding."""
        self.user = []
        self._active = None

    def migrate(self, overrides: Dict[str, str]) -> None:
        """Turns the code editor's old per-action keys (``{"delete_line": "ctrl-shift-d"}`` in
        ``designer.json``) into bindings, unless ``keymap.json`` already exists."""
        if self.path.exists() or not overrides:
            return
        for name, keys in overrides.items():
            namespace = "editor" if name in DEFAULT_KEYS else "code_panel"
            action = f"{namespace}::{name}"
            if action not in actions():
                continue
            context = actions()[action].context
            for b in self.defaults:
                if b.action == action:
                    self.user.append(Binding(b.keys, None, context, True))
            for key in (k.strip() for k in keys.split(",")):
                normalized = normalize(key, context) if key else None
                if normalized:
                    self.user.append(Binding(normalized, action, context, True))
        self._active = None
        self.save()

    # -- the code editor ------------------------------------------------------------------------------------
    def editor_keymap(self) -> Dict[str, Optional[str]]:
        """The ``ui.editor(keymap=...)`` for the user's ``Editor`` bindings: their editor actions, and nothing
        for keys taken away or bound to the designer's actions (so the editor leaves those keys to it)."""
        out: Dict[str, Optional[str]] = {}
        for b in self.user:
            if b.context == "Editor":
                out[b.keys] = b.action.split("::", 1)[1] if b.action and b.action.startswith("editor::") else None
        return out

    def captured(self, contexts: Sequence[str]) -> Tuple[str, ...]:
        """Keys without Ctrl bound to the designer's actions in ``contexts`` that the editor would otherwise
        type or use (Alt+Z), so it hands them over (function keys reach the designer anyway)."""
        out = []
        for b in self.active:
            if b.context in contexts and " " not in b.keys and not b.keys.startswith("ctrl-") \
                    and not re.search(r"(^|-)f\d+$", b.keys) \
                    and not (b.action or "").startswith("editor::") and b.keys not in out:
                out.append(b.keys)
        return tuple(out)


_KEYMAP: Optional[Keymap] = None


def keymap_path() -> Path:
    """The user's ``keymap.json``, in the Pyzed config folder."""
    return config_dir() / "keymap.json"


def get() -> Keymap:
    """The keymap of the current config folder (one per folder)."""
    global _KEYMAP
    path = keymap_path()
    if _KEYMAP is None or _KEYMAP.path != path:
        _KEYMAP = Keymap(path)
    return _KEYMAP


def shortcut_groups() -> List[Tuple[str, List[Tuple[str, str]]]]:
    """The keyboard shortcut reference from the keymap, by group: ``[(title, [(label, keys), ...])]``,
    translated, with the keys in force (the first ones of each action)."""
    from .locale import tr

    km = get()
    groups: Dict[str, List[Tuple[str, str]]] = {}
    for info in actions().values():
        keys = km.keys_for(info.id)
        if keys:
            groups.setdefault(info.category, []).append((info.title, keys))
    for category, items in FIXED:
        groups.setdefault(category, []).extend((tr(label), keys) for label, keys in items)
    return [(tr(category), items) for category, items in groups.items()]
