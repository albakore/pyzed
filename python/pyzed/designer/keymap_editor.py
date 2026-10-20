"""The keymap editor, like Zed's: every action with its keys, context and source, searchable, with the keys in
conflict marked, to change keys by pressing them, take them away or put the defaults back, and a button that
opens ``keymap.json`` in the code panel."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .. import _core, ui
from ..theme import Theme
from . import keymap as _keymap
from .keymap import ActionInfo, Binding
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

SEARCH_ID = "designer-keymap-search"
#: A widget id nothing has, focused while recording so the search field does not take the keys.
RECORDER_ID = "designer-keymap-recorder"
FILTERS = ("all", "user", "conflicts")
ROW_HEIGHT = 40.0

#: A row of the editor: an action and one of its bindings (``None`` when it has no keys).
Row = Tuple[ActionInfo, Optional[Binding]]


class KeymapEditor:
    """The state of the keymap editor dialog."""

    def __init__(self, designer: "Designer") -> None:
        self.d = designer
        self.query = ""
        #: ``"all"``, ``"user"`` (changed by the user) or ``"conflicts"``.
        self.filter = "all"
        #: The action whose keys are being recorded and the binding they replace (``None`` adds one).
        self.recording: Optional[Tuple[str, Optional[Binding]]] = None
        self.strokes: List[str] = []
        #: The context the recorded keys will work in.
        self.context = "Workspace"
        self.error: Optional[str] = None

    @property
    def km(self) -> _keymap.Keymap:
        return _keymap.get()

    def open(self) -> Any:
        """Opens the keymap editor; returns the command that focuses its search field."""
        self.recording, self.strokes, self.error = None, [], None
        self.d.open_dialog_named("keymap")
        return _core.Command.focus(SEARCH_ID)

    def set_query(self, text: str) -> None:
        self.query = text

    def set_filter(self, name: str) -> None:
        self.filter = name

    # -- the list ---------------------------------------------------------------------------------------------
    def rows(self) -> List[Row]:
        """The actions and their bindings that match the search and the filter, in the keymap's order."""
        km = self.km
        km.refresh()
        conflicts = km.conflicts()
        needle = self.query.strip().lower()
        by_action: Dict[str, List[Binding]] = {}
        for b in km.active:
            by_action.setdefault(b.action or "", []).append(b)
        out: List[Row] = []
        for info in _keymap.actions().values():
            bindings: List[Optional[Binding]] = list(by_action.get(info.id, [])) or [None]
            for b in bindings:
                if self.filter == "user" and not km.is_changed(info.id):
                    continue
                if self.filter == "conflicts" and (b is None or (b.context, b.keys) not in conflicts):
                    continue
                text = f"{info.title} {info.label} {info.name} {b.keys if b else ''} {b.context if b else ''}"
                if needle and needle not in text.lower():
                    continue
                out.append((info, b))
        return out

    def conflict_note(self, binding: Binding) -> Optional[str]:
        """What else ``binding``'s keys run in its context, or ``None``."""
        others = [b for b in self.km.conflicts().get((binding.context, binding.keys), []) if b.action != binding.action]
        if not others:
            return None
        names = ", ".join(_keymap.actions()[b.action].title for b in others if b.action)
        last = self.km.conflicts()[(binding.context, binding.keys)][-1]
        if last.action == binding.action:
            return tr("Overrides {names}", names=names)
        return tr("Shadowed by {names}", names=names)

    # -- recording keys ---------------------------------------------------------------------------------------
    def start(self, action: str, binding: Optional[Binding] = None) -> Any:
        """Starts recording new keys for ``binding`` of ``action`` (or for a new binding); returns the command
        that takes the keyboard away from the search field."""
        self.recording = (action, binding)
        self.strokes = []
        self.context = binding.context if binding is not None else _keymap.actions()[action].context
        self.error = None
        return _core.Command.focus(RECORDER_ID)

    def record(self, combo: str) -> Any:
        """A key pressed while recording: Escape cancels, Enter saves what was pressed, any other key is added
        (two make a chord, a third starts again)."""
        if combo == "escape":
            return self.cancel()
        if combo == "enter" and self.strokes:
            return self.confirm()
        stroke = _keymap.normalize(combo)
        if stroke is None:
            return None  # a modifier on its own
        self.strokes = [stroke] if len(self.strokes) >= 2 else [*self.strokes, stroke]
        self.error = None
        return None

    @property
    def keys(self) -> str:
        """The keys recorded so far."""
        return " ".join(self.strokes)

    def clash(self) -> Optional[str]:
        """What the recorded keys already run in the chosen context, if something else."""
        if self.recording is None or not self.strokes:
            return None
        current = self.km.resolve(self.keys, (self.context,))
        if current is None or current == self.recording[0]:
            return None
        return tr("Already bound to {name} in {context}", name=_keymap.actions()[current].title,
                  context=self.context)

    def set_context(self, context: str) -> None:
        self.context = context

    def confirm(self) -> Any:
        """Saves the recorded keys; returns the command that gives the keyboard back to the search field."""
        if self.recording is None or not self.strokes:
            return None
        action, binding = self.recording
        error = self.km.change(binding, self.keys, self.context) if binding is not None \
            else self.km.add(action, self.keys, self.context)
        if error is not None:
            self.error = tr(error)
            return None
        self.recording = None
        self._saved()
        return _core.Command.focus(SEARCH_ID)

    def cancel(self) -> Any:
        self.recording, self.strokes, self.error = None, [], None
        return _core.Command.focus(SEARCH_ID)

    # -- other changes ----------------------------------------------------------------------------------------
    def remove(self, binding: Binding) -> None:
        """Takes ``binding``'s keys away."""
        self.km.remove(binding)
        self._saved()

    def reset(self, action: str) -> None:
        """Puts back the default keys of ``action``."""
        self.km.reset(action)
        self._saved()

    def reset_all(self) -> None:
        """Puts back every default key (``keymap.json`` is left with no bindings)."""
        self.km.reset_all()
        self._saved()

    def edit_file(self) -> Any:
        """Opens ``keymap.json`` in the code panel (created if missing); its changes apply when it is saved."""
        path = self.km.ensure_file()
        self.d.close_dialog()
        if self.d.buffers.open(path):
            return _core.Command.focus(self.d.editor_id)
        return None

    def _saved(self) -> None:
        if self.km.save() is None:
            self.d.notify(tr("Could not save the keymap"), "; ".join(self.km.errors), kind="error", seconds=5)
        self.d.keymap_changed()


def _row(ke: KeymapEditor, row: Row, t: Theme) -> Any:
    """One binding (or an action with no keys): name and id, keys, context, source and buttons."""
    info, binding = row
    km = ke.km
    changed = km.is_changed(info.id)
    recording = ke.recording == (info.id, binding)
    note = ke.conflict_note(binding) if binding is not None else None
    second = ui.label(note, size="sm", color="warning", wrap=False, theme=t) if note \
        else ui.label(info.name, size="sm", color="text_muted", mono=True, wrap=False, theme=t)
    name = _core.container(_core.column([
        ui.label(info.title, weight="medium" if changed else None, wrap=False, theme=t), second,
    ], spacing=1), width="fill", clip=True)
    if recording:
        shown = ke.keys or tr("Press keys…")
        keys: Any = _core.container(
            ui.kbd(ke.keys, theme=t) if ke.keys else ui.label(shown, size="sm", color="text_muted", theme=t),
            padding=(2, 8), height=26, width=200, align_y="center", border_color=t.accent, border_width=1.0, radius=4)
        context = ui.select(list(_keymap.CONTEXTS), ke.context, ke.set_context, size="sm", width=120, theme=t)
        buttons = _core.row([
            ui.icon_button("check", ke.confirm, size="sm", disabled=not ke.strokes, tooltip=tr("Save (Enter)"),
                           theme=t),
            ui.icon_button("x", ke.cancel, size="sm", tooltip=tr("Cancel (Escape)"), theme=t),
        ], spacing=2)
        source = _core.space(width=70)
    else:
        keys = _core.container(ui.kbd(binding.keys, theme=t) if binding is not None
                               else ui.label("—", size="sm", color="text_muted", theme=t), width=200)
        context = ui.label(binding.context if binding is not None else "", size="sm", color="text_muted",
                           width=120, theme=t)
        source = ui.badge(tr("User"), tint="accent", theme=t) if binding is not None and binding.user \
            else ui.label(tr("Default") if binding is not None else "", size="sm", color="text_muted", theme=t)
        source = _core.container(source, width=70)
        buttons = _core.row([
            ui.icon_button("pencil", lambda: ke.start(info.id, binding), size="sm",
                           tooltip=tr("Change keys") if binding is not None else tr("Add keys"), theme=t),
            ui.icon_button("plus", lambda: ke.start(info.id), size="sm", tooltip=tr("Add keys"), theme=t)
            if binding is not None else None,
            ui.icon_button("trash-2", lambda: ke.remove(binding), size="sm", tooltip=tr("Remove keys"), theme=t)
            if binding is not None else None,
            ui.icon_button("rotate-ccw", lambda: ke.reset(info.id), size="sm", tooltip=tr("Default keys"), theme=t)
            if changed else None,
        ], spacing=2)
    return _core.row([name, keys, context, source, _core.container(buttons, width=110, align_x="right")], spacing=10,
                     align="center", height=ROW_HEIGHT, padding=(0, 8))


def dialog(d: "Designer", t: Theme) -> Any:
    """The keymap editor dialog."""
    ke = d.keymap_editor
    km = ke.km
    rows = ke.rows()
    n_conflicts = len(km.conflicts())
    labels = {"all": tr("All"), "user": tr("Changed"), "conflicts": tr("Conflicts ({n})", n=n_conflicts)}
    top = _core.row([
        ui.search_input(ke.query, ke.set_query, placeholder=tr("Search actions, keys or contexts…"), id=SEARCH_ID,
                        width="fill", theme=t),
        ui.segmented(list(labels.values()), labels[ke.filter],
                     lambda label: ke.set_filter(next(k for k, v in labels.items() if v == label)), theme=t),
    ], spacing=10, align="center")
    notes: List[Any] = []
    if ke.recording is not None:
        hint = ke.error or ke.clash() or tr("Press the keys (two for a chord such as ctrl-k ctrl-s); Enter saves, "
                                            "Escape cancels")
        color = "error" if ke.error else "warning" if ke.clash() else "text_muted"
        notes.append(ui.label(hint, size="sm", color=color, theme=t))
    for error in km.errors[:3]:
        notes.append(ui.label(f"⚠ {error}", size="sm", color="error", theme=t))
    header = _core.row([
        ui.label(tr("Action"), size="xs", weight="semibold", color="text_muted", width="fill", theme=t),
        ui.label(tr("Keys"), size="xs", weight="semibold", color="text_muted", width=200, theme=t),
        ui.label(tr("Context"), size="xs", weight="semibold", color="text_muted", width=120, theme=t),
        ui.label(tr("Source"), size="xs", weight="semibold", color="text_muted", width=70, theme=t),
        _core.space(width=110),
    ], spacing=10, padding=(0, 8))
    body_rows = ui.virtual_list(rows, lambda row: _row(ke, row, t), item_height=ROW_HEIGHT, height=440, theme=t) \
        if rows else _core.container(ui.label(tr("No action matches."), size="sm", color="text_muted", theme=t),
                                     padding=12, height=440)
    body = _core.column([top, *notes, header, _core.rule(thickness=1, color=t.border_variant), body_rows], spacing=8,
                        width="fill")
    return ui.modal(body, title=tr("Keymap editor"), on_close=d.close_dialog, width=920, footer=[
        ui.button(tr("Edit keymap.json"), ke.edit_file, icon="file-json", variant="ghost", theme=t),
        ui.button(tr("Reset all"), ke.reset_all, icon="rotate-ccw", variant="ghost", disabled=not km.user, theme=t),
        _core.space(width="fill"),
        ui.button(tr("Done"), d.close_dialog, variant="solid", theme=t),
    ], theme=t)
