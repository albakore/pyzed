"""Property editors picked from a type annotation, like the details panels of Godot and Unreal.

Any annotation works: ``int | str``, ``Optional[float]``, ``list[str]``, ``dict[str, int]``,
``tuple[int, int]``, ``Literal[...]``, ``Annotated[int, pz.Range(0, 10)]``, the ``pz.Color``,
``pz.Icon`` and ``pz.Multiline`` hints, and classes (dataclasses, components or any class of the
module): those get a button that creates a new instance with its defaults.

Values are edited as Python source, so whatever the editor writes is what the class declares:

    t = parse_type("dict[str, int]")
    default_source(t)           # "{}"
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple

from .. import _core, ui
from ..icons import icon as _icon
from ..theme import Theme
from . import scene_code
from .components import Prop

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

SCALARS = {"str", "int", "float", "bool", "bytes", "Color", "Icon", "Multiline"}
_ALIASES = {"List": "list", "Sequence": "list", "MutableSequence": "list", "Iterable": "list", "Set": "set",
            "FrozenSet": "set", "frozenset": "set", "AbstractSet": "set", "MutableSet": "set", "Tuple": "tuple",
            "Dict": "dict", "Mapping": "dict", "MutableMapping": "dict", "DefaultDict": "dict",
            "OrderedDict": "dict", "Text": "str"}


@dataclass(frozen=True)
class Type:
    """A parsed annotation.

    ``kind`` is a scalar name (``str``, ``int``, ``float``, ``bool``, ``Color``, ``Icon``, ``Multiline``),
    ``choice`` (``Literal``), ``range`` (``Annotated[..., pz.Range]``), ``optional``, ``union``, ``list``,
    ``set``, ``tuple`` (fixed items), ``dict``, ``class``, ``none`` or ``any``.
    """

    kind: str
    args: Tuple["Type", ...] = ()
    name: str = ""  # the class name, or the annotation text of a scalar
    extra: Tuple[Any, ...] = ()  # choice options, or (base, min, max, step) of a range

    @property
    def label(self) -> str:
        """A short name for the type (shown in unions and in the type column)."""
        if self.kind == "optional":
            return f"{self.args[0].label}?"
        if self.kind == "union":
            return " | ".join(a.label for a in self.args)
        if self.kind in ("list", "set"):
            return f"{self.kind}[{self.args[0].label}]"
        if self.kind == "tuple":
            return f"tuple[{', '.join(a.label for a in self.args)}]"
        if self.kind == "dict":
            return f"dict[{self.args[0].label}, {self.args[1].label}]"
        if self.kind == "choice":
            return "Choice"
        if self.kind == "range":
            return self.extra[0]
        if self.kind == "none":
            return "None"
        if self.kind == "any":
            return "Any"
        return self.name or self.kind


ANY = Type("any")


def _name(node: ast.expr) -> str:
    return ast.unparse(node).replace("typing.", "")


def _type_of(node: ast.expr) -> Type:
    if isinstance(node, ast.Constant):
        if node.value is None:
            return Type("none")
        if isinstance(node.value, str):  # a forward reference: "Point"
            return parse_type(node.value)
        return ANY
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _union([_type_of(node.left), _type_of(node.right)])
    if isinstance(node, (ast.Name, ast.Attribute)):
        text = _name(node)
        last = text.rsplit(".", 1)[-1]
        last = _ALIASES.get(last, last)
        if last in ("Color", "Icon", "Multiline") or (last in SCALARS and "." not in text):
            return Type("str" if last == "bytes" else last, name=last)
        if last in ("list", "set", "dict", "tuple"):
            return Type(last, (ANY, ANY) if last == "dict" else (ANY,) if last != "tuple" else ())
        if last in ("Any", "object"):
            return ANY
        if last == "None":
            return Type("none")
        return Type("class", name=text)
    if isinstance(node, ast.Subscript):
        base = _ALIASES.get(_name(node.value).rsplit(".", 1)[-1], _name(node.value).rsplit(".", 1)[-1])
        items = list(node.slice.elts) if isinstance(node.slice, ast.Tuple) else [node.slice]
        if base == "Optional":
            return _union([_type_of(items[0]), Type("none")])
        if base == "Union":
            return _union([_type_of(i) for i in items])
        if base == "Literal":
            return Type("choice", extra=tuple(i.value for i in items if isinstance(i, ast.Constant)))
        if base == "Annotated":
            inner = _type_of(items[0])
            if scene_code.kind_of(ast.unparse(node)) == "Range":
                return Type("range", name=inner.name, extra=scene_code.range_of(ast.unparse(node)))
            return inner
        if base in ("list", "set"):
            return Type(base, (_type_of(items[0]),))
        if base == "tuple":
            if len(items) == 2 and isinstance(items[1], ast.Constant) and items[1].value is Ellipsis:
                return Type("list", (_type_of(items[0]),), name="tuple")  # tuple[int, ...] edits like a list
            return Type("tuple", tuple(_type_of(i) for i in items))
        if base == "dict":
            key = _type_of(items[0])
            return Type("dict", (key, _type_of(items[1]) if len(items) > 1 else ANY))
        if base == "ClassVar":
            return _type_of(items[0])
        return Type("class", name=_name(node.value))
    return ANY


def _union(types: Sequence[Type]) -> Type:
    flat: List[Type] = []
    for t in types:
        for part in (t.args if t.kind == "union" else (t.args[0], Type("none")) if t.kind == "optional" else (t,)):
            if part not in flat:
                flat.append(part)
    none = Type("none") in flat
    rest = [t for t in flat if t.kind != "none"]
    if not rest:
        return Type("none")
    inner = rest[0] if len(rest) == 1 else Type("union", tuple(rest))
    return Type("optional", (inner,)) if none else inner


def parse_type(annotation: str) -> Type:
    """Parses an annotation (``Any`` when it does not parse)."""
    try:
        return _type_of(ast.parse(annotation.strip() or "Any", mode="eval").body)
    except SyntaxError:
        return ANY


# -- classes ------------------------------------------------------------------------


@dataclass
class Field:
    """A field of a class that can be created from the panel."""

    name: str
    type: str = "Any"
    default: Optional[str] = None  # Python source; ``None`` when the field is required


Classes = Callable[[str], Optional[List[Field]]]


def module_classes(source: str) -> Dict[str, List[Field]]:
    """The classes of a module with annotated fields (dataclasses, components...), as ``{name: fields}``."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    out: Dict[str, List[Field]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        fields = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) \
                    and not item.target.id.startswith("_"):
                annotation = ast.unparse(item.annotation)
                if annotation.replace("typing.", "").startswith("ClassVar"):
                    continue
                value = item.value
                if isinstance(value, ast.Call) and _name(value.func).rsplit(".", 1)[-1] in ("field", "state"):
                    value = next((kw.value for kw in value.keywords if kw.arg == "default"),
                                 value.args[0] if value.args else None)
                fields.append(Field(item.target.id, annotation, ast.unparse(value) if value is not None else None))
        out[node.name] = fields
    return out


def registered_classes() -> Dict[str, List[Field]]:
    """The props of every ``pz.Component`` defined so far, by class name."""
    from .. import component

    out: Dict[str, List[Field]] = {}
    for cls in component.registered():
        fields = []
        for info in getattr(cls, "__props__", {}).values():
            annotation = info.annotation
            text = annotation if isinstance(annotation, str) else getattr(annotation, "__name__", None) \
                if isinstance(annotation, type) else str(annotation).replace("typing.", "")
            fields.append(Field(info.name, text or "Any", None if info.required else scene_code.literal(info.default)))
        out[cls.__name__] = fields
    return out


def class_resolver(*sources: Dict[str, List[Field]]) -> Classes:
    """Looks a class up by name (or by the last part of a dotted name) in ``sources``, in order."""
    def find(name: str) -> Optional[List[Field]]:
        for source in sources:
            for key in (name, name.rsplit(".", 1)[-1]):
                if key in source:
                    return source[key]
        return None
    return find


# -- values --------------------------------------------------------------------------


def default_source(t: Type) -> str:
    """The source of a new value of type ``t``: ``""``, ``0``, ``[]``, ``Point()``..."""
    kind = t.kind
    if kind in ("str", "Multiline"):
        return '""'
    if kind == "Color":
        return '"accent"'
    if kind == "Icon":
        return '"star"'
    if kind == "int":
        return "0"
    if kind == "float":
        return "0.0"
    if kind == "bool":
        return "False"
    if kind == "choice":
        return scene_code.literal(t.extra[0]) if t.extra else "None"
    if kind == "range":
        base, low, _high, _step = t.extra
        return str(int(low)) if base == "int" else repr(float(low))
    if kind in ("optional", "none", "any"):
        return "None"
    if kind == "union":
        return default_source(t.args[0])
    if kind == "list":
        return "()" if t.name == "tuple" else "[]"
    if kind == "set":
        return "set()"
    if kind == "dict":
        return "{}"
    if kind == "tuple":
        items = [default_source(a) for a in t.args]
        return "(" + ", ".join(items) + ("," if len(items) == 1 else "") + ")"
    if kind == "class":
        return f"{t.name}()"
    return "None"


def parse_value(source: Optional[str]) -> Optional[ast.expr]:
    """The expression node of a value's source (``None`` when it does not parse)."""
    if source is None:
        return None
    try:
        return ast.parse(source.strip(), mode="eval").body
    except SyntaxError:
        return None


def _literal(node: Optional[ast.expr]) -> Tuple[bool, Any]:
    if node is None:
        return False, None
    try:
        return True, ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return False, None


def matches(t: Type, node: Optional[ast.expr]) -> bool:
    """Whether the value ``node`` fits type ``t`` (used to tell which member of a union a value is)."""
    if node is None:
        return False
    kind = t.kind
    ok, value = _literal(node)
    if kind == "none":
        return ok and value is None
    if kind == "optional":
        return (ok and value is None) or matches(t.args[0], node)
    if kind == "union":
        return any(matches(a, node) for a in t.args)
    if kind in ("str", "Color", "Icon", "Multiline"):
        return ok and isinstance(value, str)
    if kind == "bool":
        return ok and isinstance(value, bool)
    if kind == "int":
        return ok and isinstance(value, int) and not isinstance(value, bool)
    if kind == "float":
        return ok and isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "range":
        return ok and isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "choice":
        return ok and value in t.extra
    if kind == "list":
        return isinstance(node, (ast.List, ast.Tuple))
    if kind == "set":
        return isinstance(node, ast.Set) or (isinstance(node, ast.Call) and _name(node.func) == "set")
    if kind == "tuple":
        return isinstance(node, ast.Tuple)
    if kind == "dict":
        return isinstance(node, ast.Dict)
    if kind == "class":
        return isinstance(node, ast.Call) and _name(node.func).rsplit(".", 1)[-1] == t.name.rsplit(".", 1)[-1]
    return True


def fits(t: Type, source: Optional[str]) -> bool:
    """Whether ``source`` is a value of type ``t``."""
    return t.kind == "any" or matches(t, parse_value(source))


def _seq(kind: str, items: Sequence[str], tuple_: bool = False) -> str:
    if kind == "set":
        return "{" + ", ".join(items) + "}" if items else "set()"
    if tuple_:
        return "(" + ", ".join(items) + ("," if len(items) == 1 else "") + ")"
    return "[" + ", ".join(items) + "]"


def _src(node: ast.expr) -> str:
    return ast.unparse(node)


# -- the editor ----------------------------------------------------------------------

ICONS = {"str": "type", "Multiline": "text", "int": "hash", "float": "percent", "range": "sliders-horizontal",
         "bool": "toggle-right", "Color": "palette", "Icon": "image", "choice": "list-checks", "union": "split",
         "list": "brackets", "set": "brackets", "tuple": "brackets", "dict": "braces", "class": "box",
         "none": "circle-off", "any": "asterisk"}
#: Each kind takes a syntax color of the theme, like the colored pins of Unreal's variables.
TOKENS = {"str": "string", "Multiline": "string", "int": "number", "float": "number", "range": "number",
          "bool": "enum", "Color": "constant", "Icon": "keyword", "choice": "enum", "union": "keyword",
          "list": "property", "set": "property", "tuple": "property", "dict": "property", "class": "type",
          "none": "comment", "any": "comment"}


def type_icon(t: Type) -> str:
    """The icon of a type (an optional type takes the icon of what it holds)."""
    return ICONS.get(t.args[0].kind if t.kind == "optional" else t.kind, "asterisk")


def type_color(t: Type, theme: Theme) -> str:
    """The color of a type's icon, taken from the theme's syntax colors."""
    token = TOKENS.get(t.args[0].kind if t.kind == "optional" else t.kind, "comment")
    style = theme.syntax.get(token)
    if isinstance(style, tuple):
        style = style[0]
    return style or theme.icon_muted


def type_badge(t: Type, theme: Theme, size: float = 14) -> Any:
    """The colored icon of a type."""
    return _icon(type_icon(t), size=size, color=type_color(t, theme))


@dataclass
class Row:
    """One line of the editor: a label (text or widget) on the left and an editor on the right."""

    label: Any
    editor: Any
    depth: int = 0
    icon: Optional[Type] = None


@dataclass
class Context:
    """What the editors need: the designer, the theme, how to find classes and a key for each editor."""

    d: Optional["Designer"]
    theme: Theme
    classes: Classes = field(default=lambda _name: None)
    drafts: Dict[str, str] = field(default_factory=dict)


Set = Callable[[str], Any]
MAX_DEPTH = 4  # how deep instances inside instances are expanded


def build(t: Type, source: Optional[str], on_change: Set, ctx: Context, key: str, depth: int = 0) -> Tuple[Any, List[Row]]:
    """The editor of a value of type ``t``: the widget shown next to its label, and the rows of its items
    (list items, dict entries, the fields of an instance), indented below it."""
    node = parse_value(source)
    th = ctx.theme
    kind = t.kind
    if kind == "optional":
        ok, value = _literal(node)
        if node is None or (ok and value is None):
            return _row([_muted("None", th), _small("plus", lambda: on_change(default_source(t.args[0])),
                                                     "Set a value", th)]), []
        inner, rows = build(t.args[0], source, on_change, ctx, key, depth)
        return _row([_fill(inner), _small("x", lambda: on_change("None"), "Set to None", th)]), rows
    if kind == "union":
        current = next((a for a in t.args if matches(a, node)), None)
        labels = [a.label for a in t.args]

        def switch(label: str) -> None:
            picked = t.args[labels.index(label)]
            if picked != current:
                on_change(default_source(picked))

        picker = _core.container(ui.select(labels, current.label if current else None, switch, size="sm",
                                           placeholder="type", theme=th), width=72)
        if current is None:
            return _row([picker, _fill(_expression(source, on_change, ctx, key))]), []
        inner, rows = build(current, source, on_change, ctx, key, depth)
        return _row([picker, _fill(inner)]), rows
    if kind in ("list", "set", "tuple"):
        return _sequence(t, node, source, on_change, ctx, key, depth)
    if kind == "dict":
        return _mapping(t, node, source, on_change, ctx, key, depth)
    if kind == "class":
        return _instance(t, node, source, on_change, ctx, key, depth)
    if kind in ("none", "any"):
        return _expression(source, on_change, ctx, key), []
    return _scalar(t, node, source, on_change, ctx, key), []


def _scalar(t: Type, node: Optional[ast.expr], source: Optional[str], on_change: Set, ctx: Context, key: str) -> Any:
    ok, value = _literal(node)
    if not ok or not matches(t, node):  # an expression (or a value of another type): edit it as Python
        return _row([_fill(_expression(source, on_change, ctx, key)),
                     _small("rotate-ccw", lambda: on_change(default_source(t)), f"Reset to a {t.label}", ctx.theme)])
    th = ctx.theme
    kind = t.kind
    if kind == "range":
        base, low, high, step = t.extra
        prop = Prop(key, "number", value, min=low, max=high, step=0.1 if base == "float" and step == 1 else step)
        cast: Callable[[Any], Any] = int if base == "int" else float
    elif kind in ("int", "float"):
        prop = Prop(key, "number", value, step=1.0 if kind == "int" else 0.1)
        cast = int if kind == "int" else float
    elif kind == "bool":
        prop, cast = Prop(key, "bool", value), bool
    elif kind == "choice":
        prop, cast = Prop(key, "choice", value, choices=tuple(str(c) for c in t.extra)), str
        options = {str(c): c for c in t.extra}
        return _choice(prop, value, lambda v: on_change(scene_code.literal(options.get(v, v))), th)
    else:
        prop = Prop(key, {"Color": "color", "Icon": "icon", "Multiline": "multiline"}.get(kind, "text"), value)
        cast = str
    return _editor(ctx, prop, value, lambda v: on_change(scene_code.literal(cast(v))), key)


def _choice(prop: Prop, value: Any, on_change: Callable[[str], Any], th: Theme) -> Any:
    return ui.select(list(prop.choices), str(value), on_change, width="fill", size="sm", theme=th)


def _editor(ctx: Context, prop: Prop, value: Any, on_change: Callable[[Any], Any], key: str) -> Any:
    if ctx.d is not None:
        from .panels import editor_for

        return editor_for(ctx.d, prop, value, on_change, f"typed:{key}", ctx.theme)
    th = ctx.theme
    if prop.kind == "bool":
        return _core.container(ui.switch(bool(value), on_change, theme=th), width="fill", align_x="end")
    if prop.kind == "number":
        return ui.number_field(float(value or 0), on_change, min=prop.min, max=prop.max, step=prop.step,
                               width="fill", theme=th)
    return ui.input("" if value is None else str(value), on_change, size="sm", theme=th)


def _sequence(t: Type, node: Optional[ast.expr], source: Optional[str], on_change: Set, ctx: Context, key: str,
              depth: int) -> Tuple[Any, List[Row]]:
    th = ctx.theme
    is_tuple = t.kind == "tuple" or t.name == "tuple"
    if not matches(t, node) and not (t.kind == "list" and isinstance(node, ast.Tuple)):
        return _reset(t, source, on_change, ctx, key), []
    assert node is not None
    elts = list(node.elts) if isinstance(node, (ast.List, ast.Tuple, ast.Set)) else []
    items = [_src(e) for e in elts]
    fixed = t.kind == "tuple"

    def write(new: List[str]) -> None:
        on_change(_seq(t.kind, new, is_tuple))

    rows: List[Row] = []
    for i, item in enumerate(items):
        item_type = t.args[i] if fixed and i < len(t.args) else (t.args[0] if t.args else ANY)

        def set_item(text: str, i: int = i) -> None:
            new = list(items)
            new[i] = text
            write(new)

        def remove(i: int = i) -> None:
            write(items[:i] + items[i + 1:])

        editor, below = build(item_type, item, set_item, ctx, f"{key}.{i}", depth + 1)
        if not fixed:
            editor = _row([_fill(editor), _small("trash-2", remove, "Remove", th)])
        rows.append(Row(f"[{i}]", editor, depth + 1, item_type))
        rows.extend(below)
    if fixed:
        summary = _muted(f"{len(items)} items", th)
        return summary, rows
    item_type = t.args[0] if t.args else ANY
    head = _row([_muted(f"{len(items)} item{'s' if len(items) != 1 else ''}", th),
                 _small("plus", lambda: write([*items, default_source(item_type)]), "Add an item", th),
                 _small("trash-2", lambda: write([]), "Remove all", th, disabled=not items)])
    return head, rows


def _new_key(t: Type, taken: Sequence[Any]) -> str:
    if t.kind == "int":
        n = 0
        while n in taken:
            n += 1
        return str(n)
    if t.kind in ("str", "any"):
        n, name = 1, "key"
        while name in taken:
            n += 1
            name = f"key{n}"
        return scene_code.literal(name)
    return default_source(t)


def _mapping(t: Type, node: Optional[ast.expr], source: Optional[str], on_change: Set, ctx: Context, key: str,
             depth: int) -> Tuple[Any, List[Row]]:
    th = ctx.theme
    if not isinstance(node, ast.Dict):
        return _reset(t, source, on_change, ctx, key), []
    key_type, value_type = (t.args + (ANY, ANY))[:2]
    pairs = [(_src(k) if k is not None else "None", _src(v)) for k, v in zip(node.keys, node.values)]

    def write(new: List[Tuple[str, str]]) -> None:
        on_change("{" + ", ".join(f"{k}: {v}" for k, v in new) + "}")

    rows: List[Row] = []
    for i, (k, v) in enumerate(pairs):
        def set_key(text: str, i: int = i) -> None:
            new = list(pairs)
            new[i] = (text, new[i][1])
            write(new)

        def set_value(text: str, i: int = i) -> None:
            new = list(pairs)
            new[i] = (new[i][0], text)
            write(new)

        def remove(i: int = i) -> None:
            write(pairs[:i] + pairs[i + 1:])

        key_editor, _ = build(key_type, k, set_key, ctx, f"{key}.k{i}", depth + 1)
        editor, below = build(value_type, v, set_value, ctx, f"{key}.v{i}", depth + 1)
        rows.append(Row(key_editor, _row([_fill(editor), _small("trash-2", remove, "Remove", th)]), depth + 1,
                        value_type))
        rows.extend(below)
    taken = [_literal(k)[1] for k in node.keys if k is not None]
    head = _row([_muted(f"{len(pairs)} entr{'ies' if len(pairs) != 1 else 'y'}", th),
                 _small("plus", lambda: write([*pairs, (_new_key(key_type, taken), default_source(value_type))]),
                        "Add an entry", th),
                 _small("trash-2", lambda: write([]), "Remove all", th, disabled=not pairs)])
    return head, rows


def _instance(t: Type, node: Optional[ast.expr], source: Optional[str], on_change: Set, ctx: Context, key: str,
              depth: int) -> Tuple[Any, List[Row]]:
    th = ctx.theme
    short = t.name.rsplit(".", 1)[-1]
    new = _button(f"New {short}", "plus", lambda: on_change(f"{t.name}()"), th)
    ok, value = _literal(node)
    if node is None or (ok and value is None):  # empty: create one with its defaults
        return _row([_muted("None", th), new]), []
    if not matches(t, node):
        return _row([_fill(_expression(source, on_change, ctx, key)), new]), []
    assert isinstance(node, ast.Call)
    fields = ctx.classes(t.name) if depth < MAX_DEPTH else None  # a class that holds itself stops here
    head = _row([_muted(f"{short}()", th, mono=True),
                 _small("rotate-ccw", lambda: on_change(f"{t.name}()"), "New instance with its defaults", th),
                 _small("x", lambda: on_change("None"), "Empty (None)", th)])
    if fields is None:  # an unknown class: edit its arguments as Python
        return _row([_fill(_expression(source, on_change, ctx, key)), _small(
            "x", lambda: on_change("None"), "Empty (None)", th)]), []
    given: Dict[str, str] = {}
    for f, arg in zip(fields, node.args):
        given[f.name] = _src(arg)
    for kw in node.keywords:
        if kw.arg is not None:
            given[kw.arg] = _src(kw.value)
    func = _src(node.func)

    def write(values: Dict[str, str]) -> None:
        on_change(f"{func}(" + ", ".join(f"{k}={v}" for k, v in values.items()) + ")")

    rows: List[Row] = []
    for f in fields:
        ft = parse_type(f.type)

        def set_field(text: str, name: str = f.name, default: Optional[str] = f.default) -> None:
            values = dict(given)
            if default is not None and text == default:
                values.pop(name, None)  # back to its default: leave it out of the call
            else:
                values[name] = text
            write(values)

        current = given.get(f.name, f.default if f.default is not None else default_source(ft))
        editor, below = build(ft, current, set_field, ctx, f"{key}.{f.name}", depth + 1)
        rows.append(Row(f.name, editor, depth + 1, ft))
        rows.extend(below)
    return head, rows


def _reset(t: Type, source: Optional[str], on_change: Set, ctx: Context, key: str) -> Any:
    return _row([_fill(_expression(source, on_change, ctx, key)),
                 _small("rotate-ccw", lambda: on_change(default_source(t)), f"Reset to an empty {t.label}",
                        ctx.theme)])


def _expression(source: Optional[str], on_change: Set, ctx: Context, key: str) -> Any:
    """A Python expression; it is written once it parses (the text typed so far is kept meanwhile)."""
    text = ctx.drafts.get(key, source or "")

    def change(value: str) -> None:
        ctx.drafts[key] = value
        if parse_value(value) is not None:
            ctx.drafts.pop(key, None)
            on_change(value)

    return ui.input(text, change, mono=True, size="sm", placeholder="a Python expression", theme=ctx.theme)


# -- small widgets -------------------------------------------------------------------


def _row(items: List[Any]) -> Any:
    return _core.row(items, spacing=4, align="center", width="fill")


def _fill(widget: Any) -> Any:
    return _core.container(widget, width="fill")


def _muted(text: str, th: Theme, mono: bool = False) -> Any:
    return _core.container(_core.text(text, size=12.5, color=th.text_muted, font="mono" if mono else None,
                                      wrap=False), width="fill", clip=True)


def _small(name: str, action: Callable[[], Any], tip: str, th: Theme, disabled: bool = False) -> Any:
    return ui.icon_button(name, action, size="xs", tooltip=tip, disabled=disabled, theme=th)


def _button(label: str, name: str, action: Callable[[], Any], th: Theme) -> Any:
    return ui.button(label, action, icon=name, variant="ghost", size="sm", theme=th)


def rows_view(rows: Sequence[Row], th: Theme, label_width: float, indent: float = 12.0, gap: float = 6) -> Any:
    """Lays out item rows like a details panel: labels indented by depth, editors in one column."""
    out = []
    for r in rows:
        pad = 8 + r.depth * indent  # items start under their property's name
        label = r.label
        if isinstance(label, str):
            label = _core.text(label, size=12.5, color=th.text_muted, wrap=False, font="mono")
        parts = [type_badge(r.icon, th, 12)] if r.icon is not None else []
        left = _core.container(_core.row([*parts, _core.container(label, width="fill", clip=True)], spacing=4,
                                         align="center"), width=label_width, padding=(0, 0, 0, pad), clip=True)
        out.append(_core.row([left, _core.container(r.editor, width="fill")], spacing=8, align="center",
                             width="fill"))
    return _core.column(out, spacing=gap, width="fill")
