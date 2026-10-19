"""Creating forms: templates and ``new_form``, used by the designer's "New form" dialog and by scripts.

    from pyzed import designer

    path = designer.new_form("ui/settings", template="dialog", title="Settings")
    designer.design(path)

A template is a function that fills an empty ``Form``; add your own with
``register_template``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Union

from . import code as _code
from . import components as _components
from .document import Document
from .model import SUFFIX, Control, Form, identifier


@dataclass(frozen=True)
class Template:
    """A starting point for new forms."""

    name: str
    label: str
    icon: str
    description: str
    build: Callable[[Form], None]
    size: tuple = (640, 420)
    #: ``(handler, source)`` pairs replacing the generated stubs of handlers the template wires
    handlers: tuple = ()


_TEMPLATES: Dict[str, Template] = {}


def register_template(template: Template) -> Template:
    _TEMPLATES[template.name] = template
    return template


def templates() -> List[Template]:
    return list(_TEMPLATES.values())


def _place(form: Form, type_: str, name: str, x: float, y: float, w: Optional[float] = None,
           h: Optional[float] = None, *, parent: Optional[str] = None, **props) -> Control:
    control = _components.get(type_).create(name, x, y, w, h)
    control.props.update(props)
    control.parent = parent
    return form.add(control)


def _blank(form: Form) -> None:
    return None


def _dialog(form: Form) -> None:
    _place(form, "heading", "heading", 24, 20, form.width - 48, 32, text=form.title, level="2")
    _place(form, "label", "message", 24, 64, form.width - 48, form.height - 140, text="Write your message here.")
    buttons = _place(form, "row", "buttons", 24, form.height - 60, form.width - 48, 36, justify="end")
    buttons.anchor = ("left", "right", "bottom")
    _place(form, "button", "cancel", 0, 0, 96, 32, parent="buttons", text="Cancel", variant="ghost")
    _place(form, "button", "ok", 0, 0, 96, 32, parent="buttons", text="OK", variant="solid")
    form["ok"].events["click"] = "ok_click"
    form["cancel"].events["click"] = "cancel_click"


_DIALOG_CODE = (
    ("ok_click", 'def ok_click(form, event):\n    """Accepts the dialog."""\n    return form.close()\n'),
    ("cancel_click", 'def cancel_click(form, event):\n    """Closes the dialog without changes."""\n    return form.close()\n'),
)


def _login(form: Form) -> None:
    card = _place(form, "column", "fields", (form.width - 320) / 2, 40, 320, 300, gap=12)
    card.anchor = ()
    _place(form, "heading", "heading", 0, 0, 320, 36, parent="fields", text="Sign in", level="2")
    _place(form, "input", "email", 0, 0, 320, 32, parent="fields", placeholder="Email", icon="mail")
    _place(form, "input", "password", 0, 0, 320, 32, parent="fields", placeholder="Password", icon="lock",
           secure=True)
    _place(form, "checkbox", "remember", 0, 0, 320, 24, parent="fields", text="Remember me")
    _place(form, "button", "sign_in", 0, 0, 320, 34, parent="fields", text="Sign in", variant="solid")
    _place(form, "label", "status", 0, 0, 320, 24, parent="fields", text="", color="text_muted", size="sm")


def _sidebar(form: Form) -> None:
    side = _place(form, "column", "sidebar", 0, 0, 200, form.height, gap=4, padding=12, background="surface")
    side.anchor = ("left", "top", "bottom")
    for i, label in enumerate(("Home", "Projects", "Settings")):
        _place(form, "button", f"nav{i + 1}", 0, 0, 176, 30, parent="sidebar", text=label, variant="ghost",
               icon=("house", "folder", "settings")[i])
    main = _place(form, "column", "content", 200, 0, form.width - 200, form.height, gap=12, padding=24)
    main.anchor = ("left", "top", "right", "bottom")
    _place(form, "heading", "title", 0, 0, 300, 36, parent="content", text="Home")
    _place(form, "label", "body", 0, 0, 300, 60, parent="content", text="Pick a section on the left.")


def _settings(form: Form) -> None:
    grid = _place(form, "grid", "options", 24, 24, form.width - 48, 168, columns=2, gap=12, row_height=28,
                  align="center")
    grid.anchor = ("left", "top", "right")
    for i, (label, kind) in enumerate((("Name", "input"), ("Theme", "select"), ("Notifications", "switch"),
                                       ("Volume", "slider"))):
        _place(form, "label", f"label{i + 1}", 0, 0, 120, 24, parent="options", text=label)
        _place(form, kind, f"{kind}{i + 1}", 0, 0, 200, 28, parent="options",
               **({"text": ""} if kind == "switch" else {}))
    buttons = _place(form, "row", "buttons", 24, form.height - 60, form.width - 48, 36, justify="end")
    buttons.anchor = ("left", "right", "bottom")
    _place(form, "button", "save", 0, 0, 96, 32, parent="buttons", text="Save", variant="solid")


for _template in (
    Template("blank", "Blank", "square-dashed", "An empty window.", _blank),
    Template("dialog", "Dialog", "message-square", "A message with OK and Cancel buttons.", _dialog, (420, 220),
             _DIALOG_CODE),
    Template("login", "Sign in", "log-in", "Email and password in a centered column.", _login, (520, 380)),
    Template("sidebar", "Sidebar", "panel-left", "Navigation on the left and content on the right.", _sidebar,
             (760, 480)),
    Template("settings", "Settings", "settings", "Labelled options in a grid.", _settings, (480, 280)),
):
    register_template(_template)


def create(name: str = "Form1", *, title: Optional[str] = None, template: str = "blank",
           width: Optional[float] = None, height: Optional[float] = None) -> Document:
    """A new, unsaved form built from ``template``, with stubs for the events the template wires."""
    try:
        spec = _TEMPLATES[template]
    except KeyError:
        raise KeyError(f"unknown template {template!r}; available: {sorted(_TEMPLATES)}") from None
    name = identifier(name) or "form1"
    form = Form(name=name, title=title or name.replace("_", " ").title(), width=float(width or spec.size[0]),
                height=float(height or spec.size[1]))
    spec.build(form)
    doc = Document(form, code=_code.new_module(form.name))
    for owner, events in [(None, form.events)] + [(c.name, c.events) for c in form.controls]:
        for event in list(events):
            doc.wire(owner, event)
    for handler, source in spec.handlers:
        doc.set_handler_source(handler, source)
    doc.history = type(doc.history)(form)
    doc.dirty = True
    return doc


def new_form(path: Union[str, Path], *, title: Optional[str] = None, template: str = "blank",
             width: Optional[float] = None, height: Optional[float] = None, overwrite: bool = False) -> Path:
    """Creates ``path`` (``.pzform`` added if missing) and its handlers module from ``template``.

    Returns the form's path. Raises ``FileExistsError`` if it exists, unless ``overwrite``.
    """
    path = Path(path)
    if path.suffix != SUFFIX:
        path = path.with_suffix(SUFFIX)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists")
    doc = create(path.stem, title=title, template=template, width=width, height=height)
    return doc.save(path)
