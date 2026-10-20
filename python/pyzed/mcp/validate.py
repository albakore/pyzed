"""Static checks of the MCP server: Pyzed code and designer forms.

``check_code`` reads Python source without running it and reports names that do not exist in
``pyzed`` or ``pyzed.ui``, keyword arguments a function does not take, apps without ``view`` and
components without ``render``, side effects in ``view()``/``render()`` and lambdas in loops that do
not capture the loop variable. ``check_form`` validates a ``.pzform`` against the designer's
components. Both return ``{"ok": bool, "issues": [...]}``; ``ok`` is ``False`` only for errors.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Sequence, Set

import pyzed

#: Calls that should not happen while building the widget tree.
_SIDE_EFFECTS = {"sleep", "urlopen", "get", "post", "put", "delete", "request", "system", "run", "Popen", "remove",
                 "rmtree", "connect"}
_SIDE_EFFECT_MODULES = {"time", "os", "subprocess", "requests", "httpx", "urllib", "shutil", "socket"}


def _issue(node: Optional[ast.AST], severity: str, message: str) -> Dict[str, Any]:
    return {"line": getattr(node, "lineno", 1), "column": getattr(node, "col_offset", 0) + 1,
            "severity": severity, "message": message}


def _accepted(func: Any) -> Optional[Set[str]]:
    """The keyword names ``func`` takes, or ``None`` when it takes any (``**kwargs``) or is unknown."""
    try:
        params = inspect.signature(func).parameters.values()
    except (TypeError, ValueError):
        return None
    if any(p.kind is p.VAR_KEYWORD for p in params):
        return None
    return {p.name for p in params if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)}


class _Checker(ast.NodeVisitor):
    def __init__(self) -> None:
        self.issues: List[Dict[str, Any]] = []
        self.pz: Set[str] = set()       # names bound to the pyzed module
        self.ui: Set[str] = set()       # names bound to pyzed.ui
        self.imported: Dict[str, Any] = {}  # names imported from pyzed / pyzed.ui
        self.runs: List[ast.AST] = []

    # -- imports ------------------------------------------------------------------------------------
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "pyzed":
                self.pz.add(alias.asname or "pyzed")
            elif alias.name == "pyzed.ui" and alias.asname:
                self.ui.add(alias.asname)
            elif alias.name == "pyzed.ui":
                self.pz.add("pyzed")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module not in ("pyzed", "pyzed.ui") or node.level:
            return
        source = pyzed if node.module == "pyzed" else pyzed.ui
        for alias in node.names:
            if alias.name == "*":
                continue
            local = alias.asname or alias.name
            if node.module == "pyzed" and alias.name == "ui":
                self.ui.add(local)
            elif not hasattr(source, alias.name) and importlib.util.find_spec(f"{node.module}.{alias.name}") is None:
                self.issues.append(_issue(node, "error", f"{node.module} has no {alias.name!r}"))
            elif hasattr(source, alias.name):
                self.imported[local] = getattr(source, alias.name)

    # -- names and calls ----------------------------------------------------------------------------
    def _target(self, node: ast.AST):
        """``(qualified name, object)`` when ``node`` is ``pz.x``, ``pz.ui.x``, ``ui.x`` or an imported name."""
        if isinstance(node, ast.Name) and node.id in self.imported:
            return node.id, self.imported[node.id]
        if not isinstance(node, ast.Attribute):
            return None
        value = node.value
        if isinstance(value, ast.Name) and value.id in self.pz:
            if not hasattr(pyzed, node.attr):
                return f"pz.{node.attr}", None
            return f"pz.{node.attr}", getattr(pyzed, node.attr)
        is_ui = (isinstance(value, ast.Name) and value.id in self.ui) or (
            isinstance(value, ast.Attribute) and value.attr == "ui" and isinstance(value.value, ast.Name)
            and value.value.id in self.pz)
        if is_ui:
            return f"ui.{node.attr}", getattr(pyzed.ui, node.attr, None)
        return None

    def visit_Attribute(self, node: ast.Attribute) -> None:
        target = self._target(node)
        if target is not None and target[1] is None:
            self.issues.append(_issue(node, "error", f"{target[0]} does not exist; check list_components"))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        target = self._target(node.func)
        if target is not None and target[1] is not None:
            name, func = target
            if name.endswith(".run") or name == "run":
                self.runs.append(node)
            accepted = _accepted(func) if callable(func) and not inspect.isclass(func) else None
            if accepted is not None:
                for kw in node.keywords:
                    if kw.arg is not None and kw.arg not in accepted:
                        self.issues.append(_issue(kw, "error", f"{name}() has no parameter {kw.arg!r}; it takes: "
                                                                f"{', '.join(sorted(accepted)) or 'no keywords'}"))
        self.generic_visit(node)

    # -- classes ------------------------------------------------------------------------------------
    def _base(self, node: ast.ClassDef) -> Optional[str]:
        for base in node.bases:
            target = self._target(base)
            if target is not None and target[1] in (pyzed.App, pyzed.Component):
                return "App" if target[1] is pyzed.App else "Component"
        return None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        base = self._base(node)
        methods = {n.name: n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        if base == "App":
            if "view" not in methods:
                self.issues.append(_issue(node, "error", f"{node.name} is a pz.App without a view() method"))
            else:
                self._check_pure(methods["view"])
            for item in node.body:
                if isinstance(item, ast.Assign) and isinstance(item.value, (ast.List, ast.Dict, ast.Set)):
                    names = ", ".join(t.id for t in item.targets if isinstance(t, ast.Name))
                    self.issues.append(_issue(item, "warning", f"mutable class attribute {names} on an App is shared "
                                                               "state; initialize it in __init__"))
        elif base == "Component":
            if "render" not in methods:
                self.issues.append(_issue(node, "error", f"{node.name} is a pz.Component without a render() method"))
            else:
                self._check_pure(methods["render"])
        self.generic_visit(node)

    def _check_pure(self, func: ast.AST) -> None:
        """Warns about state changes and I/O in ``view()``/``render()`` (outside lambdas and nested functions)."""
        name = getattr(func, "name", "view")
        stack = list(ast.iter_child_nodes(func))
        while stack:
            node = stack.pop()
            if isinstance(node, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self":
                        self.issues.append(_issue(node, "warning", f"{name}() changes self.{t.attr}; {name}() runs "
                                                                   "after every message and must not change state"))
            if isinstance(node, ast.Call):
                fn = node.func
                called = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""
                module = fn.value.id if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) else ""
                builtin = isinstance(fn, ast.Name) and called in ("open", "input", "print")
                if builtin or called in ("sleep", "urlopen") or (module in _SIDE_EFFECT_MODULES
                                                                 and called in _SIDE_EFFECTS):
                    self.issues.append(_issue(node, "warning", f"{name}() calls {module + '.' if module else ''}"
                                                               f"{called}(); do I/O in update, callbacks or tasks"))
            stack.extend(ast.iter_child_nodes(node))

    # -- loops --------------------------------------------------------------------------------------
    def _loop(self, targets: Sequence[ast.AST], body: Sequence[ast.AST]) -> None:
        names = {n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)}

        def visit(node: ast.AST, bound: Set[str]) -> None:
            if isinstance(node, ast.Lambda):
                args = {a.arg for a in node.args.args + node.args.kwonlyargs}
                inner = {n.id for n in ast.walk(node.body) if isinstance(n, ast.Name)}
                for var in sorted((inner & names) - args - bound):
                    self.issues.append(_issue(node, "warning", f"lambda uses the loop variable {var!r}: capture it "
                                                               f"with a default (lambda {var}={var}: ...)"))
                bound = bound | args | (inner & names)  # reported once, here
            for child in ast.iter_child_nodes(node):
                visit(child, bound)

        for part in body:
            visit(part, set())

    def visit_For(self, node: ast.For) -> None:
        self._loop([node.target], node.body)
        self.generic_visit(node)

    def _comprehension(self, node: Any) -> None:
        elements = [node.elt] if hasattr(node, "elt") else [node.key, node.value]
        self._loop([g.target for g in node.generators], elements)
        self.generic_visit(node)

    visit_ListComp = visit_SetComp = visit_GeneratorExp = visit_DictComp = _comprehension


def _ruff(source: str) -> List[Dict[str, Any]]:
    exe = shutil.which("ruff")
    if exe is None:
        return []
    try:
        # Only syntax errors and pyflakes: style rules would bury the useful findings.
        cmd = [exe, "check", "--isolated", "--select", "E9,F", "--output-format", "json",
               "--stdin-filename", "app.py", "-"]
        result = subprocess.run(cmd, input=source, capture_output=True, text=True, timeout=30,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        found = json.loads(result.stdout or "[]")
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    return [{"line": f["location"]["row"], "column": f["location"]["column"], "severity": "warning",
             "message": f"ruff {f['code']}: {f['message']}"} for f in found]


def check_code(source: str, *, lint: bool = True) -> Dict[str, Any]:
    """Checks Pyzed source code without running it (and with ruff when ``lint`` and it is installed)."""
    try:
        tree = ast.parse(source)
    except SyntaxError as err:
        return {"ok": False, "issues": [{"line": err.lineno or 1, "column": err.offset or 1, "severity": "error",
                                         "message": f"syntax error: {err.msg}"}]}
    checker = _Checker()
    checker.visit(tree)
    issues = checker.issues
    if len(checker.runs) > 1:
        issues.append(_issue(checker.runs[1], "warning", "pz.run() is called more than once; it can only start "
                                                         "one event loop per process"))
    if lint:
        issues += _ruff(source)
    issues.sort(key=lambda i: (i["line"], i["column"]))
    return {"ok": not any(i["severity"] == "error" for i in issues), "issues": issues}


def check_form(content: str, handlers: str = "") -> Dict[str, Any]:
    """Validates the JSON of a ``.pzform`` and, when given, that its handlers module defines every handler."""
    from ..designer import code as code_mod
    from ..designer import components
    from ..designer.model import RESERVED, Form

    issues: List[Dict[str, Any]] = []

    def add(severity: str, message: str) -> None:
        issues.append({"severity": severity, "message": message})

    try:
        data = json.loads(content)
        form = Form.from_dict(data)
    except (ValueError, TypeError) as err:
        return {"ok": False, "issues": [{"severity": "error", "message": f"not a valid form: {err}"}]}
    raw = data.get("controls", [])
    seen: Set[str] = set()
    wanted: Dict[str, str] = {}
    for c in raw:
        name = str(c.get("name", ""))
        if not name.isidentifier():
            add("error", f"control name {name!r} is not a valid identifier")
        elif name in RESERVED:
            add("error", f"control name {name!r} is reserved; rename it")
        if name in seen:
            add("error", f"two controls are called {name!r}")
        seen.add(name)
        if c.get("parent") and c["parent"] not in {str(o.get("name")) for o in raw}:
            add("error", f"{name}: parent {c['parent']!r} does not exist")
    for control in form.controls:
        try:
            spec = components.get(control.type)
        except KeyError:
            add("error", f"{control.name}: unknown component type {control.type!r}; "
                         "see list_components(kind='designer')")
            continue
        for prop in control.props:
            if spec.prop(prop) is None:
                add("warning", f"{control.name}: {control.type} has no prop {prop!r}")
        for event, handler in control.events.items():
            if event not in spec.all_events:
                known = ", ".join(spec.all_events)
                add("error", f"{control.name}: {control.type} has no event {event!r}; it has: {known}")
            if not str(handler).isidentifier():
                add("error", f"{control.name}.{event}: handler {handler!r} is not a valid function name")
            wanted[str(handler)] = f"{control.name}.{event}"
        if control.parent:
            parent = form.get(control.parent)
            if parent is not None and components.get(parent.type).container is None:
                add("error", f"{control.name}: its parent {parent.name!r} ({parent.type}) is not a container")
    for event, handler in form.events.items():
        if event not in components.FORM_EVENTS:
            add("error", f"the form has no event {event!r}; it has: {', '.join(components.FORM_EVENTS)}")
        wanted[str(handler)] = f"form.{event}"
    if handlers:
        try:
            defined = set(code_mod.functions(handlers))
        except SyntaxError as err:
            add("error", f"handlers module: syntax error on line {err.lineno}: {err.msg}")
        else:
            for handler, where in wanted.items():
                if handler not in defined:
                    add("error", f"{where} calls {handler}(form, event), which the handlers module does not define")
    return {"ok": not any(i["severity"] == "error" for i in issues), "issues": issues,
            "controls": len(form.controls)}
