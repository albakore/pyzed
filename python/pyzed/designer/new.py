"""Creating forms: templates and ``new_form``, used by the designer's "New form" dialog and by scripts.

    from pyzed import designer

    path = designer.new_form("ui/settings", template="dialog", title="Settings")
    designer.design(path)

The templates are data, not code: each one is a folder in ``designer/templates`` with a
``template.json`` (label, icon, description), the ``form.pzform`` to start from and, if the
template wires events, a ``handlers.py.tmpl`` with their code (Python, named ``.tmpl`` so
packagers keep it as a data file). ``{title}`` in the form's texts becomes the new form's
title. Add your own folders with ``load_templates``, or build a
template in Python with ``Template(..., build=fill)`` and ``register_template``.
"""

from __future__ import annotations

import ast
import json
import re

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from . import code as _code
from . import components as _components
from .document import Document
from .model import SUFFIX, Control, Form, identifier

#: The templates that come with the designer, one folder each.
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@dataclass(frozen=True)
class Template:
    """A starting point for new forms: a ``build`` function that fills an empty ``Form``, or a saved form."""

    name: str
    label: str
    icon: str
    description: str
    build: Optional[Callable[[Form], None]] = None
    size: tuple = (640, 420)
    #: ``(handler, source)`` pairs replacing the generated stubs of handlers the template wires
    handlers: tuple = ()
    #: The form to copy (the contents of a ``.pzform``), for templates loaded from a folder
    form: Optional[Dict[str, Any]] = None


_TEMPLATES: Dict[str, Template] = {}


def register_template(template: Template) -> Template:
    """Adds (or replaces, by name) a template offered in the "New form" dialog; returns it."""
    _TEMPLATES[template.name] = template
    return template


def templates() -> List[Template]:
    """Returns the registered form templates, in registration order."""
    return list(_TEMPLATES.values())


def _handlers(path: Path) -> tuple:
    """The ``(name, source)`` of each function in a template's ``handlers.py.tmpl``."""
    if not path.is_file():
        return ()
    text = path.read_text(encoding="utf-8")
    return tuple((node.name, ast.get_source_segment(text, node) + "\n") for node in ast.parse(text).body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))


def load_template(folder: Union[str, Path]) -> Template:
    """Reads the template in ``folder`` (``template.json``, ``form.pzform`` and an optional ``handlers.py.tmpl``)."""
    folder = Path(folder)
    meta = json.loads((folder / "template.json").read_text(encoding="utf-8"))
    form = json.loads((folder / "form.pzform").read_text(encoding="utf-8"))
    size = (form["form"].get("width", 640), form["form"].get("height", 420))
    return Template(meta.get("name", folder.name), meta.get("label", folder.name.title()), meta.get("icon", "file"),
                    meta.get("description", ""), size=tuple(size), handlers=_handlers(folder / "handlers.py.tmpl"),
                    form=form)


def load_templates(folder: Union[str, Path]) -> List[Template]:
    """Registers every template folder inside ``folder`` (sorted by their ``order``); returns them."""
    found = []
    for path in sorted(Path(folder).iterdir()):
        if (path / "template.json").is_file():
            order = json.loads((path / "template.json").read_text(encoding="utf-8")).get("order", 1000)
            found.append((order, path.name, load_template(path)))
    return [register_template(t) for _, _, t in sorted(found, key=lambda x: (x[0], x[1]))]


def _place(form: Form, type_: str, name: str, x: float, y: float, w: Optional[float] = None,
           h: Optional[float] = None, *, parent: Optional[str] = None, **props) -> Control:
    """Adds a control of ``type_`` with its defaults; a helper for ``build`` functions."""
    control = _components.get(type_).create(name, x, y, w, h)
    control.props.update(props)
    control.parent = parent
    return form.add(control)


def _titled(value: Any, title: str) -> Any:
    """``value`` with ``{title}`` replaced, inside strings, lists and dicts."""
    if isinstance(value, str):
        return value.replace("{title}", title)
    if isinstance(value, list):
        return [_titled(v, title) for v in value]
    if isinstance(value, dict):
        return {k: _titled(v, title) for k, v in value.items()}
    return value


load_templates(TEMPLATES_DIR)


def create(name: str = "Form1", *, title: Optional[str] = None, template: str = "blank",
           width: Optional[float] = None, height: Optional[float] = None) -> Document:
    """A new, unsaved form built from ``template``, with stubs for the events the template wires."""
    try:
        spec = _TEMPLATES[template]
    except KeyError:
        raise KeyError(f"unknown template {template!r}; available: {sorted(_TEMPLATES)}") from None
    name = name if name.isidentifier() else (identifier(name) or "form1")
    title = title or name.replace("_", " ").title()
    if spec.form is not None:
        form = Form.from_dict(_titled(spec.form, title))
        form.name, form.title = name, title
    else:
        form = Form(name=name, title=title, width=float(width or spec.size[0]), height=float(height or spec.size[1]))
        if spec.build is not None:
            spec.build(form)
    doc = Document(form, code=_code.new_module(form.name))
    if spec.form is not None and (width or height):
        # a saved form drawn at its own size: resize it, moving what is inside as the anchors say
        size = (form.width, form.height)
        form.width, form.height = float(width or form.width), float(height or form.height)
        doc.reflow(None, size)
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

    The form is named after the file (``order-details.pzform`` -> ``OrderDetails``).

    Returns the form's path. Raises ``FileExistsError`` if it exists, unless ``overwrite``.
    """
    path = Path(path)
    if path.suffix != SUFFIX:
        path = path.with_suffix(SUFFIX)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists")
    # settings.pzform -> Settings, order-details.pzform -> OrderDetails
    name = "".join(part.capitalize() for part in re.split(r"[^0-9a-zA-Z]+", path.stem) if part) or "Form1"
    doc = create(name, title=title, template=template, width=width, height=height)
    return doc.save(path)
