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

#: Names a control cannot take because handlers use them on the form (``form.title``...).
RESERVED = frozenset({"name", "title", "size", "window", "close"} | set(keyword.kwlist))

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
    ``grow`` in a flex row or ``span`` in a grid.
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

    @property
    def rect(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.width, self.height)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["anchor"] = list(self.anchor)
        # Only containers' children carry these, so plain forms stay as they were.
        if not data["parent"]:
            del data["parent"]
        if not data["layout"]:
            del data["layout"]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Control":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        known["anchor"] = tuple(a for a in known.get("anchor", ("left", "top")) if a in ANCHORS)
        known["props"] = dict(known.get("props") or {})
        known["events"] = dict(known.get("events") or {})
        known["layout"] = dict(known.get("layout") or {})
        known["parent"] = known.get("parent") or None
        return cls(**known)

    def copy(self) -> "Control":
        return copy.deepcopy(self)


@dataclass
class Form:
    """A window designed visually: its settings, its controls (in z-order) and its events.

    ``theme`` is any registered theme name; ``accent``, ``radius`` and ``font_size``
    tweak it without writing a theme file. ``grid`` is the designer's snapping step.
    """

    name: str = "Form1"
    title: str = "Form1"
    width: float = 640.0
    height: float = 420.0
    theme: str = "One Dark"
    accent: Optional[str] = None
    background: Optional[str] = None
    radius: Optional[float] = None
    font_size: float = 14.0
    resizable: bool = True
    grid: int = 8
    controls: List[Control] = field(default_factory=list)
    events: Dict[str, str] = field(default_factory=dict)
    code: Optional[str] = None

    # -- lookup -------------------------------------------------------------
    def get(self, name: str) -> Optional[Control]:
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
        return new

    def reorder(self, names: Iterable[str], where: str) -> None:
        """Moves controls to the ``"front"`` or ``"back"`` of the z-order."""
        names = set(names)
        picked = [c for c in self.controls if c.name in names]
        rest = [c for c in self.controls if c.name not in names]
        self.controls = rest + picked if where == "front" else picked + rest

    # -- serialization ------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        data = {k: v for k, v in asdict(self).items() if k not in ("controls",)}
        return {
            "format": FORMAT,
            "form": data,
            "controls": [c.to_dict() for c in self.controls],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Form":
        fmt = data.get("format", FORMAT)
        if not str(fmt).startswith("pyzed.form/"):
            raise ValueError(f"not a Pyzed form (format {fmt!r})")
        settings = {k: v for k, v in (data.get("form") or {}).items() if k in cls.__dataclass_fields__}
        settings.pop("controls", None)
        form = cls(**settings)
        form.events = dict(form.events or {})
        form.controls = [Control.from_dict(c) for c in data.get("controls", [])]
        form._repair_parents()
        return form

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "Form":
        return cls.from_dict(json.loads(text))

    def copy(self) -> "Form":
        return copy.deepcopy(self)


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
