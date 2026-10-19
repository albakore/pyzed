"""The handlers module of a form: generating stubs and editing one function at a time.

Handlers are plain functions in a ``.py`` file next to the form, named
``<control>_<event>`` like in Visual Basic::

    def ok_button_click(form, event):
        form.status.text = f"Hello, {form.name_input.text}!"

The designer edits a single function's source at a time; this module finds it with
``ast`` and splices the new text into the file, so the rest of the file (imports,
helpers, comments) is never touched.
"""

from __future__ import annotations

import ast
import itertools
import sys
import textwrap
from pathlib import Path
from types import ModuleType
from typing import Dict, List, Optional, Tuple, Union

_counter = itertools.count()

HEADER = '''"""Event handlers for the {form} form.

Each function receives the running ``form`` (controls are attributes: ``form.button1.text``)
and an ``event`` with ``event.sender``, ``event.name`` and ``event.value``.
"""

'''


def handler_name(owner: str, event: str) -> str:
    """The conventional handler name: ``("button1", "click")`` -> ``"button1_click"``."""
    return f"{owner}_{event}"


def new_module(form_name: str) -> str:
    """Returns the text of a new, empty handlers module for the form ``form_name`` (just its docstring)."""
    return HEADER.format(form=form_name)


def stub(name: str, doc: str = "") -> str:
    """Returns the source of an empty handler ``name(form, event)`` with ``doc`` as its docstring (``"Event
    handler."`` if empty)."""
    doc = doc or "Event handler."
    return f'def {name}(form, event):\n    """{doc}"""\n    pass\n'


def find_function(source: str, name: str) -> Optional[Tuple[int, int]]:
    """The ``(first, last)`` 1-based lines of top-level function ``name`` (decorators included)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            first = min([node.lineno] + [d.lineno for d in node.decorator_list])
            return first, node.end_lineno or node.lineno
    return None


def functions(source: str) -> List[str]:
    """Names of the top-level functions in ``source``."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def get_function(source: str, name: str) -> Optional[str]:
    """Returns the source of top-level function ``name`` (decorators included), or ``None`` if missing."""
    span = find_function(source, name)
    if span is None:
        return None
    lines = source.splitlines(keepends=True)
    return "".join(lines[span[0] - 1: span[1]])


def ensure_function(source: str, name: str, doc: str = "") -> Tuple[str, bool]:
    """Adds a stub for ``name`` at the end of ``source`` if missing; returns ``(source, created)``."""
    if find_function(source, name) is not None:
        return source, False
    source = source.rstrip()
    gap = "\n\n\n" if source else ""
    return source + gap + stub(name, doc), True


def replace_function(source: str, name: str, new_code: str, *, strict: bool = True) -> str:
    """Replaces the source of function ``name`` with ``new_code`` (appended if it is missing).

    Raises ``SyntaxError`` if ``new_code`` is not valid Python or, with ``strict``, if it is
    anything but that one function (a line typed without indentation would otherwise
    escape into module code), so a typo in the event editor never corrupts the file.
    """
    new_code = textwrap.dedent(new_code).rstrip() + "\n"
    tree = ast.parse(new_code)
    if strict:
        body = tree.body
        if len(body) != 1 or not isinstance(body[0], (ast.FunctionDef, ast.AsyncFunctionDef)) \
                or body[0].name != name:
            line = body[1].lineno if len(body) > 1 else 1
            raise SyntaxError(f"keep the code indented inside def {name}(...)", ("<handler>", line, 1, ""))
    span = find_function(source, name)
    if span is None:
        source, _ = ensure_function(source, name)
        span = find_function(source, name)
        assert span is not None
    lines = source.splitlines(keepends=True)
    return "".join(lines[: span[0] - 1]) + new_code + "".join(lines[span[1]:])


def rename_function(source: str, old: str, new: str) -> str:
    """Renames the definition of ``old`` to ``new`` (calls elsewhere are left alone)."""
    span = find_function(source, old)
    if span is None or find_function(source, new) is not None:
        return source
    lines = source.splitlines(keepends=True)
    for i in range(span[0] - 1, span[1]):
        stripped = lines[i].lstrip()
        if stripped.startswith(("def ", "async def ")):
            lines[i] = lines[i].replace(f"def {old}(", f"def {new}(", 1)
            break
    return "".join(lines)


def body_is_empty(code: str) -> bool:
    """Whether a function only has a docstring and/or ``pass`` (an untouched stub)."""
    try:
        node = ast.parse(textwrap.dedent(code)).body[0]
    except (SyntaxError, IndexError):
        return False
    body = getattr(node, "body", [])
    return all(isinstance(s, ast.Pass) or (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
               for s in body)


def load_module(path: Union[str, Path]) -> ModuleType:
    """Imports a handlers file fresh (a new module object every time, so edits are picked up).

    The source is compiled directly instead of through the import system, so a stale
    ``__pycache__`` entry (same size, same second) can never hide an edit.
    """
    path = Path(path).resolve()
    module = ModuleType(f"pyzed_form_{path.stem}_{next(_counter)}")
    module.__file__ = str(path)
    folder = str(path.parent)
    added = folder not in sys.path
    if added:
        sys.path.insert(0, folder)
    try:
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)  # noqa: S102
    finally:
        if added:
            sys.path.remove(folder)
    return module


def handlers(module: Optional[ModuleType]) -> Dict[str, object]:
    """The callables defined in a handlers module, by name."""
    if module is None:
        return {}
    return {k: v for k, v in vars(module).items() if callable(v) and not k.startswith("_")}
