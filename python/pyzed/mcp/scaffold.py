"""Code generators of the MCP server: components, apps and designer forms.

Each function returns source text (or, for forms, both files) and never writes to disk, so an agent
can review the result before saving it where it wants.
"""

from __future__ import annotations

import keyword
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence

#: Python literals accepted as a prop default when given as text.
_LITERAL = re.compile(r"^(-?\d+(\.\d+)?|True|False|None|\".*\"|'.*'|\[.*\]|\(.*\)|\{.*\})$")


def _identifier(name: str, what: str) -> str:
    name = (name or "").strip()
    if not name.isidentifier() or keyword.iskeyword(name):
        raise ValueError(f"{what} {name!r} is not a valid Python identifier")
    return name


def _member(name: str, what: str) -> str:
    from ..component import _RESERVED, Component

    name = _identifier(name, what)
    if name in _RESERVED or name.startswith("_") or hasattr(Component, name):
        raise ValueError(f"{what} {name!r} is reserved by pz.Component; pick another name")
    return name


def _class_name(name: str) -> str:
    words = re.split(r"[^0-9A-Za-z]+", name.strip())
    out = "".join(w[:1].upper() + w[1:] for w in words if w)
    if out[:1].isdigit():
        out = "_" + out
    return _identifier(out, "component name")


def _default(value: Any) -> str:
    if isinstance(value, str) and _LITERAL.match(value.strip()):
        return value.strip()
    return repr(value)


def _type_of(prop: Mapping[str, Any]) -> str:
    if prop.get("type"):
        return str(prop["type"])
    default = prop.get("default")
    if isinstance(default, bool):
        return "bool"
    if isinstance(default, int):
        return "int"
    if isinstance(default, float):
        return "float"
    if isinstance(default, (list, tuple)):
        return "list"
    if isinstance(default, dict):
        return "dict"
    return "str"


def _fallback_default(type_: str) -> str:
    return {"bool": "False", "int": "0", "float": "0.0", "list": "[]"}.get(type_, '""')


def component(name: str, *, description: str = "", props: Sequence[Mapping[str, Any]] = (),
              state: Sequence[Mapping[str, Any]] = (), events: Optional[Mapping[str, str]] = None,
              icon: str = "box", category: str = "Custom") -> Dict[str, str]:
    """A ``pz.Component`` subclass with the given props, state and events, ready to fill in.

    ``props`` and ``state`` are lists of ``{"name", "type", "default", "doc"}`` (``type`` and
    ``default`` optional). ``events`` maps event names to what they mean. Returns ``code`` (the
    module) and ``usage`` (how a view uses it).
    """
    from ..component import LIFECYCLE_EVENTS, Component

    cls = _class_name(name)
    events = {_identifier(e, "event name"): doc for e, doc in dict(events or {}).items()}
    for event in events:
        if event in LIFECYCLE_EVENTS:
            raise ValueError(f"{event!r} is a built-in lifecycle event of every component")
    # A method per event raises it; one that would shadow a Component method gets an emit_ prefix.
    methods = {e: (f"emit_{e}" if hasattr(Component, e) else e) for e in events}
    lines = ['"""' + (description or f"The {cls} component.") + '"""', "", "import pyzed as pz",
             "from pyzed import ui", "", "", f"class {cls}(pz.Component):",
             f'    """{description or f"The {cls} component."}"""', ""]
    lines += [f'    icon = "{icon}"', f'    category = "{category}"']
    if events:
        lines.append("    events = {")
        lines += [f'        "{e}": {doc!r},' for e, doc in events.items()]
        lines.append("    }")
    lines += ["", "    # Its look, like CSS: & is the component; the parent adds class_=, id= and style=.",
              "    stylesheet = {",
              '        "&": {"background": "panel", "border": (1, "border"), "radius": 8, "padding": 12,',
              '              "transition": 120},',
              '        "&:hover": {"border_color": "accent"},',
              "    }"]
    nests = not any(str(p.get("name", "")) == "children" for p in props)
    if nests:
        lines += ["", "    children: list = ()  # what the parent nests inside, like HTML children"]
    if props:
        lines += ["", "    # Props: the parent passes them on every render."]
        for prop in props:
            pname = _member(str(prop.get("name", "")), "prop name")
            ptype = _type_of(prop)
            default = _default(prop["default"]) if "default" in prop else _fallback_default(ptype)
            doc = f"  # {prop['doc']}" if prop.get("doc") else ""
            lines.append(f"    {pname}: {ptype} = {default}{doc}")
    if state:
        lines += ["", "    # State: private, kept between renders."]
        for item in state:
            sname = _member(str(item.get("name", "")), "state name")
            stype = _type_of(item)
            default = _default(item.get("default", None))
            doc = f", doc={item['doc']!r}" if item.get("doc") else ""
            lines.append(f"    {sname}: {stype} = pz.state({default}{doc})")
    for event, method in methods.items():
        lines += ["", f"    def {method}(self, value=None):",
                  f'        """Raises ``{event}``: the parent\'s ``on_{event}`` receives ``event.value``."""',
                  f'        return self.emit("{event}", value)']
    names = [str(p["name"]) for p in props][:4]
    shown = [f'            ui.label(f"{n}: {{self.{n}}}"),' for n in names]
    first_event = next(iter(events), None)
    lines += ["", "    def render(self):", "        return pz.box("]
    lines += shown or [f'            ui.label("{cls}"),']
    if nests:
        lines.append("            *self.children,")
    if first_event:
        text = first_event.replace("_", " ").capitalize()
        lines.append(f'            ui.button("{text}", self.{methods[first_event]}),')
    lines += ["            gap=8,", "        )", ""]
    args = ", ".join(f"{p['name']}=..." for p in props[:3])
    handlers = ", ".join(f"on_{e}=lambda event: ..." for e in list(events)[:2])
    usage = f"{cls}({', '.join(a for a in (args, handlers) if a)})"
    return {"code": "\n".join(lines), "usage": usage, "class_name": cls}


def app(title: str = "My App", *, size: Sequence[int] = (900, 600), theme: str = "One Dark",
        layout: str = "simple") -> str:
    """A ``pz.App`` script. ``layout`` is ``"simple"`` (a centered counter) or ``"workspace"``
    (a Zed-like window with a sidebar, tabs, a status bar and a command palette)."""
    if layout == "workspace":
        from pathlib import Path

        template = (Path(__file__).resolve().parent.parent / "templates" / "app.py.tmpl").read_text(encoding="utf-8")
        return template.format(name=title)
    if layout != "simple":
        raise ValueError('layout must be "simple" or "workspace"')
    width, height = size
    return f'''"""{title}: a Pyzed app. Run it with `python main.py` (or `pyzed dev main.py` for hot reload)."""

import pyzed as pz
from pyzed import ui

# The look of the app, like a CSS file: classes, :hover and media queries.
pz.stylesheet({{
    ".page": {{"width": "fill", "height": "fill", "padding": 32}},
    ".card": {{"background": "panel", "border": (1, "border"), "radius": 12, "padding": 24, "width": 360}},
    "@media (max_width: 480)": {{".page": {{"padding": 12}}}},
}})


class App(pz.App):
    title = {title!r}
    size = ({width}, {height})
    theme = {theme!r}

    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1

    def update(self, message):
        if message == "reset":
            self.count = 0

    def view(self):
        return pz.box(
            pz.box(
                ui.heading(f"Clicks: {{self.count}}"),
                pz.box(
                    ui.button("Click me", self.increment, icon="plus", variant="solid"),
                    ui.button("Reset", "reset", variant="ghost"),
                    display="flex", gap=8,
                ),
                class_="card", gap=16,
            ),
            class_="page", display="flex", justify="center", align="center",
        )


if __name__ == "__main__":
    pz.run(App)
'''


def form(name: str, *, title: str = "", width: float = 480, height: float = 320, theme: str = "One Dark",
         controls: Sequence[Mapping[str, Any]] = (), form_events: Sequence[str] = ()) -> Dict[str, Any]:
    """A designer form: the ``.pzform`` JSON and its handlers module.

    Each control is ``{"type", "name"?, "props"?, "events"?, "x"?, "y"?, "width"?, "height"?,
    "parent"?, "anchor"?}``; ``type`` is a designer toolbox type (``button``, ``input``, ``label``...),
    ``events`` a list of event names (wired to ``<control>_<event>``) or a mapping of event to handler
    name, and ``anchor`` a list of edges or a preset of ``pyzed.anchors.PRESETS`` (``"bottom_wide"``).
    Controls without a position are stacked from the top-left corner. ``form_events`` wires the
    form's own events (``load``, ``close``, ``key``, ``resize``).
    """
    from ..designer import code as code_mod
    from ..designer import components
    from ..designer.model import Form, identifier

    form_name = identifier(name) or "Form1"
    doc = Form(name=form_name, title=title or name, width=width, height=height, theme=theme)
    handlers: List[str] = []
    warnings: List[str] = []
    y = 16.0
    for spec in controls:
        type_ = str(spec.get("type", ""))
        component = components.get(type_)
        control = component.create(str(spec.get("name") or type_), x=spec.get("x", 16), y=spec.get("y", y),
                                   width=spec.get("width"), height=spec.get("height"))
        if "y" not in spec and component.visual and not spec.get("parent"):
            y += control.height + 8
        for key, value in dict(spec.get("props") or {}).items():
            if component.prop(key) is None:
                warnings.append(f"{type_} has no prop {key!r}; known: {', '.join(p.name for p in component.props)}")
            control.props[key] = value
        if spec.get("parent") and not component.visual:
            warnings.append(f"{type_} is non-visual: it belongs to the form, not to {spec['parent']!r}")
        elif spec.get("parent"):
            control.parent = str(spec["parent"])
        if spec.get("anchor"):
            from .. import anchors

            try:
                control.anchor = anchors.edges(spec["anchor"])
            except ValueError as err:
                warnings.append(str(err))
        wanted = spec.get("name")
        control = doc.add(control)
        if wanted and control.name != wanted:
            warnings.append(f"control {wanted!r} was renamed to {control.name!r} (reserved or taken)")
        events = spec.get("events") or {}
        if not isinstance(events, Mapping):
            events = {e: code_mod.handler_name(control.name, e) for e in events}
        for event, handler in events.items():
            if event not in component.all_events:
                warnings.append(f"{type_} has no event {event!r}; known: {', '.join(component.all_events)}")
                continue
            control.events[event] = handler
            handlers.append(handler)
    for event in form_events:
        if event not in components.FORM_EVENTS:
            warnings.append(f"forms have no event {event!r}; known: {', '.join(components.FORM_EVENTS)}")
            continue
        doc.events[event] = code_mod.handler_name("form", event)
        handlers.append(doc.events[event])
    if y + 16 > doc.height:
        doc.height = y + 16
    source = code_mod.new_module(form_name)
    for handler in dict.fromkeys(handlers):
        source, _ = code_mod.ensure_function(source, handler)
    return {
        "files": {f"{form_name}.pzform": doc.to_json(), f"{form_name}.py": source},
        "warnings": warnings,
        "run": f"pyzed run {form_name}.pzform --reload",
    }
