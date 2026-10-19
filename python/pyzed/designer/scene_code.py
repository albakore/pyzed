"""The code of a component designed visually: one ``pz.Component`` class, read and edited with ``ast``.

The class in the ``.py`` file is the source of truth for what the component declares,
so writing it by hand and editing it in the designer are the same thing::

    class Rating(SceneComponent, scene="rating.pzcomp"):
        \"\"\"Stars the user can click.\"\"\"

        value: int = 0                    # public property (a prop)
        hover: int = pz.state(0)          # private property (state)
        events = {"change": "A star was picked."}

        def star1_click(self, event):     # a control's event handler
            return self.emit("change", 1)

``members`` / ``custom_events`` / ``methods`` read the class; ``set_members``,
``set_events`` and the method helpers rewrite only the lines they own, so imports,
helpers and comments elsewhere in the file are never touched.
"""

from __future__ import annotations

import ast
import keyword
import re
import textwrap
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: Types offered for properties; each maps to a property editor in the designer.
TYPES = ("str", "int", "float", "bool", "list", "dict", "Any")

#: Class attributes that configure the component and are not properties.
RESERVED = {"events", "label", "icon", "category", "size", "designer", "type_name", "description", "scene"}

#: Methods every component can override, with the stub the designer writes for them.
LIFECYCLE = {
    "setup": ("self", "Runs once before the first render (props are already set)."),
    "on_mount": ("self", "Runs after the first render; may return a Command."),
    "on_unmount": ("self", "Runs when the component stops being rendered."),
}

INDENT = "    "


@dataclass
class Member:
    """A property of the component: public (a prop the parent passes) or private (state)."""

    name: str
    type: str = "str"
    default: Any = None
    public: bool = True
    description: str = ""
    #: The default as Python source when it is not a literal (``list(range(3))``).
    source: Optional[str] = None

    @property
    def default_source(self) -> str:
        """The default as Python source: ``source`` if set, ``""`` for a ``str`` without a default, else the
        default as a literal."""
        if self.source is not None:
            return self.source
        if self.default is None and self.type in ("str",):
            return '""'
        return literal(self.default)

    def statement(self) -> str:
        """The line that declares this member in the class body."""
        annotation = self.type or "Any"
        if self.public:
            line = f"{self.name}: {annotation} = {self.default_source}"
        else:
            doc = f", doc={literal(self.description)}" if self.description else ""
            line = f"{self.name}: {annotation} = pz.state({self.default_source}{doc})"
        if self.public and self.description:
            line += f"  # {self.description}"
        return line


@dataclass
class ClassInfo:
    """What ``read`` found in the class: its members, events, methods and docstring."""

    name: str
    members: List[Member] = field(default_factory=list)
    events: Dict[str, str] = field(default_factory=dict)
    methods: List[str] = field(default_factory=list)
    doc: str = ""


def literal(value: Any) -> str:
    """Python source for a literal, with double-quoted strings (the style of generated code)."""
    if isinstance(value, str):
        text = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{text}"'
    if isinstance(value, list):
        return "[" + ", ".join(literal(v) for v in value) + "]"
    if isinstance(value, tuple):
        return "(" + ", ".join(literal(v) for v in value) + ("," if len(value) == 1 else "") + ")"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{literal(k)}: {literal(v)}" for k, v in value.items()) + "}"
    return repr(value)


def class_identifier(text: str) -> str:
    """Turns any text into a CamelCase class name (``"star rating"`` -> ``"StarRating"``)."""
    words = [w for w in re.split(r"\W+|_", str(text)) if w]
    name = "".join(w[:1].upper() + w[1:] for w in words)
    if not name:
        return "Component1"
    if name[0].isdigit():
        name = "C" + name
    return name


def member_identifier(text: str) -> str:
    """Turns any text into a lowercase snake_case member name (``"Max value"`` -> ``"max_value"``); ``""`` for
    empty text, and a keyword gets a trailing underscore."""
    name = re.sub(r"\W+", "_", str(text).strip()).strip("_").lower()
    if not name:
        return ""
    if name[0].isdigit():
        name = "_" + name
    return name + "_" if keyword.iskeyword(name) else name


# -- reading ---------------------------------------------------------------------


def _parse(source: str) -> Optional[ast.Module]:
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def find_class(source: str, name: Optional[str] = None) -> Optional[ast.ClassDef]:
    """The top-level class ``name`` (or the first class when ``name`` is None)."""
    tree = _parse(source)
    if tree is None:
        return None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and (name is None or node.name == name):
            return node
    return None


def _is_state_call(node: Optional[ast.expr]) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (isinstance(func, ast.Attribute) and func.attr == "state") or (isinstance(func, ast.Name)
                                                                        and func.id == "state")


def _literal(node: Optional[ast.expr], source: str) -> Tuple[Any, Optional[str]]:
    if node is None:
        return None, None
    try:
        return ast.literal_eval(node), None
    except (ValueError, SyntaxError, TypeError):
        return None, ast.get_source_segment(source, node)


def _comment(source: str, node: ast.stmt) -> str:
    line = source.splitlines()[(node.end_lineno or node.lineno) - 1]
    end = node.end_col_offset or 0
    rest = line[end:].strip()
    return rest[1:].strip() if rest.startswith("#") else ""


def _member(node: ast.stmt, source: str) -> Optional[Member]:
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        name = node.target.id
        annotation = ast.get_source_segment(source, node.annotation) or "Any"
        value = node.value
    elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
            and _is_state_call(node.value):
        name, annotation, value = node.targets[0].id, "Any", node.value
    else:
        return None
    if name.startswith("_") or name in RESERVED:
        return None
    if annotation.replace("typing.", "").startswith("ClassVar"):
        return None
    if _is_state_call(value):
        assert isinstance(value, ast.Call)
        default, src = _literal(value.args[0] if value.args else None, source)
        doc = next((kw.value for kw in value.keywords if kw.arg == "doc"), None)
        description = doc.value if isinstance(doc, ast.Constant) and isinstance(doc.value, str) else ""
        return Member(name, annotation, default, False, description, src)
    default, src = _literal(value, source)
    return Member(name, annotation, default, True, _comment(source, node), src)


def _events_node(cls: ast.ClassDef) -> Optional[ast.stmt]:
    for node in cls.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(
            node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == "events" for t in targets):
            return node
    return None


def read(source: str, name: Optional[str] = None) -> Optional[ClassInfo]:
    """Parses the component class (``None`` if the source does not parse or has no such class)."""
    cls = find_class(source, name)
    if cls is None:
        return None
    info = ClassInfo(cls.name, doc=ast.get_docstring(cls) or "")
    for node in cls.body:
        member = _member(node, source)
        if member is not None:
            info.members.append(member)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info.methods.append(node.name)
    events = _events_node(cls)
    if events is not None and events.value is not None:  # type: ignore[union-attr]
        value, _ = _literal(events.value, source)  # type: ignore[union-attr]
        if isinstance(value, dict):
            info.events = {str(k): str(v) for k, v in value.items()}
        elif isinstance(value, (list, tuple)):
            info.events = {str(v): "" for v in value}
    return info


# -- rewriting ---------------------------------------------------------------------


def _lines(source: str) -> List[str]:
    return source.splitlines(keepends=True)


def _body_insert_line(cls: ast.ClassDef) -> int:
    """The 0-based line where declarations go: after the docstring, or at the start of the body."""
    first = cls.body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return first.end_lineno or first.lineno
    return first.lineno - 1


def _replace_statements(source: str, cls_name: Optional[str], picked: Sequence[ast.stmt], block: List[str],
                        *, anchor: Optional[int] = None) -> str:
    """Removes ``picked`` statements and puts ``block`` (lines without indentation) where the first was."""
    cls = find_class(source, cls_name)
    assert cls is not None
    lines = _lines(source)
    if picked:
        where = picked[0].lineno - 1
    else:
        where = anchor if anchor is not None else _body_insert_line(cls)
    drop = set()
    for node in picked:
        drop.update(range(node.lineno - 1, node.end_lineno or node.lineno))
    kept_before = [line for i, line in enumerate(lines[:where]) if i not in drop]
    kept_after = [line for i, line in enumerate(lines[where:], start=where) if i not in drop]
    new = [f"{INDENT}{line}\n" if line else "\n" for line in block]
    if not picked and new and anchor is None:
        # a fresh block: separate it from the docstring above and the code below
        if kept_before and kept_before[-1].strip():
            new.insert(0, "\n")
        if kept_after and kept_after[0].strip():
            new.append("\n")
    text = "".join(kept_before + new + kept_after)
    return _ensure_body(text, cls_name)


def _ensure_body(source: str, cls_name: Optional[str]) -> str:
    """Adds ``pass`` to a class left with an empty body (so the file still parses)."""
    if _parse(source) is not None:
        return source
    lines = _lines(source)
    for i, line in enumerate(lines):
        if re.match(rf"class\s+{re.escape(cls_name or '')}\w*\b.*:\s*$", line):
            lines.insert(i + 1, f"{INDENT}pass\n")
            return "".join(lines)
    return source


def set_members(source: str, members: Sequence[Member], cls_name: Optional[str] = None) -> str:
    """Rewrites the property declarations of the class to ``members`` (in that order)."""
    cls = find_class(source, cls_name)
    if cls is None:
        raise SyntaxError(f"no class {cls_name or ''} to edit in the component code".replace("  ", " "))
    picked = [node for node in cls.body if _member(node, source) is not None]
    block = [m.statement() for m in members]
    source = _replace_statements(source, cls.name, picked, block)
    if any(not m.public or "pz." in m.type for m in members):
        source = ensure_import(source)
    wanted = [name for name in ("Annotated", "Literal") if any(m.type.startswith(f"{name}[") for m in members)]
    if wanted:
        source = ensure_typing(source, wanted)
    return source


def ensure_typing(source: str, names: Sequence[str]) -> str:
    """Makes sure ``from typing import ...`` names ``names`` (``Literal`` and ``Annotated`` hints use it)."""
    tree = _parse(source)
    if tree is None:
        return source
    node = next((n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == "typing"), None)
    lines = _lines(source)
    if node is not None:
        have = [a.name if not a.asname else f"{a.name} as {a.asname}" for a in node.names]
        missing = [n for n in names if n not in {a.name for a in node.names}]
        if not missing or node.lineno != node.end_lineno:
            return source
        lines[node.lineno - 1] = f"from typing import {', '.join(sorted([*have, *missing]))}\n"
        return "".join(lines)
    line = f"from typing import {', '.join(sorted(names))}\n"
    first = next((n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))
                  and getattr(n, "module", None) != "__future__"), None)
    if first is not None:  # the standard library goes first, then a blank line
        lines[first.lineno - 1:first.lineno - 1] = [line, "\n"]
    else:
        doc = tree.body[0] if tree.body and isinstance(tree.body[0], ast.Expr) else None
        lines.insert(doc.end_lineno if doc is not None and doc.end_lineno else 0, line)
    return "".join(lines)


# -- property kinds (like Godot's export hints) --------------------------------------

#: What the type drop-down offers: plain types and the hints that pick an editor.
KINDS = ("str", "int", "float", "bool", "Color", "Icon", "Multiline", "Choice", "Range", "list", "dict", "Any")


def kind_of(type_: str) -> str:
    """The kind of a property from its annotation (``pz.Color`` is ``Color``, ``Literal[...]`` is ``Choice``)."""
    text = type_.replace("typing.", "").strip()
    if text.startswith("Literal["):
        return "Choice"
    if text.startswith("Annotated[") and "Range(" in text:
        return "Range"
    last = text.rsplit(".", 1)[-1]
    if last in ("Color", "Icon", "Multiline"):
        return last
    return text


def choices_of(type_: str) -> List[str]:
    """The options of a ``Literal[...]`` annotation."""
    try:
        node = ast.parse(type_.replace("typing.", ""), mode="eval").body
    except SyntaxError:
        return []
    if not isinstance(node, ast.Subscript):
        return []
    items = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]  # type: ignore[attr-defined]
    return [str(i.value) for i in items if isinstance(i, ast.Constant)]


def choice_type(options: Sequence[str]) -> str:
    """Returns the ``Literal[...]`` annotation of a choice between ``options`` (``str`` when there are
    none)."""
    return f"Literal[{', '.join(literal(str(o)) for o in options)}]" if options else "str"


def range_of(type_: str) -> Tuple[str, float, float, float]:
    """``(base type, min, max, step)`` of an ``Annotated[int, pz.Range(0, 10)]`` annotation."""
    try:
        node = ast.parse(type_.replace("typing.", ""), mode="eval").body
    except SyntaxError:
        return ("int", 0, 100, 1)
    base, values = "int", [0.0, 100.0, 1.0]
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Tuple):
        first, *rest = node.slice.elts
        base = ast.unparse(first)
        for extra in rest:
            if isinstance(extra, ast.Call):
                args = [a.value for a in extra.args if isinstance(a, ast.Constant)]
                args += [k.value.value for k in extra.keywords if isinstance(k.value, ast.Constant)]
                values[:len(args)] = [float(a) for a in args[:3]]
    return (base, values[0], values[1], values[2])


def range_type(base: str, low: float, high: float, step: float = 1) -> str:
    """Returns the ``Annotated[base, pz.Range(low, high[, step])]`` annotation of a bounded number (``step``
    is left out when it is 1)."""
    def num(v: float) -> str:
        return str(int(v)) if float(v).is_integer() and base == "int" else repr(float(v))
    tail = f", {num(step)}" if step != 1 else ""
    return f"Annotated[{base}, pz.Range({num(low)}, {num(high)}{tail})]"


def type_for(kind: str, previous: str = "") -> str:
    """The annotation written for a kind picked in the type drop-down."""
    if kind == "Color":
        return "pz.Color"
    if kind == "Icon":
        return "pz.Icon"
    if kind == "Multiline":
        return "pz.Multiline"
    if kind == "Choice":
        return previous if kind_of(previous) == "Choice" else choice_type(["first", "second"])
    if kind == "Range":
        return previous if kind_of(previous) == "Range" else range_type("int", 0, 100)
    return kind


def set_events(source: str, events: Dict[str, str], cls_name: Optional[str] = None) -> str:
    """Rewrites (or adds, or removes) the ``events = {...}`` declaration."""
    cls = find_class(source, cls_name)
    if cls is None:
        raise SyntaxError("no class to edit in the component code")
    node = _events_node(cls)
    block: List[str] = []
    if events:
        if len(events) == 1:
            (name, doc), = events.items()
            block = [f"events = {{{literal(name)}: {literal(doc)}}}"]
        else:
            block = ["events = {", *[f"{INDENT}{literal(k)}: {literal(v)}," for k, v in events.items()], "}"]
    anchor = None
    if node is None:
        members = [n for n in cls.body if _member(n, source) is not None]
        anchor = (members[-1].end_lineno or members[-1].lineno) if members else None
    return _replace_statements(source, cls.name, [node] if node is not None else [], block, anchor=anchor)


def ensure_import(source: str) -> str:
    """Makes sure ``pyzed`` is imported as ``pz`` (private members use ``pz.state``)."""
    if re.search(r"^import pyzed as pz\b", source, re.M):
        return source
    lines = _lines(source)
    tree = _parse(source)
    where = 0
    if tree is not None:
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "pyzed":
                where = node.lineno - 1  # ``import pyzed`` goes before ``from pyzed... import``
                break
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and where == 0 \
                    and node is tree.body[0]:
                where = node.end_lineno or node.lineno
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                where = node.end_lineno or node.lineno
    lines.insert(where, "import pyzed as pz\n")
    return "".join(lines)


# -- methods -------------------------------------------------------------------------


def _method(cls: ast.ClassDef, name: str) -> Optional[ast.stmt]:
    for node in cls.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def find_method(source: str, name: str, cls_name: Optional[str] = None) -> Optional[Tuple[int, int]]:
    """The ``(first, last)`` 1-based lines of method ``name`` (decorators included)."""
    cls = find_class(source, cls_name)
    node = _method(cls, name) if cls is not None else None
    if node is None:
        return None
    first = min([node.lineno] + [d.lineno for d in node.decorator_list])  # type: ignore[attr-defined]
    return first, node.end_lineno or node.lineno


def get_method(source: str, name: str, cls_name: Optional[str] = None) -> Optional[str]:
    """The source of a method, dedented to column 0 (as the designer's editor shows it)."""
    span = find_method(source, name, cls_name)
    if span is None:
        return None
    lines = _lines(source)[span[0] - 1: span[1]]
    return textwrap.dedent("".join(lines))


def method_stub(name: str, doc: str = "", args: str = "self, event") -> str:
    """Returns the source of an empty method ``name(args)`` at column 0, with ``doc`` as its docstring."""
    return f'def {name}({args}):\n{INDENT}"""{doc or "Event handler."}"""\n{INDENT}pass\n'


def _indent(code: str) -> str:
    return "".join(f"{INDENT}{line}" if line.strip() else line for line in _lines(code))


def ensure_method(source: str, name: str, doc: str = "", args: str = "self, event",
                  cls_name: Optional[str] = None) -> Tuple[str, bool]:
    """Adds a stub method at the end of the class if missing; returns ``(source, created)``."""
    cls = find_class(source, cls_name)
    if cls is None:
        raise SyntaxError("no class to add the method to in the component code")
    if _method(cls, name) is not None:
        return source, False
    lines = _lines(source)
    end = cls.end_lineno or cls.lineno
    body = [n for n in cls.body]
    only_pass = len(body) == 1 and isinstance(body[0], ast.Pass)
    stub = _indent(method_stub(name, doc, args))
    if only_pass:
        lines[body[0].lineno - 1: body[0].end_lineno] = [stub]
    else:
        if end - 1 < len(lines) and not lines[end - 1].endswith("\n"):
            lines[end - 1] += "\n"
        lines.insert(end, "\n" + stub)
    return "".join(lines), True


def replace_method(source: str, name: str, new_code: str, cls_name: Optional[str] = None) -> str:
    """Replaces method ``name`` with ``new_code`` (written at column 0, as the editor shows it).

    Raises ``SyntaxError`` and changes nothing unless ``new_code`` is exactly that one
    function, so a line typed without indentation never escapes into the class body.
    """
    new_code = textwrap.dedent(new_code).rstrip() + "\n"
    tree = ast.parse(new_code)
    body = tree.body
    if len(body) != 1 or not isinstance(body[0], (ast.FunctionDef, ast.AsyncFunctionDef)) or body[0].name != name:
        line = body[1].lineno if len(body) > 1 else 1
        raise SyntaxError(f"keep the code indented inside def {name}(...)", ("<method>", line, 1, ""))
    span = find_method(source, name, cls_name)
    if span is None:
        source, _ = ensure_method(source, name, cls_name=cls_name)
        span = find_method(source, name, cls_name)
        assert span is not None
    lines = _lines(source)
    return "".join(lines[: span[0] - 1]) + _indent(new_code) + "".join(lines[span[1]:])


def remove_method(source: str, name: str, cls_name: Optional[str] = None) -> str:
    """Removes method ``name`` (and the blank lines above it) from the class; returns the new source.

    The class keeps a ``pass`` if it would be left empty; the source is unchanged if the method is not there.
    """
    span = find_method(source, name, cls_name)
    if span is None:
        return source
    lines = _lines(source)
    first, last = span[0] - 1, span[1]
    while first > 0 and not lines[first - 1].strip():
        first -= 1
    return _ensure_body("".join(lines[:first]) + "".join(lines[last:]), cls_name)


def rename_method(source: str, old: str, new: str, cls_name: Optional[str] = None) -> str:
    """Renames the definition of method ``old`` to ``new`` (calls are left alone); does nothing if ``old`` is
    missing or ``new`` is taken."""
    span = find_method(source, old, cls_name)
    if span is None or find_method(source, new, cls_name) is not None:
        return source
    lines = _lines(source)
    for i in range(span[0] - 1, span[1]):
        if lines[i].lstrip().startswith(("def ", "async def ")):
            lines[i] = lines[i].replace(f"def {old}(", f"def {new}(", 1)
            break
    return "".join(lines)


def rename_class(source: str, old: str, new: str) -> str:
    """Renames class ``old`` to ``new`` in its ``class`` line; does nothing if ``old`` is missing or ``new``
    exists."""
    cls = find_class(source, old)
    if cls is None or find_class(source, new) is not None:
        return source
    lines = _lines(source)
    i = cls.lineno - 1
    lines[i] = re.sub(rf"\bclass\s+{re.escape(old)}\b", f"class {new}", lines[i], count=1)
    return "".join(lines)


def set_scene_file(source: str, scene_file: str, cls_name: Optional[str] = None) -> str:
    """Points the class's ``scene=`` argument at ``scene_file`` (after a "Save as")."""
    cls = find_class(source, cls_name)
    keyword_ = next((k for k in cls.keywords if k.arg == "scene"), None) if cls is not None else None
    if keyword_ is None or not isinstance(keyword_.value, ast.Constant) or keyword_.value.value == scene_file:
        return source
    lines = _lines(source)
    node = keyword_.value
    if node.lineno != node.end_lineno:
        return source
    i = node.lineno - 1
    line = lines[i].encode()  # ast offsets are in bytes
    lines[i] = (line[:node.col_offset] + literal(scene_file).encode() + line[node.end_col_offset:]).decode()
    return "".join(lines)


def _is_import_component(node: ast.stmt) -> bool:
    return isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) \
        and isinstance(node.value.func, ast.Name) and node.value.func.id == "import_component"


def base_of(source: str, cls_name: Optional[str] = None) -> Optional[Tuple[str, str]]:
    """``(name, scene file)`` of the designed component the class inherits from, or ``None``."""
    tree = _parse(source)
    cls = find_class(source, cls_name)
    if tree is None or cls is None or not cls.bases or not isinstance(cls.bases[0], ast.Name):
        return None
    for node in tree.body:
        if _is_import_component(node) and any(isinstance(t, ast.Name) and t.id == cls.bases[0].id
                                              for t in node.targets):  # type: ignore[attr-defined]
            args = node.value.args  # type: ignore[attr-defined]
            if args and isinstance(args[0], ast.Constant) and isinstance(args[0].value, str):
                return cls.bases[0].id, args[0].value
    return None


def set_base(source: str, base_name: Optional[str], base_file: Optional[str], cls_name: Optional[str] = None) -> str:
    """Makes the class inherit from the designed component in ``base_file`` (``None``: from ``SceneComponent``).

    Writes ``Base = import_component("base.pzcomp")`` above the class and puts ``Base``
    first in its bases, fixing the ``from pyzed.designer import ...`` line.
    """
    if base_of(source, cls_name) == ((base_name, base_file) if base_name and base_file else None):
        return source
    tree = _parse(source)
    if tree is None:
        raise SyntaxError("the class does not parse")
    lines = _lines(source)
    # drop the old import_component lines (and the blank lines after them)
    for node in reversed([n for n in tree.body if _is_import_component(n)]):
        end = node.end_lineno or node.lineno
        while end < len(lines) and not lines[end].strip():
            end += 1
        del lines[node.lineno - 1:end]
    source = "".join(lines)
    cls = find_class(source, cls_name)
    if cls is None:
        return source
    lines = _lines(source)
    first = cls.bases[0] if cls.bases else None
    parent = base_name if base_name and base_file else "SceneComponent"
    i = cls.lineno - 1
    if first is not None and first.lineno == first.end_lineno == cls.lineno:
        line = lines[i].encode()
        lines[i] = (line[:first.col_offset] + parent.encode() + line[first.end_col_offset:]).decode()
    if base_name and base_file:
        lines[i:i] = [f"{base_name} = import_component({literal(base_file)})\n", "\n", "\n"]
    return _designer_imports("".join(lines))


def _designer_imports(source: str) -> str:
    """Keeps ``from pyzed.designer import`` naming exactly the helpers the module uses."""
    tree = _parse(source)
    if tree is None:
        return source
    node = next((n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == "pyzed.designer"), None)
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    wanted = [name for name in ("SceneComponent", "import_component") if name in used]
    lines = _lines(source)
    if node is None:
        if wanted:
            where = next((n.end_lineno or n.lineno for n in reversed(tree.body)
                          if isinstance(n, (ast.Import, ast.ImportFrom))), 0)
            lines.insert(where, f"from pyzed.designer import {', '.join(wanted)}\n")
        return "".join(lines)
    others = [a for a in node.names if a.name not in ("SceneComponent", "import_component")]
    names = [*wanted, *(f"{a.name} as {a.asname}" if a.asname else a.name for a in others)]
    if node.lineno != node.end_lineno:
        return source  # a wrapped import: leave it to the user
    lines[node.lineno - 1:node.end_lineno] = [f"from pyzed.designer import {', '.join(names)}\n"] if names else []
    return "".join(lines)


def set_docstring(source: str, doc: str, cls_name: Optional[str] = None) -> str:
    """Sets (or replaces, or with an empty ``doc`` removes) the docstring of the class; returns the new
    source."""
    cls = find_class(source, cls_name)
    if cls is None:
        return source
    lines = _lines(source)
    first = cls.body[0]
    quoted = f'{INDENT}"""{doc.strip()}"""\n' if doc.strip() else ""
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        lines[first.lineno - 1: first.end_lineno] = [quoted]
    elif quoted:
        lines.insert(first.lineno - 1, quoted + "\n")
    return _ensure_body("".join(lines), cls.name)


def new_module(class_name: str, scene_file: str, doc: str = "") -> str:
    """The code of a brand-new component: imports and an empty class tied to its scene."""
    doc = doc or f"The {class_name} component."
    return (
        f'"""{class_name}: a component designed in Pyzed Design.\n\n'
        f"The layout is in {scene_file}; properties, events and logic are below. Use it like\n"
        f"any component: ``{class_name}(...)`` in a view, or from the designer's toolbox.\n"
        f'"""\n\n'
        f"from pyzed.designer import SceneComponent\n\n\n"
        f"class {class_name}(SceneComponent, scene={literal(scene_file)}):\n"
        f'{INDENT}"""{doc}"""\n'
    )
