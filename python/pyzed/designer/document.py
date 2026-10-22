"""The document being edited: form + handler code + selection + undo, with every editing command.

The designer UI only translates clicks and keys into calls on ``Document``; all the
behavior lives here, so it can be tested (and scripted) without opening a window.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from . import code as _code
from . import components as _components
from . import geometry
from . import layout as _layout
from .history import History
from .model import RESERVED, SUFFIX, Control, Form, code_path, identifier, load, save

PASTE_OFFSET = 16
#: The ``format`` of copied controls on the system clipboard (``clipboard_text`` / ``paste_text``).
CLIPBOARD_FORMAT = "pyzed.controls/1"

#: What the last copy took, shared by every open document so controls paste into another form.
_clipboard: List[Dict[str, Any]] = []


class Document:
    """A form open in the designer.

    ``code`` is the text of the handlers module, kept in memory and written next to
    the form on ``save``. ``selection`` holds control names, primary first.
    """

    def __init__(self, form: Optional[Form] = None, path: Optional[Union[str, Path]] = None,
                 code: Optional[str] = None) -> None:
        self.form = form or Form()
        self.path: Optional[Path] = Path(path) if path else None
        self.code = code if code is not None else _code.new_module(self.form.name)
        self.selection: List[str] = []
        self.history = History(self.form)
        self.dirty = False
        self.revision = 0
        #: Whether resizing the form or a container moves and sizes what is inside it the way the anchors say.
        self.follow_anchors = True
        #: A stand-in for "nothing open" (the main window's last tab was closed): no tab, an empty area.
        self.blank = False

    @property
    def clipboard(self) -> List[Dict[str, Any]]:
        """The copied controls (as ``Control.to_dict()`` data), shared by every document."""
        return _clipboard

    @clipboard.setter
    def clipboard(self, controls: List[Dict[str, Any]]) -> None:
        _clipboard[:] = controls

    # -- files --------------------------------------------------------------
    @classmethod
    def open(cls, path: Union[str, Path]) -> "Document":
        """Loads the form at ``path`` and the text of its handlers module (if the file exists) into a new
        document."""
        path = Path(path)
        form = load(path)
        module = code_path(path, form)
        code = module.read_text(encoding="utf-8") if module.exists() else None
        return cls(form, path, code)

    @property
    def code_path(self) -> Optional[Path]:
        """Where the handlers module is saved, or ``None`` while the form has no file."""
        return code_path(self.path, self.form) if self.path else None

    @property
    def display_name(self) -> str:
        """The name shown for the document: its file name, or ``<form name>.pzform`` if unsaved."""
        return self.path.name if self.path else f"{self.form.name}{SUFFIX}"

    def save(self, path: Optional[Union[str, Path]] = None) -> Path:
        """Writes the form and its handlers module; returns the form path."""
        if path is not None:
            self.path = Path(path) if Path(path).suffix else Path(path).with_suffix(SUFFIX)
        if self.path is None:
            raise ValueError("this form has no file yet; pass a path")
        save(self.form, self.path)
        module = self.code_path
        assert module is not None
        if self.code.strip() or module.exists():
            module.write_text(self.code, encoding="utf-8")
        self.dirty = False
        return self.path

    # -- changes and undo ---------------------------------------------------
    def commit(self, group: Optional[str] = None) -> None:
        """Records an undo step after an edit (``group`` merges repeated edits of one field)."""
        if self.history.push(self.form, group):
            self.dirty = True

    def _restore(self, form: Optional[Form]) -> bool:
        if form is None:
            return False
        self.form = form
        self.selection = [n for n in self.selection if form.get(n) is not None]
        self.dirty = True
        self.revision += 1
        return True

    def undo(self) -> bool:
        """Goes back one undo step; returns ``False`` if there was nothing to undo."""
        return self._restore(self.history.undo())

    def redo(self) -> bool:
        """Redoes one undone step; returns ``False`` if there was nothing to redo."""
        return self._restore(self.history.redo())

    # -- selection ----------------------------------------------------------
    @property
    def selected(self) -> List[Control]:
        """The selected controls, primary first (names that no longer exist are skipped)."""
        return [c for c in (self.form.get(n) for n in self.selection) if c is not None]

    @property
    def primary(self) -> Optional[Control]:
        """The primary (first) selected control, or ``None`` when nothing is selected."""
        selected = self.selected
        return selected[0] if selected else None

    def select(self, names: Union[str, Iterable[str], None], *, add: bool = False) -> None:
        """Selects the controls ``names`` (one name, several, or ``None`` for none); unknown names are
        ignored.

        With ``add``, each name is toggled in the current selection instead of replacing it.
        """
        if names is None:
            names = []
        elif isinstance(names, str):
            names = [names]
        names = [n for n in names if self.form.get(n) is not None]
        if add:
            for n in names:
                if n in self.selection:
                    self.selection.remove(n)
                else:
                    self.selection.append(n)
        else:
            self.selection = list(dict.fromkeys(names))

    def select_all(self) -> None:
        """Selects every control of the form."""
        self.selection = self.form.names()

    def is_selected(self, name: str) -> bool:
        """Whether the control ``name`` is selected."""
        return name in self.selection

    # -- creating and deleting ---------------------------------------------
    def add(self, type_: str, x: float, y: float, width: Optional[float] = None,
            height: Optional[float] = None, *, snap: bool = True, parent: Optional[str] = None) -> Control:
        """Places a new ``type_`` control (snapped to the grid) and selects it.

        With ``parent`` (a container's name) it goes inside it, and ``x``/``y`` are
        relative to the container.
        """
        spec = _components.get(type_)
        grid = self.form.grid
        container = self.form.get(parent) if parent else None
        if container is not None and (_layout.kind(container) is None or not spec.visual):
            container = None  # non-visual components belong to the form itself
        if container is not None and _layout.kind(container) == "dock" and type_ != "dock_panel":
            container = None  # a dock holds Dock panels; controls go on a panel
        w, h = width or spec.size[0], height or spec.size[1]
        bounds = (container.width, container.height) if container is not None else self.size
        if container is not None and _layout.kind(container) != "free":
            w, h = min(w, bounds[0]), min(h, bounds[1])
        x = geometry.snap(x, grid, snap)
        y = geometry.snap(y, grid, snap)
        x = max(0.0, min(x, bounds[0] - min(w, bounds[0])))
        y = max(0.0, min(y, bounds[1] - min(h, bounds[1])))
        control = spec.create(self.form.unique_name(type_), x, y, w, h)
        control.parent = container.name if container is not None else None
        self.form.add(control)
        for child_type, values in spec.children:  # a new Dock comes with its first panels
            child_spec = _components.get(child_type)
            child = child_spec.create(self.form.unique_name(child_type), 0, 0, *child_spec.size)
            child.props.update(dict(values))
            child.parent = control.name
            self.form.add(child)
        self.selection = [control.name]
        self.commit()
        return control

    # -- hierarchy ----------------------------------------------------------
    def rects(self) -> Dict[str, Tuple[float, float, float, float]]:
        """The absolute rectangle of every control (see ``layout.resolve``)."""
        return _layout.resolve(self.form)

    def can_contain(self, container: Optional[str], name: str) -> bool:
        """Whether control ``name`` can be moved into ``container`` (``None`` is the form, which takes
        anything): it must be a container other than the control itself and not inside it."""
        if container is None:
            return True
        control = self.form.get(name)
        if control is not None and not _components.spec(control.type).visual:
            return False  # a timer, a watcher... belongs to the form, not to a container
        target = self.form.get(container)
        if target is not None and _layout.kind(target) == "dock" and (control is None or control.type != "dock_panel"):
            return False  # a dock holds Dock panels only
        return (target is not None and _layout.kind(target) is not None and container != name
                and not self.form.is_inside(container, name))

    def reparent(self, names: Sequence[str], parent: Optional[str], *, index: Optional[int] = None,
                 at: Optional[Tuple[float, float]] = None, commit: bool = True,
                 rects: Optional[Dict[str, Tuple[float, float, float, float]]] = None) -> List[str]:
        """Moves controls into ``parent`` (or onto the form with ``None``), keeping them where they are.

        ``index`` is the position among the new siblings (flex and grid containers lay
        them out in that order); ``at`` an absolute point for the first control's
        top-left corner instead of its current one; ``rects`` the absolute rectangles to
        start from (``self.rects()`` by default). Returns the names actually moved.
        """
        rects = rects if rects is not None else self.rects()
        moved = [n for n in names if self.form.get(n) is not None and self.can_contain(parent, n)]
        # skip controls whose container is moving with them: they follow it
        moved = [n for n in moved if not any(a.name in moved for a in self.form.ancestors(n))]
        if not moved:
            return []
        ox, oy = _layout.origin(self.form, rects, parent)
        shift = (0.0, 0.0)
        if at is not None and moved[0] in rects:
            shift = (at[0] - rects[moved[0]][0], at[1] - rects[moved[0]][1])
        controls = [self.form[n] for n in moved]
        for control in controls:
            ax, ay = rects[control.name][0] + shift[0], rects[control.name][1] + shift[1]
            control.x, control.y = round(ax - ox), round(ay - oy)
            control.parent = parent
        if index is not None:
            rest = [c for c in self.form.controls if c not in controls]
            siblings = [c for c in rest if c.parent == parent]
            if index < len(siblings):
                at_pos = rest.index(siblings[index])
            else:
                at_pos = rest.index(siblings[-1]) + 1 if siblings else len(rest)
            self.form.controls = rest[:at_pos] + controls + rest[at_pos:]
        if commit:
            self.commit()
        return moved

    def wrap(self, type_: str, names: Optional[Sequence[str]] = None) -> Optional[Control]:
        """Puts controls (the selection by default) inside a new container of ``type_`` around them."""
        form = self.form
        picked = [form[n] for n in (names if names is not None else self.selection) if form.get(n) is not None]
        picked = [c for c in picked if not any(a in picked for a in form.ancestors(c.name))
                  and _components.spec(c.type).visual]
        if not picked:
            return None
        parent = picked[0].parent
        picked = [c for c in picked if c.parent == parent]
        rects = self.rects()
        ox, oy = _layout.origin(form, rects, parent)
        boxes = [rects[c.name] for c in picked]
        x1, y1 = min(b[0] for b in boxes), min(b[1] for b in boxes)
        x2, y2 = max(b[0] + b[2] for b in boxes), max(b[1] + b[3] for b in boxes)
        spec = _components.get(type_)
        container = spec.create(form.unique_name(type_), x1 - ox, y1 - oy, max(x2 - x1, 8), max(y2 - y1, 8))
        container.parent = parent
        # the new container takes the place of the first wrapped control in the z-order
        index = form.controls.index(picked[0])
        form.controls.insert(index, container)
        if spec.container in ("flex", "grid"):
            column = container.props.get("direction") == "column"
            picked.sort(key=lambda c: (rects[c.name][1], rects[c.name][0]) if column or spec.container == "grid"
                        else (rects[c.name][0], rects[c.name][1]))
        self.reparent([c.name for c in picked], container.name, index=0 if spec.container != "free" else None,
                      rects=rects, commit=False)
        self.selection = [container.name]
        self.commit()
        return container

    def move_out(self, name: str) -> None:
        """Moves a control out of its container, into the container's own parent."""
        control = self.form.get(name)
        if control is None or not control.parent:
            return
        parent = self.form[control.parent]
        self.reparent([name], parent.parent)

    def set_layout(self, name: str, key: str, value: Any) -> None:
        """Sets an option the parent's layout reads (``grow``, ``span``)."""
        control = self.form[name]
        if value in (None, "", 0) and key in control.layout:
            del control.layout[key]
        elif value not in (None, ""):
            control.layout[key] = value
        self.commit(group=f"layout:{name}:{key}")

    def delete(self) -> List[str]:
        """Removes the selected controls (and what is inside them); returns the removed names."""
        removed = [c.name for c in self.form.remove(self.selection)]
        self.selection = []
        if removed:
            from . import timeline

            timeline.drop_targets(self.form, removed)
            self.commit()
        return removed

    def copy(self) -> int:
        """Copies the selection, with whatever is inside the selected containers."""
        picked = [c for c in self.selected
                  if not any(self.is_selected(a.name) for a in self.form.ancestors(c.name))]
        out: List[Dict[str, Any]] = []
        for control in picked:
            out.append(control.to_dict())
            out.extend(c.to_dict() for c in self.form.descendants(control.name))
        self.clipboard = out
        return len(picked)

    def clipboard_text(self) -> str:
        """The copied controls as JSON for the system clipboard, so another form, another Pyzed Design
        window or a text file can take them (see ``paste_text``)."""
        return json.dumps({"format": CLIPBOARD_FORMAT, "controls": self.clipboard}, indent=1)

    @staticmethod
    def parse_clipboard(text: str) -> Optional[List[Dict[str, Any]]]:
        """The controls in clipboard ``text`` written by ``clipboard_text``, or ``None`` when it holds
        something else. Controls of a type this Pyzed does not know are left out."""
        try:
            data = json.loads(text)
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict) or data.get("format") != CLIPBOARD_FORMAT:
            return None
        known = {spec.type for spec in _components.all_components()}
        controls = [c for c in data.get("controls") or [] if isinstance(c, dict) and c.get("type") in known
                    and isinstance(c.get("name"), str)]
        names = {c["name"] for c in controls}
        for c in controls:  # a child whose container was left out lands on the form
            if c.get("parent") and c["parent"] not in names:
                c["parent"] = None
        return controls

    def paste_text(self, text: str, offset: float = PASTE_OFFSET) -> Optional[List[str]]:
        """Pastes the controls in system clipboard ``text`` (see ``clipboard_text``); returns the new
        names, or ``None`` when the text holds no Pyzed controls."""
        controls = self.parse_clipboard(text)
        if controls is None:
            return None
        if controls != self.clipboard:
            self.clipboard = controls
        return self.paste(offset)

    def cut(self) -> int:
        """Copies the selection to the clipboard and deletes it; returns how many controls were copied."""
        count = self.copy()
        self.delete()
        return count

    def paste(self, offset: float = PASTE_OFFSET) -> List[str]:
        """Adds copies of the clipboard (shifted by ``offset``) without their events; they keep their names when
        those are free in this form."""
        names: List[str] = []
        renamed: Dict[str, str] = {}
        copied = {d.get("name") for d in self.clipboard}
        for data in self.clipboard:
            control = Control.from_dict(data)
            old = control.name
            # into another form a control keeps its name when it is free there
            if self.form.get(old) is not None or old in RESERVED or old == self.form.name or identifier(old) != old:
                control.name = self.form.unique_name(control.type)
            renamed[old] = control.name
            control.events = {}
            if control.parent in copied:  # inside a pasted container: keep its place there
                control.parent = renamed.get(control.parent)
                self.form.add(control)
                continue
            if control.parent and self.form.get(control.parent) is None:
                control.parent = None
            limit = self.size
            if control.parent:
                parent = self.form[control.parent]
                limit = (parent.width, parent.height)
            control.x = min(control.x + offset, max(limit[0] - control.width, 0))
            control.y = min(control.y + offset, max(limit[1] - control.height, 0))
            self.form.add(control)
            names.append(control.name)
        if names:
            self.selection = names
            self.copy()
            self.commit()
        return names

    def duplicate(self) -> List[str]:
        """Pastes a copy of the selection right away, leaving the clipboard as it was; returns the new
        names."""
        saved = self.clipboard
        self.copy()
        names = self.paste()
        self.clipboard = saved
        return names

    # -- geometry -----------------------------------------------------------
    @property
    def size(self) -> Tuple[float, float]:
        """The form's ``(width, height)`` in pixels."""
        return (self.form.width, self.form.height)

    def nudge(self, dx: float, dy: float) -> None:
        """Moves the selected controls (those not placed by a layout) by ``dx``, ``dy`` pixels, kept inside
        their container when they share one; repeated nudges merge into one undo step."""
        selected = [c for c in self.selected if not _layout.managed(self.form, c)]
        parents = {c.parent for c in selected}
        limit = self.size
        if len(parents) == 1 and None not in parents:
            parent = self.form[next(iter(parents))]
            limit = (parent.width, parent.height)
        geometry.move(selected, dx, dy, limit=limit if len(parents) == 1 else None)
        self.commit(group="nudge")

    def align(self, edge: str, *, to_form: bool = False) -> None:
        """Aligns the selected controls on ``edge`` (see ``geometry.align``): to each other, or to the form
        with ``to_form`` or when only one control is selected."""
        selected = self.selected
        to = (0.0, 0.0, self.form.width, self.form.height) if to_form or len(selected) == 1 else None
        geometry.align(selected, edge, to=to)
        self.commit()

    def center(self, axis: str = "both") -> None:
        """Centers the selection (as a group) in the form."""
        box = geometry.bounds(self.selected)
        if box is None:
            return
        dx = round((self.form.width - box[2]) / 2 - box[0]) if axis in ("both", "horizontal") else 0
        dy = round((self.form.height - box[3]) / 2 - box[1]) if axis in ("both", "vertical") else 0
        geometry.move(self.selected, dx, dy)
        self.commit()

    def distribute(self, axis: str) -> None:
        """Spaces the selected controls evenly along ``axis`` (see ``geometry.distribute``)."""
        geometry.distribute(self.selected, axis)
        self.commit()

    def same_size(self, which: str = "both") -> None:
        """Gives the selected controls the primary one's width, height or both (``which``)."""
        geometry.same_size(self.selected, which)
        self.commit()

    def snap_to_grid(self) -> None:
        """Snaps the selected controls (or all of them if nothing is selected) to the form's grid."""
        geometry.snap_controls(self.selected or self.form.controls, self.form.grid)
        self.commit()

    def reorder(self, where: str) -> None:
        """Moves the selected controls in the z-order (``where``: see ``Form.reorder``)."""
        self.form.reorder(self.selection, where)
        self.commit()

    def set_rect(self, name: str, rect: Sequence[float], *, group: Optional[str] = None) -> None:
        """Sets the position and size of control ``name`` from ``rect`` ``(x, y, width, height)``, rounded to
        whole pixels; edits with the same ``group`` merge into one undo step."""
        control = self.form[name]
        control.x, control.y, control.width, control.height = (round(v) for v in rect)
        self.commit(group)

    # -- properties ---------------------------------------------------------
    def set_prop(self, name: str, key: str, value: Any) -> None:
        """Sets property ``key`` of control ``name`` to ``value`` (repeated edits merge into one undo
        step)."""
        self.form[name].props[key] = value
        self.commit(group=f"prop:{name}:{key}")

    def set_style(self, name: Optional[str], key: str, value: Any) -> None:
        """Sets one style property of a control, or of the form's global style when ``name`` is
        ``None``; ``None`` removes it."""
        style = self.form.style if name is None else self.form[name].style
        if value is None:
            if key not in style:
                return
            del style[key]
        else:
            style[key] = value
        self.commit(group=f"style:{name}:{key}")

    def set_animations(self, name: str, animations: List[Dict[str, Any]], *, group: Optional[str] = None) -> None:
        """Replaces the animations of control ``name`` (see ``designer.motion``). Edits with the same
        ``group`` in a row undo together (typing a duration)."""
        control = self.form[name]
        if control.animations == animations:
            return
        control.animations = [dict(a) for a in animations]
        self.commit(group=group)

    # -- timeline animations (see ``designer.timeline``) ------------------------
    def set_clip(self, clip: Any, *, old: Optional[str] = None, group: Optional[str] = None) -> None:
        """Stores the ``pz.Clip`` ``clip`` in the form (in place of the clip ``old`` when it is renamed)."""
        from . import timeline

        before = [dict(a) for a in self.form.animations]
        timeline.put(self.form, clip, old)
        if self.form.animations != before:
            self.commit(group=group)

    def remove_clip(self, name: str) -> None:
        """Removes the clip ``name`` (and stops it playing when the form opens)."""
        from . import timeline

        if any(a.get("name") == name for a in self.form.animations):
            timeline.remove(self.form, name)
            self.commit()

    def set_autoplay(self, name: str) -> None:
        """Plays the clip ``name`` when the form opens (``""``: none)."""
        if self.form.autoplay != name:
            self.form.autoplay = name
            self.commit()

    def clear_style(self, name: Optional[str]) -> None:
        """Removes every style property of a control (or of the form's global style)."""
        target = self.form if name is None else self.form[name]
        if target.style:
            target.style = {}
            self.commit()

    def set_field(self, name: str, key: str, value: Any) -> None:
        """Sets a ``Control`` attribute (x, y, width, height, visible, enabled, locked, anchor); a container's
        new width or height moves what is inside it as its anchors say."""
        control = self.form[name]
        size = (control.width, control.height)
        if key in ("width", "height"):
            value = max(float(value), geometry.MIN_SIZE)
        setattr(control, key, value)
        self.reflow(name, size)
        self.commit(group=f"field:{name}:{key}")

    def set_bind(self, name: str, bind: Optional[str]) -> None:
        """Binds control ``name`` to the field (or, for display controls, the expression) ``bind`` of
        ``form.data``; ``None`` or ``""`` unbinds it."""
        self.form[name].bind = (bind or "").strip()
        self.commit(group=f"bind:{name}")

    def set_rule(self, name: str, rule: str, value: Any) -> None:
        """Sets validation ``rule`` (``required``, ``min_length``, ``pattern``...) of control ``name``;
        ``None``, ``""`` or ``False`` removes it."""
        rules = self.form[name].rules
        if value in (None, "", False):
            rules.pop(rule, None)
        else:
            rules[rule] = value
        self.commit(group=f"rule:{name}:{rule}")

    def toggle_anchor(self, name: str, edge: str) -> None:
        """Adds ``edge`` to the anchors of control ``name``, or removes it if it was there."""
        control = self.form[name]
        anchor = set(control.anchor)
        anchor ^= {edge}
        control.anchor = tuple(a for a in ("left", "top", "right", "bottom") if a in anchor)
        self.commit()

    def parent_size(self, name: str) -> Tuple[float, float]:
        """The design size of what control ``name`` is anchored to: its container, or the form."""
        control = self.form[name]
        parent = self.form.get(control.parent) if control.parent else None
        return (parent.width, parent.height) if parent is not None else (self.form.width, self.form.height)

    def set_anchor(self, name: str, anchor: Any, *, move: bool = False, margin: float = 0.0) -> None:
        """Anchors control ``name`` with a preset (``"top_right"``, ``"full"``...) or edges. With ``move`` it is
        also moved (and, on stretched axes, sized) to where the anchor points, ``margin`` pixels in."""
        from .. import anchors

        control = self.form[name]
        size = (control.width, control.height)
        control.anchor = anchors.edges(anchor)
        if move:
            x, y, w, h = anchors.snap_to(control.anchor, control.rect, self.parent_size(name), margin)
            control.x, control.y, control.width, control.height = round(x), round(y), round(w), round(h)
            self.reflow(name, size)
        self.commit()

    def set_offset(self, name: str, side: str, value: float) -> None:
        """Sets the distance from the ``side`` (``left``, ``top``, ``right``, ``bottom``) of the container to
        control ``name``; the opposite side stays where it is, so the control grows or shrinks."""
        control = self.form[name]
        size = (control.width, control.height)
        pw, ph = self.parent_size(name)
        value = float(value)
        if side == "left":
            right = control.x + control.width
            control.x, control.width = value, max(right - value, geometry.MIN_SIZE)
        elif side == "right":
            control.width = max(pw - value - control.x, geometry.MIN_SIZE)
        elif side == "top":
            bottom = control.y + control.height
            control.y, control.height = value, max(bottom - value, geometry.MIN_SIZE)
        elif side == "bottom":
            control.height = max(ph - value - control.y, geometry.MIN_SIZE)
        else:
            raise ValueError(f"unknown side {side!r}")
        self.reflow(name, size)
        self.commit(group=f"offset:{name}:{side}")

    def set_pivot(self, name: str, x: float, y: float) -> None:
        """Sets the pivot of control ``name`` (``0`` to ``1`` on each axis; the center is the default)."""
        control = self.form[name]
        pivot = [min(max(round(float(x), 3), 0.0), 1.0), min(max(round(float(y), 3), 0.0), 1.0)]
        if pivot == [0.5, 0.5]:
            control.layout.pop("pivot", None)
        else:
            control.layout["pivot"] = pivot
        self.commit(group=f"pivot:{name}")

    def set_form(self, key: str, value: Any) -> None:
        """Sets attribute ``key`` of the form (a new ``name`` is made a valid identifier first)."""
        if key == "name":
            value = identifier(value) or self.form.name
        size = (self.form.width, self.form.height)
        setattr(self.form, key, value)
        self.reflow(None, size)
        self.commit(group=f"form:{key}")

    def reflow(self, parent: Optional[str], size: Tuple[float, float]) -> None:
        """After the form (``parent`` ``None``) or container ``parent`` was resized from ``size``, moves and
        sizes what is inside it the way the anchors say (unless ``follow_anchors`` is off)."""
        new = (self.form.width, self.form.height) if parent is None else \
            (self.form[parent].width, self.form[parent].height)
        if not self.follow_anchors or tuple(new) == tuple(size):
            return
        inside = self.form.descendants(parent) if parent else self.form.controls
        _layout.reflow(self.form, parent, {c.name: c.rect for c in inside}, size, new)

    def rename(self, old: str, new: str) -> str:
        """Renames a control, its selection entry and the handlers that follow the naming convention."""
        control = self.form.get(old)
        if control is None:
            return old
        new = self.form.rename(old, new)
        if new == old:
            return old
        from . import timeline

        timeline.rename_target(self.form, old, new)
        self.selection = [new if n == old else n for n in self.selection]
        for event, handler in list(control.events.items()):
            if handler == _code.handler_name(old, event):
                renamed = _code.handler_name(new, event)
                self.code = _code.rename_function(self.code, handler, renamed)
                control.events[event] = renamed
        self.commit()
        return new

    # -- events and code ----------------------------------------------------
    def owner(self, name: Optional[str]) -> Tuple[str, Dict[str, str]]:
        """The display name and event map of a control, or of the form when ``name`` is ``None``."""
        if name is None:
            return self.form.name, self.form.events
        control = self.form[name]
        return control.name, control.events

    def events_of(self, name: Optional[str]) -> Tuple[str, ...]:
        """Returns the events of control ``name``, or the form's events when ``name`` is ``None``."""
        if name is None:
            return _components.FORM_EVENTS
        return _components.spec(self.form[name].type).all_events

    def wire(self, name: Optional[str], event: str) -> str:
        """Connects ``event`` to a handler (creating its stub if needed) and returns the function name."""
        owner, events = self.owner(name)
        handler = events.get(event)
        if not handler:
            handler = _code.handler_name("form" if name is None else owner, event)
            events[event] = handler
            self.commit()
        type_ = self.form[name].type if name is not None else None
        doc = _components.event_text(type_, event, "Event handler.").format(name=owner)
        self.code, created = _code.ensure_function(self.code, handler, doc)
        if created:
            self.dirty = True
        return handler

    def unwire(self, name: Optional[str], event: str, *, delete_code: bool = False) -> None:
        """Disconnects ``event``; with ``delete_code`` an untouched stub is removed too."""
        _, events = self.owner(name)
        handler = events.pop(event, None)
        if handler and delete_code:
            source = _code.get_function(self.code, handler)
            still_used = any(handler in c.events.values() for c in self.form.controls) or \
                handler in self.form.events.values()
            if source and not still_used and _code.body_is_empty(source):
                self.code = _code.replace_function(self.code, handler, "", strict=False).rstrip() + "\n"
                self.code = self.code.replace("\n\n\n\n", "\n\n\n")
        self.commit()

    def handler_source(self, handler: str) -> str:
        """Returns the source of ``handler`` in the code, or a new stub if it is not there yet."""
        return _code.get_function(self.code, handler) or _code.stub(handler)

    def set_handler_source(self, handler: str, source: str) -> None:
        """Replaces one handler's code (raises ``SyntaxError`` and changes nothing if it is invalid)."""
        self.code = _code.replace_function(self.code, handler, source)
        self.dirty = True

    def set_code(self, source: str) -> None:
        """Replaces the whole text of the handlers module and marks the document as changed."""
        self.code = source
        self.dirty = True
