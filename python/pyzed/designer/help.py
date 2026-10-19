"""The designer's pages in the built-in reference: every toolbox control and the objects handlers use.

``pyzed.reference`` holds the library's API; this module adds two sections to it, built from the
toolbox itself (``components``) and from the docstrings of the running form's objects, so a new
control or property shows up without writing anything:

- **Form controls**: one page per toolbox entry, with its properties (type, default and what each
  one does), events (with the handler name to write) and the methods every control has.
- **Form code**: ``form``, a control (``form.button1``) and ``event``, as handlers see them.

``lookup_code`` turns the name under the cursor in the code editor (``form.button1.text``,
``event.value``, ``ui.button``) into the page about it.
"""

from __future__ import annotations

import inspect
import re
from typing import Any, Dict, List, Optional

from .. import reference as _reference
from . import components as _components
from .locale import tr
from .model import Form

SECTION = "Form controls"
CODE_SECTION = "Form code"

#: What each property does, by name. ``(type, name)`` keys describe a property that means
#: something else on one control. Shown in the reference and as the tooltip of the property grid.
PROP_DOCS: Dict[Any, str] = {
    "align": "Where the content sits: start, center or end.",
    "background": "Fill color behind the content (a theme token or a hex color).",
    "border": "Draws a border around the panel.",
    "checked": "Whether it is on. Changes when the user clicks it (read it in the change event).",
    "color": "Text or icon color (a theme token or a hex color).",
    "columns": "How many columns the cells are laid out in.",
    "data": "The table: one row per line, cells separated by commas, the first row is the header.",
    "delta": "The change shown next to the figure (positive is drawn as a rise).",
    "direction": "Whether the children run horizontally (row) or vertically (column).",
    "fit": "How the picture fills its box: contain, cover, fill or none.",
    "gap": "Space between the children, in pixels.",
    "horizontal": "Lays the options out side by side instead of one per line.",
    "icon": "A Lucide icon name (pick it with the icon button).",
    "initials": "The letters shown in the circle.",
    "interval": "Milliseconds between two tick events.",
    "items": "The rows of the list, one per line.",
    "justify": "How the children are spread along the main axis: start, center, end or space between.",
    "keys": "The key combination to draw, such as ctrl-s.",
    "kind": "The chart type: bar, line or donut.",
    "labels": "The label of each value, one per line.",
    "language": "The language used to highlight the text (none for plain text).",
    "level": "The heading size: 1 is the biggest.",
    "line_numbers": "Shows line numbers in a gutter.",
    "max": "The highest value.",
    "min": "The lowest value.",
    "options": "The choices, one per line.",
    "padding": "Space between the border and the children, in pixels.",
    "placeholder": "Hint shown while it is empty.",
    "radius": "Corner radius, in pixels.",
    "row_height": "The height of each row of cells (0 sizes them to their content).",
    "running": "Whether the timer is ticking. Set it from code to start or stop it.",
    "secure": "Hides what is typed (for passwords).",
    "selected": "The option chosen, by its text. Changes when the user picks one.",
    "shadow": "Draws a drop shadow under the card.",
    "size": "Text size: small, normal or large.",
    "source": "Path of the image file, relative to the form.",
    "step": "How much one step changes the value.",
    "striped": "Shades every other row.",
    "tabs": "The tab titles, one per line.",
    "text": "The text shown.",
    "tint": "Semantic color: accent, success, warning, error or info.",
    "title": "The title shown at the top.",
    "trend": "Values drawn as a small line next to the figure, one per line.",
    "value": "The current value. Changes when the user moves it (read it in the change event).",
    "values": "The numbers to plot, separated by commas.",
    "variant": "The button style: filled, ghost, outline, solid...",
    "vertical": "Draws the line vertically.",
    "weight": "Font weight: normal, medium, semibold or bold.",
    "wrap": "Wraps long lines instead of cutting them.",
    ("chip", "selected"): "Whether the chip is selected. Changes when the user clicks it.",
    ("table", "selected"): "Index of the selected row (-1 when none). Changes when the user clicks a row.",
    ("tabs", "selected"): "The title of the open tab.",
    ("icon", "size"): "Icon size, in pixels.",
    ("icon", "name"): "The Lucide icon to draw.",
    ("stat", "value"): "The figure shown, as text.",
    ("progress", "value"): "How much is done, between 0 and max.",
    ("input", "text"): "What the user typed; set it from code to change it.",
    ("search", "text"): "What the user typed; set it from code to change it.",
    ("text_area", "text"): "The text in the box: what the user typed, or set it from code.",
    ("markdown", "text"): "The Markdown source to show.",
}

#: Fields every control has, besides its own properties (read and written like them).
FIELD_DOCS = (
    ("x", "float", "Horizontal position, in pixels from the left of the form (or of its container)."),
    ("y", "float", "Vertical position, in pixels from the top."),
    ("width", "float", "Width in pixels."),
    ("height", "float", "Height in pixels."),
    ("visible", "bool", "Whether the control is shown (`show()` and `hide()` change it)."),
    ("enabled", "bool", "Whether the control reacts to the user."),
)

_KIND_TYPES = {"text": "str", "multiline": "str", "number": "float", "bool": "bool", "color": "str",
               "choice": "str", "list": "str", "rows": "str", "icon": "str"}


def prop_doc(type_: str, name: str) -> str:
    """What the property ``name`` of a control of ``type_`` does (empty when undocumented), translated."""
    text = PROP_DOCS.get((type_, name)) or PROP_DOCS.get(name, "")
    return tr(text) if text else ""


def event_doc(event: str, owner: str = "the control") -> str:
    """What the event does, with ``owner`` in it, translated."""
    text = _components.EVENT_DOCS.get(event, "")
    return tr(text, name=owner) if text else ""


def _md_value(value: Any) -> str:
    if value in (None, ""):
        return "—"
    text = repr(value) if not isinstance(value, str) else f'"{value}"'
    text = text.replace("\n", "\\n").replace("|", "\\|")
    return f"`{text if len(text) <= 40 else text[:37] + '…'}`"


# -- entries ----------------------------------------------------------------------------------------


def _entries(lang: str) -> List[_reference.Entry]:
    section = tr(SECTION)
    out = [
        _reference.Entry(id=f"control:{spec.type}", title=tr(spec.label), section=section, group=tr(spec.category),
                         summary=tr(spec.description) if spec.description else "", icon=spec.icon, kind="control")
        for specs in _components.categories().values() for spec in specs
        if _component_class(spec.type) is None  # a pz.Component has its own page (Your components)
    ]
    code = tr(CODE_SECTION)
    out += [
        _reference.Entry(id="script:form", title="form", section=code, group="",
                         summary=tr("The running form: its controls, title, size and windows."), icon="app-window",
                         kind="class"),
        _reference.Entry(id="script:control", title="form.<control>", section=code, group="",
                         summary=tr("A control of the running form: its properties and methods."), icon="square-mouse-pointer",
                         kind="class"),
        _reference.Entry(id="script:event", title="event", section=code, group="",
                         summary=tr("What a handler receives besides the form: sender, name and value."), icon="zap",
                         kind="class"),
    ]
    return out


def _component_class(type_: str) -> Optional[type]:
    from ..component import find

    return find(type_)


def _entry(id: str, lang: str) -> Optional[_reference.Entry]:  # noqa: A002
    return next((e for e in _entries(lang) if e.id == id), None)


# -- pages ------------------------------------------------------------------------------------------


def _page(id: str, lang: str) -> Optional[_reference.Page]:  # noqa: A002
    entry = _entry(id, lang)
    if entry is None:
        return None
    if id.startswith("control:"):
        return _reference.Page(entry=entry, body=control_markdown(_components.get(id.split(":", 1)[1])),
                               url=f"{_reference.SITE}{'' if lang == 'en' else lang + '/'}editor/properties/")
    from . import runtime

    cls = {"script:form": runtime.FormProxy, "script:control": runtime.ControlProxy,
           "script:event": runtime.Event}[id]
    return _reference.Page(entry=entry, body=script_markdown(id, cls),
                           url=f"{_reference.SITE}{'' if lang == 'en' else lang + '/'}editor/files-and-scripting/")


def control_markdown(spec: _components.Component, name: Optional[str] = None) -> str:
    """The page of a toolbox control: description, example, properties, events and methods.

    ``name`` is the control's name on the form (``button1``); the page uses a made-up one otherwise.
    """
    name = name or f"{spec.type}1"
    out = []
    if spec.description:
        out.append(tr(spec.description))
    first = next((p for p in spec.props if p.kind in ("text", "number", "bool", "multiline")), None)
    example = [f"def {name}_{spec.default_event}(form, event):" if spec.default_event else
               f"def form_load(form, event):"]
    if first is not None:
        value = {"text": '"Hello"', "multiline": '"Hello"', "number": "10", "bool": "True"}[first.kind]
        example.append(f"    form.{name}.{first.name} = {value}")
    if first is None:
        example.append(f"    form.{name}.show()")
    out.append("```python\n" + "\n".join(example) + "\n```")
    rows = [f"| `{p.name}` | {_KIND_TYPES.get(p.kind, p.kind)}"
            f"{' (' + ', '.join(p.choices) + ')' if p.choices else ''} | {_md_value(p.default)} | "
            f"{prop_doc(spec.type, p.name)} |" for p in spec.props]
    rows += [f"| `{field}` | {kind} | — | {tr(doc)} |" for field, kind, doc in FIELD_DOCS]
    out.append(f"## {tr('Properties')}\n\n{tr('Read and change them from code as attributes:')} "
               f"`form.{name}.<property>`.\n\n| {tr('Property')} | {tr('Type')} | {tr('Default')} | "
               f"{tr('Description')} |\n| --- | --- | --- | --- |\n" + "\n".join(rows))
    if spec.all_events:
        rows = [f"| `{e}` | `{name}_{e}(form, event)` | {_inline(event_doc(e, name))} |" for e in spec.all_events]
        out.append(f"## {tr('Events')}\n\n| {tr('Event')} | {tr('Handler')} | {tr('Description')} |\n"
                   "| --- | --- | --- |\n" + "\n".join(rows))
    from . import runtime

    methods = [(m, raw, kind) for m, raw, kind in _reference.class_members(runtime.ControlProxy) if kind == "method"]
    if methods:
        out.append(f"## {tr('Methods')}\n\n" + "\n".join(
            f"- `form.{name}.{m}()`: {_reference.member_doc(raw, kind)}" for m, raw, kind in methods)
            + f"\n\n{tr('See')} [form.<control>]({_reference.LINK}script:control).")
    also = [n for n in (f"pyzed.ui.{spec.type}", f"pyzed.{spec.type}")
            if _reference.lookup(n) == n]
    if also:
        links = ", ".join(f"[`{_reference.display_name(n)}`]({_reference.LINK}{n})" for n in also)
        out.append(f"## {tr('In code')}\n\n{tr('The same component in a Pyzed app written in code:')} {links}.")
    return "\n\n".join(out)


def _inline(text: str) -> str:
    return text.replace("``", "`").replace("|", "\\|")


def script_markdown(id: str, cls: type) -> str:  # noqa: A002
    """The page of ``form``, a control or ``event``: the docstring and every member."""
    out = [_reference.full_doc(cls)]
    if id == "script:form":
        out.append("```python\ndef button1_click(form, event):\n    form.title = \"Saved\"\n"
                   "    form.label1.text = form.textbox1.text\n    return form.close()\n```")
        out.append(tr("Every control is an attribute named like it: `form.button1`. `for control in form` "
                      "goes through all of them and `form[\"button1\"]` finds one by name."))
    elif id == "script:control":
        out.append(tr("Each property of the control reads and writes like an attribute: "
                      "`form.label1.text = \"Hi\"`. The page of each control lists its properties."))
    elif id == "script:event":
        out.append("```python\ndef slider1_change(form, event):\n    form.label1.text = f\"{event.value:.0f}%\"\n```")
    fields = [f for f in getattr(cls, "__dataclass_fields__", {})]
    if fields:
        docs = {"sender": tr("The control that raised the event (or the form)."),
                "name": tr("The event name: click, change..."),
                "value": tr("The event's value: the new text, checked state, key combo...")}
        out.append(f"## {tr('Properties')}\n\n" + "\n".join(f"- `event.{f}`: {docs.get(f, '')}" for f in fields))
    members = _reference.class_members(cls)
    if members:
        prefix = {"script:form": "form", "script:control": "form.button1"}.get(id, "event")
        out.append(f"## {tr('Methods and properties')}\n\n" + "\n\n".join(
            f"#### `{prefix}.{m}`\n\n```python\n{_reference.member_signature(cls, m, raw, kind)}\n```\n\n"
            f"{_reference.full_doc(raw.fget if kind == 'property' else raw) or ''}"
            for m, raw, kind in members))
    return "\n\n".join(o for o in out if o)


# -- lookup -----------------------------------------------------------------------------------------


def _lookup(symbol: str) -> Optional[str]:
    bare = symbol.strip().rstrip("()")
    if bare == "form" or bare.startswith("form.") and bare.count(".") == 1 and \
            hasattr(_runtime().FormProxy, bare.split(".")[1]):
        return "script:form"
    if bare == "event" or bare.startswith("event."):
        return "script:event"
    for spec in _components.all_components():
        if bare in (spec.label, spec.label.replace(" ", "")) and _component_class(spec.type) is None:
            return f"control:{spec.type}"
    return None


def _runtime():
    from . import runtime

    return runtime


_WORD = re.compile(r"[A-Za-z_][\w.]*")


def word_at(text: str, offset: int) -> str:
    """The dotted name around ``offset`` in ``text`` (``form.button1.text``), cut after the part under it."""
    start = offset
    while start > 0 and (text[start - 1].isalnum() or text[start - 1] in "._"):
        start -= 1
    end = offset
    while end < len(text) and (text[end].isalnum() or text[end] == "_"):
        end += 1
    return text[start:end].strip(".")


def lookup_code(symbol: str, form: Optional[Form] = None) -> Optional[str]:
    """The page about a name in a handler: ``form.button1(.text)`` is the page of that control's type."""
    parts = symbol.strip().rstrip("()").split(".")
    if form is not None and len(parts) >= 2 and parts[0] == "form":
        control = form.get(parts[1])
        if control is not None:
            cls = _component_class(control.type)
            if cls is not None:
                return _reference.lookup(cls.__name__)
            try:
                _components.get(control.type)
                return f"control:{control.type}"
            except KeyError:
                found = _reference.lookup(control.type)
                if found:
                    return found
    if parts and parts[0] in ("pz", "pyzed", "ui") or len(parts) == 1:
        found = _reference.lookup(".".join(parts))
        if found:
            return found
    return _lookup(symbol) or _reference.lookup(symbol)


_reference.register(_reference.Provider("designer", _entries, _page, _lookup))
