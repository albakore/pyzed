"""The form document: a window and the controls placed on it, saved as JSON.

A form lives in two files next to each other:

* ``login.pzform``: the layout (this module), plain JSON so it diffs well in git.
* ``login.py``: the event handlers, ordinary Python (see ``designer.code``).

The model is pure data with no UI dependencies, so it is easy to test and to
generate or edit from scripts.
"""

from __future__ import annotations

import copy
import json
import keyword
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

FORMAT = "pyzed.form/1"
SUFFIX = ".pzform"



def check_format(fmt: Any, current: str, what: str) -> None:
    """Raises ``ValueError`` unless ``fmt`` is ``current``'s kind (``pyzed.form/``) at a version this
    Pyzed can read: a file saved by a newer Pyzed would otherwise lose what it does not know."""
    kind, _, supported = current.rpartition("/")
    fmt = str(fmt)
    if not fmt.startswith(kind + "/"):
        raise ValueError(f"not a Pyzed {what} (format {fmt!r})")
    version = fmt[len(kind) + 1:]
    if not version.isdigit() or int(version) > int(supported):
        raise ValueError(f"this {what} was saved by a newer Pyzed (format {fmt!r}); update Pyzed to open it")


#: Names a control cannot take because handlers use them on the form (``form.title``...).
RESERVED = frozenset({"name", "title", "size", "window", "close", "data", "errors", "valid", "validate", "animations"}
                     | set(keyword.kwlist))

def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


#: Edges a control can be anchored to. Anchoring to opposite edges stretches it.
ANCHORS = ("left", "top", "right", "bottom")


@dataclass
class Control:
    """One component placed on a form.

    ``x``, ``y``, ``width`` and ``height`` are in logical pixels relative to the form's
    client area, or to the top-left corner of ``parent`` when the control sits inside a
    container (a panel, a group box, a flex row...). ``props`` holds the component's own
    properties (``text``, ``checked``...) and ``events`` maps event names (``"click"``) to
    handler function names. ``layout`` holds options read by the parent's layout, such as
    ``grow`` in a flex row or ``span`` in a grid. ``style`` holds CSS-like style properties
    (``pz.Style.to_dict()``: background, border, radius, font...) drawn on top of the props.
    ``animations`` lists the control's animations (see ``designer.motion``). ``bind`` names the
    field of ``form.data`` the control shows (and edits, for inputs), and ``rules`` what its
    value must be (see ``designer.binding``). ``hidden_in_editor`` hides it on the designer's canvas only
    (the outline's eye with the "editor" setting); the running form ignores it.
    """

    name: str
    type: str
    x: float = 0.0
    y: float = 0.0
    width: float = 100.0
    height: float = 28.0
    props: Dict[str, Any] = field(default_factory=dict)
    events: Dict[str, str] = field(default_factory=dict)
    anchor: Tuple[str, ...] = ("left", "top")
    visible: bool = True
    enabled: bool = True
    locked: bool = False
    parent: Optional[str] = None
    layout: Dict[str, Any] = field(default_factory=dict)
    style: Dict[str, Any] = field(default_factory=dict)
    animations: List[Dict[str, Any]] = field(default_factory=list)
    bind: str = ""
    rules: Dict[str, Any] = field(default_factory=dict)
    hidden_in_editor: bool = False

    @property
    def min_size(self) -> Tuple[float, float]:
        """``(min_width, min_height)`` from ``layout`` (``0`` means no limit)."""
        return (_number(self.layout.get("min_width")), _number(self.layout.get("min_height")))

    @property
    def max_size(self) -> Tuple[float, float]:
        """``(max_width, max_height)`` from ``layout`` (``0`` means no limit)."""
        return (_number(self.layout.get("max_width")), _number(self.layout.get("max_height")))

    @property
    def pivot(self) -> Tuple[float, float]:
        """The point rotation and scale turn around, and that stays put when a size limit stops the control from
        stretching: ``(0, 0)`` is the top-left corner, ``(0.5, 0.5)`` (the default) the center."""
        value = self.layout.get("pivot")
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return (min(max(_number(value[0], 0.5), 0.0), 1.0), min(max(_number(value[1], 0.5), 0.0), 1.0))
        return (0.5, 0.5)

    @property
    def rect(self) -> Tuple[float, float, float, float]:
        """The control's ``(x, y, width, height)``, relative to its parent (or the form)."""
        return (self.x, self.y, self.width, self.height)

    def to_dict(self) -> Dict[str, Any]:
        """Returns the control as JSON-ready data; empty ``parent``, ``layout`` and ``style`` are left out."""
        data = asdict(self)
        data["anchor"] = list(self.anchor)
        # Only containers' children carry these, so plain forms stay as they were.
        if not data["parent"]:
            del data["parent"]
        if not data["layout"]:
            del data["layout"]
        if not data["style"]:
            del data["style"]
        for key in ("animations", "bind", "rules", "hidden_in_editor"):
            if not data[key]:
                del data[key]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Control":
        """Builds a control from saved ``data``, ignoring unknown keys and invalid anchors."""
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        known["anchor"] = tuple(a for a in known.get("anchor", ("left", "top")) if a in ANCHORS)
        known["props"] = dict(known.get("props") or {})
        known["events"] = dict(known.get("events") or {})
        known["layout"] = dict(known.get("layout") or {})
        known["style"] = dict(known.get("style") or {})
        known["animations"] = [dict(a) for a in known.get("animations") or [] if isinstance(a, dict)]
        known["parent"] = known.get("parent") or None
        known["bind"] = str(known.get("bind") or "")
        known["hidden_in_editor"] = bool(known.get("hidden_in_editor"))
        known["rules"] = {k: v for k, v in (known.get("rules") or {}).items() if v not in (None, "", False)} \
            if isinstance(known.get("rules"), dict) else {}
        return cls(**known)

    def copy(self) -> "Control":
        """Returns a deep copy of the control."""
        return copy.deepcopy(self)


@dataclass
class Form:
    """A window designed visually: its settings, its controls (in z-order) and its events.

    ``theme`` is any registered theme name; ``accent``, ``radius`` and ``font_size``
    tweak it without writing a theme file. ``style`` is the form's global style
    (``pz.Style.to_dict()``), applied to the whole window. ``grid`` is the designer's snapping step.
    """

    name: str = "Form1"
    title: str = "Form1"
    width: float = 640.0
    height: float = 420.0
    theme: str = "Pyzed Dark"
    accent: Optional[str] = None
    background: Optional[str] = None
    radius: Optional[float] = None
    font_size: float = 14.0
    resizable: bool = True
    grid: int = 8
    style: Dict[str, Any] = field(default_factory=dict)
    controls: List[Control] = field(default_factory=list)
    events: Dict[str, str] = field(default_factory=dict)
    code: Optional[str] = None
    #: Timeline animations (``pz.Clip.to_dict()`` data, see ``designer.timeline``).
    animations: List[Dict[str, Any]] = field(default_factory=list)
    #: The clip that plays when the form opens (``""``: none).
    autoplay: str = ""
    #: The order Tab moves the keyboard focus in, by control name (``[]``: the order controls are drawn in).
    tab_order: List[str] = field(default_factory=list)

    # -- lookup -------------------------------------------------------------
    def get(self, name: str) -> Optional[Control]:
        """Returns the control called ``name``, or ``None`` if there is none."""
        for control in self.controls:
            if control.name == name:
                return control
        return None

    def __getitem__(self, name: str) -> Control:
        control = self.get(name)
        if control is None:
            raise KeyError(name)
        return control

    def names(self) -> List[str]:
        """Returns the names of all controls, in z-order."""
        return [c.name for c in self.controls]

    # -- hierarchy ----------------------------------------------------------
    def children(self, name: Optional[str]) -> List[Control]:
        """The controls directly inside ``name`` (the form itself when ``None``), in z-order."""
        return [c for c in self.controls if c.parent == name]

    def descendants(self, name: str) -> List[Control]:
        """Every control inside ``name``, at any depth (parents before their children)."""
        out: List[Control] = []
        for child in self.children(name):
            out.append(child)
            out.extend(self.descendants(child.name))
        return out

    def ancestors(self, name: str) -> List[Control]:
        """The containers holding ``name``, nearest first."""
        out: List[Control] = []
        control = self.get(name)
        while control is not None and control.parent:
            control = self.get(control.parent)
            if control is None or control in out:
                break
            out.append(control)
        return out

    def walk(self, parent: Optional[str] = None, depth: int = 0) -> Iterable[Tuple[Control, int]]:
        """``(control, depth)`` in drawing order: each control, then what it contains."""
        for child in self.children(parent):
            yield child, depth
            yield from self.walk(child.name, depth + 1)

    def is_inside(self, name: str, container: str) -> bool:
        """Whether control ``name`` is inside ``container``, at any depth."""
        return any(a.name == container for a in self.ancestors(name))

    def _repair_parents(self) -> None:
        """Drops parents that do not exist or that would make a cycle."""
        for control in self.controls:
            if control.parent and (self.get(control.parent) is None or control.parent == control.name):
                control.parent = None
        for control in self.controls:
            seen = {control.name}
            node = control
            while node is not None and node.parent:
                if node.parent in seen:
                    control.parent = None
                    break
                seen.add(node.parent)
                node = self.get(node.parent)

    def unique_name(self, base: str) -> str:
        """The first free ``base1``, ``base2``... (Visual Basic style)."""
        base = re.sub(r"\d+$", "", identifier(base)) or "control"
        taken = set(self.names()) | {self.name} | RESERVED
        n = 1
        while f"{base}{n}" in taken:
            n += 1
        return f"{base}{n}"

    # -- editing ------------------------------------------------------------
    def add(self, control: Control) -> Control:
        """Appends ``control`` (on top of the z-order) and returns it.

        An empty, reserved or taken name is replaced with a unique one, and a parent that does not exist is
        dropped.
        """
        if not control.name or control.name in RESERVED or self.get(control.name) is not None:
            control.name = self.unique_name(control.name or control.type)
        if control.parent and self.get(control.parent) is None:
            control.parent = None
        self.controls.append(control)
        return control

    def remove(self, names: Iterable[str]) -> List[Control]:
        """Removes controls and everything inside them."""
        names = set(names)
        for name in list(names):
            names.update(c.name for c in self.descendants(name))
        removed = [c for c in self.controls if c.name in names]
        self.controls = [c for c in self.controls if c.name not in names]
        self.tab_order = [n for n in self.tab_order if n not in names]
        return removed

    def rename(self, old: str, new: str) -> str:
        """Renames a control and returns the name actually used (made unique and valid)."""
        control = self[old]
        new = identifier(new)
        if new == old:
            return old
        if not new or new in RESERVED or self.get(new) is not None or new == self.name:
            new = self.unique_name(new or control.type)
        control.name = new
        for child in self.controls:
            if child.parent == old:
                child.parent = new
        self.tab_order = [new if n == old else n for n in self.tab_order]
        return new

    def reorder(self, names: Iterable[str], where: str) -> None:
        """Moves controls in the z-order: to the ``"front"`` or ``"back"``, or one step ``"forward"`` or
        ``"backward"`` past the next sibling (a control in the same container) they overlap or, when none
        does, the next sibling. Only the order among siblings matters: each container draws its own."""
        names = set(names)
        if where in ("front", "back"):
            picked = [c for c in self.controls if c.name in names]
            rest = [c for c in self.controls if c.name not in names]
            self.controls = rest + picked if where == "front" else picked + rest
            return
        if where not in ("forward", "backward"):
            raise ValueError(f"unknown z-order move {where!r}")
        forward = where == "forward"
        order = list(self.controls)
        moving = [c for c in order if c.name in names]
        for control in reversed(moving) if forward else moving:  # the nearest to the edge moves first
            siblings = [c for c in order if c.parent == control.parent]
            at = siblings.index(control)
            ahead = siblings[at + 1:] if forward else siblings[:at][::-1]
            ahead = [c for c in ahead if c.name not in names] if ahead else []
            if not ahead:
                continue
            past = next((c for c in ahead if _overlap(c.rect, control.rect)), ahead[0])
            order.remove(control)
            index = order.index(past)
            order.insert(index + 1 if forward else index, control)
        self.controls = order

    # -- tab order ----------------------------------------------------------
    def tab_sequence(self, eligible: Optional[Iterable[str]] = None) -> List[str]:
        """The controls Tab goes through, in order: those of ``tab_order`` first, then the other ``eligible``
        ones (every control by default) in the order they are drawn."""
        drawn = [c.name for c, _ in self.walk()]
        allowed = set(drawn if eligible is None else eligible)
        listed = [n for n in self.tab_order if n in allowed and self.get(n) is not None]
        return listed + [n for n in drawn if n in allowed and n not in listed]

    def set_tab_order(self, names: Iterable[str]) -> None:
        """Saves ``names`` as the tab order (unknown names and repeats are dropped; empty: drawing order)."""
        out: List[str] = []
        for name in names:
            if self.get(name) is not None and name not in out:
                out.append(name)
        self.tab_order = out

    # -- serialization ------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Returns the form as JSON-ready data: ``{"format", "form": settings, "controls": [...]}``."""
        data = {k: v for k, v in asdict(self).items() if k not in ("controls",)}
        for key in ("style", "animations", "autoplay", "tab_order"):
            if not data[key]:
                del data[key]
        return {
            "format": FORMAT,
            "form": data,
            "controls": [c.to_dict() for c in self.controls],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Form":
        """Builds a form from saved ``data`` (see ``to_dict``), ignoring unknown settings and repairing broken
        parents; raises ``ValueError`` if it is not a Pyzed form."""
        check_format(data.get("format", FORMAT), FORMAT, "form")
        settings = {k: v for k, v in (data.get("form") or {}).items() if k in cls.__dataclass_fields__}
        settings.pop("controls", None)
        form = cls(**settings)
        form.events = dict(form.events or {})
        form.style = dict(form.style or {})
        form.animations = [dict(a) for a in form.animations or ()]
        form.controls = [Control.from_dict(c) for c in data.get("controls", [])]
        form._repair_parents()
        form.set_tab_order(n for n in form.tab_order or () if isinstance(n, str))
        return form

    def to_json(self) -> str:
        """Returns the form as indented JSON text (the contents of a ``.pzform`` file)."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "Form":
        """Builds a form from the JSON ``text`` of a ``.pzform`` file."""
        return cls.from_dict(json.loads(text))

    def copy(self) -> "Form":
        """Returns a deep copy of the form and its controls."""
        return copy.deepcopy(self)


def _overlap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def identifier(text: str) -> str:
    """Turns any text into a valid, lowercase-first Python identifier (``"OK button"`` -> ``"ok_button"``)."""
    text = re.sub(r"\W+", "_", str(text).strip()).strip("_")
    if text and text[0].isdigit():
        text = "_" + text
    return text[:1].lower() + text[1:]


def code_path(form_path: Union[str, Path], form: Optional[Form] = None) -> Path:
    """The handlers module of a form: ``form.code`` if set, else the same name with ``.py``."""
    form_path = Path(form_path)
    if form is not None and form.code:
        return (form_path.parent / form.code).resolve()
    return form_path.with_suffix(".py")


def load(path: Union[str, Path]) -> Form:
    """Reads a ``.pzform`` file."""
    return Form.from_json(Path(path).read_text(encoding="utf-8"))


def save(form: Form, path: Union[str, Path]) -> Path:
    """Writes ``form`` to ``path`` (``.pzform`` is added when there is no suffix)."""
    path = Path(path)
    if not path.suffix:
        path = path.with_suffix(SUFFIX)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(form.to_json(), encoding="utf-8")
    return path
