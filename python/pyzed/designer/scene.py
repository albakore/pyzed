"""Components designed visually, like Godot scenes: a layout (``.pzcomp``) plus a ``pz.Component`` class.

A designed component lives in two files next to each other:

* ``rating.pzcomp``: its layout, the controls placed on it (JSON, like a ``.pzform``),
  how it shows in the toolbox and which control properties follow which component
  property (``bindings``).
* ``rating.py``: a ``SceneComponent`` subclass with its properties (public props and
  private state), custom events and methods. It is ordinary code: what you write by
  hand shows up in the designer and what you change in the designer is written there.

Components can be placed inside forms and inside other components, like scenes
inside scenes. ``discover`` imports every designed component of a folder so they
join the toolbox and can be used by forms.

    from pyzed import designer

    doc = designer.new_component("Rating", "ui/rating.pzcomp")
    doc.add("label", 8, 8)
    doc.add_member("value", "int", 3)
    doc.save()
"""

from __future__ import annotations

import json
import os
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from . import code as _code
from . import components as _components
from . import scene_code
from .document import Document
from .model import Control, Form

FORMAT = "pyzed.component/1"
SUFFIX = ".pzcomp"

#: The component's own "events": its main methods, shown in the Events tab when nothing is selected.
ROOT_EVENTS = {"setup": "setup", "mount": "on_mount", "unmount": "on_unmount"}

_EXTRA = ("label", "icon", "category", "description")


@dataclass
class Scene(Form):
    """The layout of a designed component: a ``Form`` whose ``name`` is the class name.

    ``bindings`` maps a control name to ``{control property: expression}``; the
    expression (usually a component property, such as ``value``, or any Python
    expression over them, such as ``f"{value} stars"``) is evaluated on every render.
    """

    name: str = "Component1"
    title: str = "Component1"
    width: float = 240.0
    height: float = 120.0
    resizable: bool = False
    label: str = ""
    icon: str = "component"
    category: str = "Custom"
    description: str = ""
    bindings: Dict[str, Dict[str, str]] = field(default_factory=dict)

    @property
    def class_name(self) -> str:
        return self.name

    def bound(self, control: str) -> Dict[str, str]:
        return self.bindings.get(control, {})

    def rename(self, old: str, new: str) -> str:
        new = super().rename(old, new)
        if new != old and old in self.bindings:
            self.bindings[new] = self.bindings.pop(old)
        return new

    def remove(self, names: Iterable[str]) -> List[Control]:
        removed = super().remove(names)
        for control in removed:
            self.bindings.pop(control.name, None)
        return removed

    def to_dict(self) -> Dict[str, Any]:
        data = {k: v for k, v in asdict(self).items() if k not in ("controls", "bindings", "title", "events")}
        return {
            "format": FORMAT,
            "component": data,
            "events": dict(self.events),
            "controls": [c.to_dict() for c in self.controls],
            "bindings": {k: dict(v) for k, v in self.bindings.items() if v},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Scene":
        fmt = str(data.get("format", FORMAT))
        if not fmt.startswith("pyzed.component/"):
            raise ValueError(f"not a Pyzed component (format {fmt!r})")
        settings = {k: v for k, v in (data.get("component") or {}).items() if k in cls.__dataclass_fields__}
        for key in ("controls", "bindings", "events"):
            settings.pop(key, None)
        scene = cls(**settings)
        scene.title = scene.name
        scene.events = dict(data.get("events") or {})
        scene.controls = [Control.from_dict(c) for c in data.get("controls", [])]
        scene.bindings = {str(k): {str(p): str(e) for p, e in (v or {}).items()}
                          for k, v in (data.get("bindings") or {}).items()}
        return scene

    @classmethod
    def from_json(cls, text: str) -> "Scene":
        return cls.from_dict(json.loads(text))


def load(path: Union[str, Path]) -> Scene:
    """Reads a ``.pzcomp`` file."""
    return Scene.from_json(Path(path).read_text(encoding="utf-8"))


def save(scene: Scene, path: Union[str, Path]) -> Path:
    path = Path(path)
    if not path.suffix:
        path = path.with_suffix(SUFFIX)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(scene.to_json(), encoding="utf-8")
    return path


def code_path(scene_path: Union[str, Path], scene: Optional[Scene] = None) -> Path:
    scene_path = Path(scene_path)
    if scene is not None and scene.code:
        return (scene_path.parent / scene.code).resolve()
    return scene_path.with_suffix(".py")


# -- editing ---------------------------------------------------------------------


class SceneDocument(Document):
    """A component open in the designer: its scene, its class code, selection and undo.

    Every command of ``Document`` works (placing, moving, aligning controls...). Events
    of controls become methods of the class (``def ok_click(self, event)``), and the
    component's own events are its lifecycle methods (``setup``, ``on_mount``...).
    Properties and custom events are read from the class and written back to it.
    """

    is_scene = True
    suffix = SUFFIX
    kind = "component"

    def __init__(self, scene: Optional[Scene] = None, path: Optional[Union[str, Path]] = None,
                 code: Optional[str] = None) -> None:
        scene = scene or Scene()
        if path is not None and not Path(path).suffix:
            path = Path(path).with_suffix(SUFFIX)
        file = Path(path).name if path else f"{scene.name.lower()}{SUFFIX}"
        if code is None:
            code = scene_code.new_module(scene.name, file, scene.description)
        super().__init__(scene, path, code)
        self._info: Tuple[str, Optional[scene_code.ClassInfo]] = ("", None)
        self._last_info: scene_code.ClassInfo = scene_code.ClassInfo(scene.name)

    @property
    def scene(self) -> Scene:
        assert isinstance(self.form, Scene)
        return self.form

    # -- files --------------------------------------------------------------
    @classmethod
    def open(cls, path: Union[str, Path]) -> "SceneDocument":
        path = Path(path)
        scene = load(path)
        module = code_path(path, scene)
        code = module.read_text(encoding="utf-8") if module.exists() else None
        return cls(scene, path, code)

    @property
    def code_path(self) -> Optional[Path]:
        return code_path(self.path, self.scene) if self.path else None

    @property
    def display_name(self) -> str:
        return self.path.name if self.path else f"{self.scene.name.lower()}{SUFFIX}"

    def save(self, path: Optional[Union[str, Path]] = None) -> Path:
        """Writes the scene and its class, then reloads the class so the toolbox shows the changes."""
        if path is not None:
            self.path = Path(path) if Path(path).suffix else Path(path).with_suffix(SUFFIX)
        if self.path is None:
            raise ValueError("this component has no file yet; pass a path")
        save(self.scene, self.path)
        self.code = scene_code.set_scene_file(self.code, self.path.name, self._class())
        module = self.code_path
        assert module is not None
        module.write_text(self.code, encoding="utf-8")
        self.dirty = False
        from .scene_runtime import scenes

        scenes.overrides.pop(self.path.resolve(), None)
        load_component(self.path)
        return self.path

    # -- the class ----------------------------------------------------------
    @property
    def info(self) -> scene_code.ClassInfo:
        """The class as last parsed (the last good parse while the code has a syntax error)."""
        if self._info[0] != self.code:
            parsed = scene_code.read(self.code, self.scene.name) or scene_code.read(self.code)
            self._info = (self.code, parsed)
            if parsed is not None:
                self._last_info = parsed
        return self._info[1] or self._last_info

    @property
    def code_ok(self) -> bool:
        _ = self.info
        return self._info[1] is not None

    @property
    def members(self) -> List[scene_code.Member]:
        return list(self.info.members)

    def member(self, name: str) -> Optional[scene_code.Member]:
        return next((m for m in self.info.members if m.name == name), None)

    def _write_members(self, members: List[scene_code.Member]) -> None:
        self.code = scene_code.set_members(self.code, members, self._class())
        self.dirty = True

    def _class(self) -> str:
        return self.info.name

    def unique_member(self, base: str = "value") -> str:
        taken = {m.name for m in self.info.members} | set(self.info.methods) | set(self.scene.names()) \
            | scene_code.RESERVED | {"emit", "render", "handles", "create"}
        base = scene_code.member_identifier(base) or "value"
        if base not in taken:
            return base
        n = 2
        while f"{base}{n}" in taken:
            n += 1
        return f"{base}{n}"

    def add_member(self, name: str = "", type_: str = "str", default: Any = None, *, public: bool = True,
                   description: str = "") -> scene_code.Member:
        """Declares a new property (``public=False`` makes it private state)."""
        if default is None:
            default = DEFAULTS.get(type_)
        member = scene_code.Member(self.unique_member(name or "value"), type_, default, public, description)
        self._write_members([*self.members, member])
        return member

    def update_member(self, member: str, /, **changes: Any) -> str:
        """Changes a property (``name``, ``type``, ``default``, ``public``, ``description``); returns its name."""
        members = self.members
        m = next((x for x in members if x.name == member), None)
        if m is None:
            raise KeyError(member)
        if "name" in changes:
            new = scene_code.member_identifier(changes.pop("name"))
            if new and new != member:
                if new in {x.name for x in members}:
                    new = self.unique_member(new)
                changes["name"] = new
                self._rename_in_bindings(member, new)
        if "type" in changes and "default" not in changes and changes["type"] != m.type:
            changes["default"] = convert(m.default, changes["type"])
        if "default" in changes:
            changes.setdefault("source", None)
        for key, value in changes.items():
            setattr(m, key, value)
        self._write_members(members)
        return m.name

    def remove_member(self, name: str) -> None:
        self._write_members([m for m in self.members if m.name != name])

    def move_member(self, name: str, offset: int) -> None:
        members = self.members
        index = next((i for i, m in enumerate(members) if m.name == name), None)
        if index is None:
            return
        target = max(0, min(len(members) - 1, index + offset))
        members.insert(target, members.pop(index))
        self._write_members(members)

    def _rename_in_bindings(self, old: str, new: str) -> None:
        for props in self.scene.bindings.values():
            for prop, expr in list(props.items()):
                if expr == old:
                    props[prop] = new

    # custom events
    @property
    def custom_events(self) -> Dict[str, str]:
        return dict(self.info.events)

    def _write_events(self, events: Dict[str, str]) -> None:
        self.code = scene_code.set_events(self.code, events, self._class())
        self.dirty = True

    def add_event(self, name: str = "changed", description: str = "") -> str:
        events = self.custom_events
        base = scene_code.member_identifier(name) or "changed"
        name, n = base, 2
        while name in events or name in ROOT_EVENTS:
            name, n = f"{base}{n}", n + 1
        events[name] = description
        self._write_events(events)
        return name

    def update_event(self, name: str, *, new_name: Optional[str] = None, description: Optional[str] = None) -> str:
        events = self.custom_events
        if name not in events:
            raise KeyError(name)
        out: Dict[str, str] = {}
        result = name
        for key, doc in events.items():
            if key == name:
                if new_name is not None:
                    candidate = scene_code.member_identifier(new_name)
                    if candidate and candidate not in events and candidate not in ROOT_EVENTS:
                        result = candidate
                out[result] = doc if description is None else description
            else:
                out[key] = doc
        self._write_events(out)
        return result

    def remove_event(self, name: str) -> None:
        events = self.custom_events
        events.pop(name, None)
        self._write_events(events)

    def set_class_name(self, name: str) -> str:
        new = scene_code.class_identifier(name)
        old = self.info.name
        if new == old:
            return old
        self.code = scene_code.rename_class(self.code, old, new)
        self.scene.name = self.scene.title = new
        self.dirty = True
        self.commit(group="scene:name")
        return new

    def set_description(self, text: str) -> None:
        self.scene.description = text
        self.code = scene_code.set_docstring(self.code, text or f"The {self.scene.name} component.", self._class())
        self.dirty = True
        self.commit(group="scene:description")

    def set_scene(self, key: str, value: Any) -> None:
        """Sets how the component shows in the toolbox (``label``, ``icon``, ``category``) or its size."""
        setattr(self.scene, key, value)
        self.commit(group=f"scene:{key}")

    def set_form(self, key: str, value: Any) -> None:
        if key == "name":
            self.set_class_name(value)
        else:
            super().set_form(key, value)

    # bindings
    def set_binding(self, control: str, prop: str, expression: Optional[str]) -> None:
        """Makes ``prop`` of ``control`` follow ``expression`` (``None`` or ``""`` removes the binding)."""
        props = self.scene.bindings.setdefault(control, {})
        if expression:
            props[prop] = expression.strip()
        else:
            props.pop(prop, None)
        if not props:
            self.scene.bindings.pop(control, None)
        self.commit(group=f"bind:{control}:{prop}")

    # -- events and code ----------------------------------------------------
    def events_of(self, name: Optional[str]) -> Tuple[str, ...]:
        if name is None:
            return tuple(ROOT_EVENTS)
        return super().events_of(name)

    def wire(self, name: Optional[str], event: str) -> str:
        """Connects ``event`` to a method of the class (adding its stub) and returns the method name."""
        if name is None:
            method = ROOT_EVENTS.get(event, event)
            if self.scene.events.get(event) != method:
                self.scene.events[event] = method
                self.commit()
            args, doc = scene_code.LIFECYCLE.get(method, ("self", ""))
            self.code, created = scene_code.ensure_method(self.code, method, doc, args, self._class())
        else:
            owner, events = self.owner(name)
            method = events.get(event) or _code.handler_name(owner, event)
            if events.get(event) != method:
                events[event] = method
                self.commit()
            doc = _components.EVENT_DOCS.get(event, "Event handler.").format(name=owner)
            self.code, created = scene_code.ensure_method(self.code, method, doc, "self, event", self._class())
        if created:
            self.dirty = True
        return method

    def unwire(self, name: Optional[str], event: str, *, delete_code: bool = False) -> None:
        _, events = self.owner(name)
        method = events.pop(event, None)
        if method and delete_code:
            source = scene_code.get_method(self.code, method, self._class())
            still_used = any(method in c.events.values() for c in self.scene.controls) or \
                method in self.scene.events.values()
            if source and not still_used and _code.body_is_empty(source):
                self.code = scene_code.remove_method(self.code, method, self._class())
        self.commit()

    def handler_source(self, handler: str) -> str:
        source = scene_code.get_method(self.code, handler, self._class())
        if source is not None:
            return source
        args, doc = scene_code.LIFECYCLE.get(handler, ("self, event", ""))
        return scene_code.method_stub(handler, doc, args)

    def set_handler_source(self, handler: str, source: str) -> None:
        self.code = scene_code.replace_method(self.code, handler, source, self._class())
        self.dirty = True

    def set_code(self, source: str) -> None:
        super().set_code(source)
        parsed = scene_code.read(source)
        if parsed is not None and parsed.name != self.scene.name:
            self.scene.name = self.scene.title = parsed.name  # the class was renamed by hand
            self.commit(group="scene:name")

    def rename(self, old: str, new: str) -> str:
        """Renames a control, its bindings and the methods that follow the naming convention."""
        control = self.scene.get(old)
        if control is None:
            return old
        new = self.scene.rename(old, new)
        if new == old:
            return old
        self.selection = [new if n == old else n for n in self.selection]
        for event, handler in list(control.events.items()):
            if handler == _code.handler_name(old, event):
                renamed = _code.handler_name(new, event)
                self.code = scene_code.rename_method(self.code, handler, renamed, self._class())
                control.events[event] = renamed
        self.commit()
        return new


#: The default value of a new property of each type.
DEFAULTS: Dict[str, Any] = {"str": "", "int": 0, "float": 0.0, "bool": False, "list": [], "dict": {}, "Any": None}


def convert(value: Any, type_: str) -> Any:
    """``value`` as ``type_`` when it can be converted, else that type's default."""
    try:
        if type_ == "str":
            return "" if value is None else str(value)
        if type_ == "int":
            return int(float(value))
        if type_ == "float":
            return float(value)
        if type_ == "bool":
            return bool(value) if not isinstance(value, str) else value.strip().lower() in ("1", "true", "yes", "on")
        if type_ == "list":
            return list(value) if isinstance(value, (list, tuple)) else []
        if type_ == "dict":
            return dict(value) if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        pass
    return DEFAULTS.get(type_)


def new_component(name: str = "Component1", path: Optional[Union[str, Path]] = None, *,
                  width: float = 240, height: float = 120, label: str = "", icon: str = "component",
                  category: str = "Custom", description: str = "") -> SceneDocument:
    """A new designed component (not saved yet; call ``save()``): its scene and an empty class."""
    class_name = scene_code.class_identifier(name)
    scene = Scene(name=class_name, title=class_name, width=width, height=height, label=label, icon=icon,
                  category=category, description=description)
    return SceneDocument(scene, path)


# -- loading the classes ------------------------------------------------------------

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "target", "__pycache__", "dist", "build"}

#: Import errors of the last ``load_component``/``discover`` calls, by ``.pzcomp`` path.
errors: Dict[Path, str] = {}


def load_component(path: Union[str, Path]) -> Optional[type]:
    """Imports the class of the component saved at ``path`` (fresh, so edits are picked up).

    Defining the class registers it in the toolbox, replacing an older version. Returns
    the class, or ``None`` (with the reason in ``errors``) if its code fails to import.
    """
    from .scene_runtime import SceneComponent

    path = Path(path).resolve()
    errors.pop(path, None)
    try:
        scene = load(path)
        module_path = code_path(path, scene)
        if not module_path.exists():
            errors[path] = f"{module_path.name} is missing"
            return None
        module = _code.load_module(module_path)
    except Exception as err:  # noqa: BLE001 - reported to the designer or the runner
        errors[path] = f"{type(err).__name__}: {err}"
        traceback.print_exc()
        return None
    for value in vars(module).values():
        if isinstance(value, type) and issubclass(value, SceneComponent) and value is not SceneComponent \
                and value.scene_path() == path:
            return value
    errors[path] = f"{module_path.name} has no SceneComponent class for {path.name}"
    return None


def open_document(path: Union[str, Path]) -> Document:
    """Opens a ``.pzform`` as a ``Document`` or a ``.pzcomp`` as a ``SceneDocument``."""
    path = Path(path)
    return SceneDocument.open(path) if path.suffix == SUFFIX else Document.open(path)


def component_files(root: Union[str, Path], limit: int = 500) -> List[Path]:
    """The ``.pzcomp`` files under ``root``, skipping virtualenvs, build output and hidden folders."""
    found: List[Path] = []
    if not Path(root).is_dir():
        return found
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        found.extend(Path(folder) / f for f in sorted(files) if f.endswith(SUFFIX))
        if len(found) >= limit:
            break
    return found[:limit]


def discover(root: Union[str, Path, None] = None) -> List[type]:
    """Imports every designed component under ``root`` (the current folder by default).

    Components may use each other, so a failed import is retried once the others
    loaded (``errors`` keeps what still failed).
    """
    pending = component_files(root or Path.cwd())
    loaded: List[type] = []
    for _ in range(2):
        retry = []
        for path in pending:
            cls = load_component(path)
            if cls is None:
                retry.append(path)
            else:
                loaded.append(cls)
        if not retry or len(retry) == len(pending):
            break
        pending = retry
    return loaded
