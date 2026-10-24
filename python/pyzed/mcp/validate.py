"""Static checks of the MCP server: Pyzed code and designer forms.

``check_code`` reads Python source without running it and reports names that do not exist in
``pyzed`` or ``pyzed.ui``, keyword arguments a function does not take, apps without ``view`` and
components without ``render``, side effects in ``view()``/``render()`` and lambdas in loops that do
not capture the loop variable, and tooltips that spell out their shortcut instead of ``keys=``. ``check_form`` validates a ``.pzform`` against the designer's
components. Both return ``{"ok": bool, "issues": [...]}``; ``ok`` is ``False`` only for errors. ``check_design``
reviews the design rules that code shows (theme tokens, the spacing and type scales, labels, tooltips, empty
states and one primary action per view).
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import re
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


def _positional(func: Any) -> Optional[int]:
    """How many positional arguments ``func`` takes, or ``None`` when it takes any (``*args``) or is unknown."""
    try:
        params = inspect.signature(func).parameters.values()
    except (TypeError, ValueError):
        return None
    if any(p.kind is p.VAR_POSITIONAL for p in params):
        return None
    return sum(p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) for p in params)


def _accepted(func: Any) -> Optional[Set[str]]:
    """The keyword names ``func`` takes, or ``None`` when it takes any (``**kwargs``) or is unknown."""
    try:
        params = inspect.signature(func).parameters.values()
    except (TypeError, ValueError):
        return None
    if any(p.kind is p.VAR_KEYWORD for p in params):
        return None
    return {p.name for p in params if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)}


_KEYS_TEXT = re.compile(r"\((ctrl|shift|alt|cmd|super|f\d+)\b|\b(ctrl|shift|alt|cmd)\+", re.IGNORECASE)


def _keys_in_text(node: ast.AST) -> bool:
    """Whether a tooltip's text spells out a shortcut ("Save (Ctrl+S)", ``format_keys(...)`` in an f-string)."""
    for part in ast.walk(node):
        if isinstance(part, ast.Constant) and isinstance(part.value, str) and _KEYS_TEXT.search(part.value):
            return True
        if isinstance(part, ast.Call) and getattr(part.func, "attr", getattr(part.func, "id", "")) == "format_keys":
            return True
    return False


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
            plain = callable(func) and not inspect.isclass(func)
            most = _positional(func) if plain else None
            given = len(node.args)
            if most is not None and given > most and not any(isinstance(a, ast.Starred) for a in node.args):
                self.issues.append(_issue(node, "error", f"{name}() takes {most} positional argument"
                                                         f"{'' if most == 1 else 's'} but {given} were given; "
                                                         "pass the rest by keyword"))
            accepted = _accepted(func) if plain else None
            if accepted is not None:
                for kw in node.keywords:
                    if kw.arg is not None and kw.arg not in accepted:
                        self.issues.append(_issue(kw, "error", f"{name}() has no parameter {kw.arg!r}; it takes: "
                                                                f"{', '.join(sorted(accepted)) or 'no keywords'}"))
        for kw in node.keywords:
            if kw.arg == "tooltip" and _keys_in_text(kw.value):
                self.issues.append(_issue(kw, "warning", "the tooltip writes its shortcut into the text; pass "
                                                         "keys=\"ctrl-s\" instead, which draws key caps"))
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


def animation_triggers() -> Dict[str, Any]:
    """What a ``.pzform`` control's ``animations`` entries take: the triggers (``on``) and presets by category."""
    from .. import animation as _animation
    from ..designer import motion

    return {"triggers": {key: label for key, label in motion.TRIGGERS},
            "event_triggers": sorted(motion.EVENT_TRIGGERS),
            "presets": {c: sorted(_animation.presets(c)) for c in _animation.CATEGORIES},
            "easings": list(motion.EASINGS), "repeats": list(motion.REPEATS),
            "example": [{"preset": "fade_in_up", "on": "mount"}, {"preset": "shake", "on": "invalid"},
                        {"preset": "tada", "on": "event", "source": "save", "event": "click"}]}


def _animation_issues(form: Any, control: Any) -> List[tuple]:
    """Problems of a control's ``animations`` entries: unknown presets or triggers, events that don't exist."""
    from ..designer import components, motion

    out: List[tuple] = []
    for i, entry in enumerate(control.animations or ()):
        where = f"{control.name}.animations[{i}]"
        if not isinstance(entry, dict):
            out.append(("error", f"{where}: an animation is an object like {{\"preset\": \"fade_in\"}}"))
            continue
        if motion.preset_of(entry) is None:
            out.append(("error", f"{where}: unknown preset {entry.get('preset')!r}; see form_animations()"))
        on = entry.get("on")
        if on not in (None, "") and on not in motion.TRIGGER_LABELS:
            out.append(("error", f"{where}: unknown trigger on={on!r}; it takes: {', '.join(motion.TRIGGER_LABELS)}"))
        if on == "event":
            source, event = str(entry.get("source") or ""), str(entry.get("event") or "")
            if source and form.get(source) is None:
                out.append(("error", f"{where}: source {source!r} is not a control of the form"))
            elif not event:
                out.append(("error", f"{where}: on='event' needs an \"event\" of its source"))
            else:
                try:
                    events = (components.get(form[source].type).all_events + ("invalid",)) if source \
                        else components.FORM_EVENTS
                except KeyError:
                    events = ()
                if events and event not in events:
                    out.append(("error", f"{where}: {source or 'the form'} has no event {event!r}; it has: "
                                         f"{', '.join(events)}"))
    return out


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
        for issue in _animation_issues(form, control):
            add(*issue)
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


# -- design review ------------------------------------------------------------------------------------

#: Keywords and style keys that take a color: a theme token there follows light and dark themes.
_COLOR_KEYS = {"color", "background", "bg", "border_color", "icon_color", "fill", "stroke", "tint", "glow",
               "placeholder_color", "selection_color", "ring_color", "hover_border_color", "focus_border_color"}
_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
#: The spacing scale (a 4 px grid, with 2 and 6 for tight spots).
SPACING = (0, 1, 2, 4, 6, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96)
_SPACING_KEYS = {"spacing", "gap", "padding", "margin"}
#: The type scale of ``ui.label(size=...)`` in pixels, plus 14 (the theme's UI font size).
TYPE_SCALE = (11, 12, 13.5, 14, 16, 20, 26)
_VAGUE_LABELS = {"ok", "submit", "click here", "yes", "no", "go", "send", "here", "button"}
_BUTTONS = {"ui.button", "ui.split_button"}

#: What a screenshot shows and code can't: the checks to do by eye before delivering.
DESIGN_CHECKLIST = [
    "One primary action (variant='solid') per view, where the flow ends (bottom right of forms and dialogs).",
    "Hierarchy at a glance: one title, body text, muted secondary text; at most two font weights.",
    "Spacing on the 4 px scale, inner space smaller than outer space, aligned edges.",
    "Only theme tokens: the screen works in screenshot(theme='Pyzed Light') and theme='Pyzed Dark'.",
    "Loading, empty, error and ideal states are designed for every list, table and request.",
    "Every icon-only button has a tooltip (and keys= for its shortcut); every input a visible label.",
    "The whole task works with the keyboard (Tab order = reading order, Enter submits, Esc closes).",
    "Sentence case, specific verb labels, errors that say how to fix them.",
    "It still works at App.min_size and with 30 % longer text (translations).",
    "Nothing slow runs in view(); every action gives feedback within 100 ms.",
]


class _DesignChecker(ast.NodeVisitor):
    """Design rules that can be read from the code (see ``get_guide("design")``)."""

    def __init__(self, base: _Checker) -> None:
        self.base = base
        self.issues: List[Dict[str, Any]] = []
        self.parents: List[str] = []

    def add(self, node: ast.AST, rule: str, message: str) -> None:
        issue = _issue(node, "warning", message)
        issue["rule"] = rule
        self.issues.append(issue)

    def _value(self, key: str, node: ast.AST) -> None:
        if not isinstance(node, ast.Constant):
            if isinstance(node, ast.Tuple) and key in _SPACING_KEYS:
                for item in node.elts:
                    self._value(key, item)
            elif isinstance(node, ast.Tuple) and key in ("border", "shadow"):
                for item in node.elts:
                    self._value("color", item)
            return
        value = node.value
        if key in _COLOR_KEYS | {"border", "shadow"} and isinstance(value, str) and _HEX.match(value):
            self.add(node, "theme-tokens", f"{key}={value!r} is a fixed color; use a theme token (\"panel\", "
                                           "\"text_muted\", \"accent\", \"error\"...) so light and dark themes work")
        elif key in _SPACING_KEYS and isinstance(value, (int, float)) and not isinstance(value, bool) \
                and value not in SPACING:
            self.add(node, "spacing-scale", f"{key}={value!r} is off the spacing scale; use one of "
                                            f"{', '.join(map(str, SPACING[2:12]))} (a 4 px grid)")

    def _style_dict(self, node: ast.Dict) -> None:
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                if isinstance(value, ast.Dict):
                    self._style_dict(value)
                else:
                    self._value(key.value, value)

    def visit_Call(self, node: ast.Call) -> None:
        target = self.base._target(node.func)
        name = target[0] if target else (getattr(node.func, "attr", "") or getattr(node.func, "id", ""))
        for kw in node.keywords:
            if kw.arg:
                self._value(kw.arg, kw.value)
        if name in ("pz.stylesheet", "pz.define_style") or getattr(node.func, "attr", "") == "style":
            for arg in node.args:
                if isinstance(arg, ast.Dict):
                    self._style_dict(arg)
        keywords = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        if name == "ui.icon_button" and "tooltip" not in keywords:
            self.add(node, "icon-tooltip", "ui.icon_button without tooltip=: an icon alone is not a label; say "
                                           "what it does (and add keys= for its shortcut)")
        if name in _BUTTONS and node.args and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str):
            text = node.args[0].value.strip()
            if text.lower() in _VAGUE_LABELS:
                self.add(node, "button-label", f"button label {text!r} is vague; name the action (\"Save changes\", "
                                               "\"Delete report\")")
            elif len(text) > 3 and text.isupper():
                self.add(node, "sentence-case", f"button label {text!r} is in capitals; use sentence case")
        if name in ("ui.label", "ui.heading", "pz.text") and isinstance(keywords.get("size"), ast.Constant):
            size = keywords["size"].value
            if isinstance(size, (int, float)) and not isinstance(size, bool) and size not in TYPE_SCALE:
                self.add(node, "type-scale", f"text size {size!r} is off the type scale; use \"xs\", \"sm\", \"md\", "
                                             "\"lg\", \"xl\" or \"2xl\" (11, 12, 13.5, 16, 20, 26 px)")
        if name == "ui.input" and "ui.field" not in self.parents and "placeholder" not in keywords:
            self.add(node, "input-label", "ui.input without a label: wrap it in ui.field(\"Title\", ...) or give it "
                                          "a placeholder when the context labels it (a search box)")
        if name == "ui.table" and "empty" not in keywords:
            self.add(node, "empty-state", "ui.table without empty=: show what an empty table means and how to fill it "
                                          "(ui.empty_state(..., size=\"sm\"))")
        self.parents.append(name)
        self.generic_visit(node)
        self.parents.pop()

    def visit_FunctionDef(self, node: Any) -> None:
        primaries = [kw for call in ast.walk(node) if isinstance(call, ast.Call)
                     for kw in call.keywords if kw.arg == "variant" and isinstance(kw.value, ast.Constant)
                     and kw.value.value in ("solid", "accent")]
        if len(primaries) > (1 if node.name in ("view", "render") else 2):
            self.add(node, "one-primary", f"{node.name}() has {len(primaries)} primary (solid) buttons; keep one "
                                          "primary action per view and make the rest \"filled\" or \"ghost\"")
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef


def check_design(source: str) -> Dict[str, Any]:
    """Reviews the design of Pyzed code without running it: fixed colors instead of theme tokens, spacing off the
    4 px grid, text sizes off the type scale, icon buttons without tooltips, vague or capitalised button labels,
    inputs without a label, tables without an empty state and views with several primary buttons. Returns the
    ``issues`` (each with a ``rule``) and the ``checklist`` of what to check by eye on a screenshot."""
    try:
        tree = ast.parse(source)
    except SyntaxError as err:
        return {"ok": False, "issues": [{"line": err.lineno or 1, "column": err.offset or 1, "severity": "error",
                                         "rule": "syntax", "message": f"syntax error: {err.msg}"}],
                "checklist": DESIGN_CHECKLIST}
    base = _Checker()
    base.visit(tree)
    checker = _DesignChecker(base)
    checker.visit(tree)
    issues = sorted(checker.issues, key=lambda i: (i["line"], i["column"]))
    return {"ok": not issues, "issues": issues, "checklist": DESIGN_CHECKLIST,
            "guide": "get_guide('design') has the rules behind each check"}
