"""Hot reload: edit your code, save, and the running window shows the change.

Turn it on with ``pz.run(MyApp, reload=True)``, the ``PYZED_RELOAD=1`` environment
variable, or by starting the app with ``pyzed dev main.py``.

How it works:

1. A background thread watches the ``.py`` files of your project: the folder of the
   module that defines your app, plus any ``paths`` you pass.
2. When one is saved, the runtime re-executes the changed modules, and the modules
   that use them, on the UI thread (``importlib.reload``; the main script is re-run
   with ``__name__`` set to something other than ``"__main__"``, so its
   ``if __name__ == "__main__":`` block does not run again).
3. Every live instance of a reloaded class is switched to the new class
   (``obj.__class__ = New``). Methods, ``view()`` and class attributes come from the new
   code. The old functions get the new code too, so a method kept somewhere else (a
   callback stored in an attribute, a timer, a thread...) also runs the new version.
4. The state is kept and brought up to date. When a class changed, its ``__init__``
   (``setup()`` for a component) runs again on a scratch copy, with the arguments the
   object was created with, and the live object takes from it:

   - the attributes it does not have yet (a new ``self.tags = []`` shows up at once);
   - the new initial value of plain data (numbers, text, lists...) that has not changed
     since it started (edit ``self.step = 1`` to ``self.step = 5`` and it is 5, unless
     the app changed it while running, in which case its value is kept).

   Everything else (what the user typed, picked or loaded) stays as it was.
5. The window redraws. If the new code fails to import, or ``view()`` raises, the error
   is shown in the window until you save a fix.

Each reload prints what changed (``Reloader.changes`` keeps it)::

    pyzed: reloaded Notes: methods changed: add, view; new state: tags

Running ``__init__`` again is skipped for classes whose code did not change, and for
classes with ``reload_init = False`` (use it when ``__init__`` opens files, devices or
connections). Define ``on_reload(self)`` on your app or window to migrate anything
else after each reload (it may return a ``Command``)::

    class Notes(pz.App):
        def on_reload(self):
            self.tags = [t.lower() for t in self.tags]

Files that are not Python (a form layout, a stylesheet...) can be watched too with
``Reloader.watch(path, callback)``; the callback runs on the UI thread after the file
changes and the window then redraws.
"""

from __future__ import annotations

import ast
import contextlib
import copy
import gc
import importlib
import importlib.util
import inspect
import linecache
import os
import sys
import sysconfig
import textwrap
import threading
import time
import traceback
import types
import weakref
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from . import _core

__all__ = ["Change", "Reloader", "ReloadError", "current", "enable", "enabled_by_env", "is_reloading", "remember"]

_PACKAGE_DIR = Path(__file__).resolve().parent
_REPLAY_NAME = "__pyzed_reload__"
#: Frames from these folders are left out of the tracebacks shown after a failed reload.
_INTERNAL_DIRS = (_PACKAGE_DIR, Path(importlib.__file__).resolve().parent)

#: The reloader of the running app (``None`` when hot reload is off).
_current: Optional["Reloader"] = None
#: True while modules are being re-executed (``pz.run`` calls are ignored then).
_reloading = False
#: The reloader whose last reload failed (its windows show the error until a fix is saved).
_failed: Optional["Reloader"] = None
#: Every window that has been drawn, so reloaded classes reach all of them.
_windows: "weakref.WeakSet[Any]" = weakref.WeakSet()
#: The initial plain values of each live object, by ``id``: what ``__init__`` gave it.
_initial: Dict[int, Tuple["weakref.ref[Any]", Dict[str, Any]]] = {}


class ReloadError(Exception):
    """Raised by ``view()`` while the last reload failed; the window shows its message."""


@dataclass
class Change:
    """What one reload changed in a class (see ``Reloader.changes``)."""

    #: The class's qualified name (``"Notes"``, ``"Notes.Settings"``).
    name: str
    #: Methods whose code changed.
    changed: List[str] = field(default_factory=list)
    #: Methods that are new.
    added: List[str] = field(default_factory=list)
    #: Methods that are gone.
    removed: List[str] = field(default_factory=list)
    #: Attributes that live objects did not have and got from the new ``__init__``.
    new_state: List[str] = field(default_factory=list)
    #: Attributes whose initial value changed in the code and were updated.
    updated_state: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.changed or self.added or self.removed or self.new_state or self.updated_state)

    def __str__(self) -> str:
        parts = []
        for label, names in (("methods changed", self.changed), ("new methods", self.added),
                             ("removed methods", self.removed), ("new state", self.new_state),
                             ("updated state", self.updated_state)):
            if names:
                parts.append(f"{label}: {', '.join(names)}")
        return f"{self.name}: {'; '.join(parts)}" if parts else self.name


def current() -> Optional["Reloader"]:
    """The active ``Reloader``, or ``None`` when hot reload is off."""
    return _current


def enabled_by_env() -> bool:
    """Whether ``PYZED_RELOAD`` asks for hot reload (``1``, ``true``, ``yes`` or ``on``)."""
    return os.environ.get("PYZED_RELOAD", "").strip().lower() in {"1", "true", "yes", "on"}


def watched_by_env() -> List[str]:
    """Extra paths to watch from ``PYZED_WATCH`` (separated like ``PATH``; set by ``pyzed dev --watch``)."""
    return [p for p in os.environ.get("PYZED_WATCH", "").split(os.pathsep) if p]


def is_reloading() -> bool:
    """True while modules are being re-executed by a reload."""
    return _reloading


def _library_dirs() -> List[Path]:
    """Folders whose files are never reloaded: the standard library, site-packages, Pyzed."""
    dirs = {_PACKAGE_DIR}
    for key in ("stdlib", "platstdlib", "purelib", "platlib"):
        path = sysconfig.get_paths().get(key)
        if path:
            dirs.add(Path(path).resolve())
    dirs.add(Path(sys.prefix).resolve() / "lib")
    return sorted(dirs)


def _within(path: Path, folder: Path) -> bool:
    try:
        path.relative_to(folder)
        return True
    except ValueError:
        return False


def _module_file(module: types.ModuleType) -> Optional[Path]:
    file = getattr(module, "__file__", None)
    if not file or not str(file).endswith(".py"):
        return None
    try:
        return Path(file).resolve()
    except OSError:
        return None


def _format_error(err: BaseException, root: Optional[Path] = None) -> str:
    """The traceback of ``err`` without Pyzed's and importlib's own frames.

    File names inside ``root`` (the project folder) are shown relative to it.
    """
    report = traceback.TracebackException.from_exception(err)
    report.stack = traceback.StackSummary.from_list(
        [
            frame
            for frame in report.stack
            if not frame.filename.startswith("<frozen")
            and not any(_within(Path(frame.filename).resolve(), d) for d in _INTERNAL_DIRS)
        ]
    )
    text = "".join(report.format())
    return text.replace(str(root) + os.sep, "") if root is not None else text


_PLAIN = (type(None), bool, int, float, complex, str, bytes)


def _plain(value: Any, depth: int = 0) -> bool:
    """Whether ``value`` is plain data (numbers, text, and small lists, tuples, sets and dicts of them)."""
    if isinstance(value, _PLAIN):
        return type(value) in _PLAIN
    if depth >= 4 or type(value) not in (list, tuple, set, frozenset, dict) or len(value) > 1000:
        return False
    if type(value) is dict:
        return all(_plain(k, depth + 1) and _plain(v, depth + 1) for k, v in value.items())
    return all(_plain(v, depth + 1) for v in value)


def _same(a: Any, b: Any) -> bool:
    try:
        return type(a) is type(b) and bool(a == b)
    except Exception:  # noqa: BLE001 - an odd __eq__ just means "not the same"
        return False


def _state_names(obj: Any) -> Iterable[str]:
    """The instance attributes that are state (not Pyzed's own, nor a component's props)."""
    props = getattr(type(obj), "__props__", None) or ()
    return [n for n in vars(obj) if not n.startswith("_pyzed") and n not in props]


def _snapshot(obj: Any) -> Dict[str, Any]:
    values = vars(obj)
    return {n: copy.deepcopy(values[n]) for n in _state_names(obj) if _plain(values[n])}


def remember(obj: Any) -> None:
    """Records the initial plain values of ``obj`` (once), so a reload can tell what the app changed.

    The runtime calls it for the app, each window and each component; call it for other
    objects created after hot reload started only if you need their defaults updated too.
    """
    entry = _initial.get(id(obj))
    if entry is not None and entry[0]() is obj:
        return
    try:
        ref = weakref.ref(obj, lambda _r, key=id(obj): _initial.pop(key, None))
        _initial[id(obj)] = (ref, _snapshot(obj))
    except TypeError:
        pass  # no weak references (slots): only new attributes are added on reload


def _code_key(code: types.CodeType) -> tuple:
    """What a function does, without its line numbers (moving a method is not a change)."""
    consts = tuple(_code_key(c) if isinstance(c, types.CodeType) else (type(c).__name__, repr(c)) for c in code.co_consts)
    return (code.co_code, code.co_names, code.co_varnames, code.co_freevars, consts,
            getattr(code, "co_exceptiontable", b""))


def _functions(value: Any) -> List[types.FunctionType]:
    """The plain functions behind a class attribute (methods, static/class methods, properties)."""
    if isinstance(value, (staticmethod, classmethod)):
        value = value.__func__
    if isinstance(value, property):
        return [f for f in (value.fget, value.fset, value.fdel) if isinstance(f, types.FunctionType)]
    if isinstance(value, types.FunctionType):
        return [value]
    return []


def _fingerprint(cls: type) -> tuple:
    """The class's own code and plain attributes: equal fingerprints mean nothing to update."""
    items = []
    for name, value in vars(cls).items():
        functions = _functions(value)
        if functions:
            items.append((name, tuple(_code_key(f.__code__) for f in functions)))
        elif _plain(value) or type(value).__name__ == "State":  # a component's ``pz.state(...)``
            items.append((name, repr(value)))
        elif not isinstance(value, type):
            items.append((name,))
    return tuple(sorted(items, key=lambda item: item[0]))


def _patch_function(old: types.FunctionType, new: types.FunctionType) -> None:
    """Gives ``old`` the code of ``new``, so every reference to ``old`` runs the new code."""
    if old is new:
        return
    try:
        old.__code__ = new.__code__
    except ValueError:
        return  # a different number of closure variables: references to `old` keep the old code
    old.__defaults__ = new.__defaults__
    old.__kwdefaults__ = new.__kwdefaults__
    old.__doc__ = new.__doc__
    for old_cell, new_cell in zip(old.__closure__ or (), new.__closure__ or ()):
        try:  # `__class__` (used by `super()`) now names the new class, and so on
            old_cell.cell_contents = new_cell.cell_contents
        except ValueError:
            pass  # an empty cell


def _fresh(obj: Any) -> Any:
    """A scratch instance of ``obj``'s (new) class, initialized like ``obj`` was, or ``None``."""
    build = getattr(obj, "__pyzed_fresh__", None)
    if build is None or not getattr(type(obj), "reload_init", True):
        return None
    with contextlib.redirect_stdout(None):  # what __init__ prints already showed once
        return build()


def _init_defaults(obj: Any) -> Dict[str, Any]:
    """New attributes of a plain object, from the simple ``self.name = value`` lines of its ``__init__``.

    Objects that Pyzed did not create (a ``Todo`` of your model, for example) cannot run
    ``__init__`` again: their arguments are unknown. A line whose value only uses
    ``self``, globals and builtins (``self.done = False``, ``self.tags = []``) still runs.
    """
    init = getattr(type(obj), "__init__", None)
    if not isinstance(init, types.FunctionType) or not init.__code__.co_argcount or not hasattr(obj, "__dict__"):
        return {}
    try:
        linecache.checkcache(init.__code__.co_filename)
        node = ast.parse(textwrap.dedent(inspect.getsource(init))).body[0]
    except (OSError, TypeError, SyntaxError, IndexError):
        return {}
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return {}
    me = init.__code__.co_varnames[0]
    other_locals = set(init.__code__.co_varnames) - {me}
    found: Dict[str, Any] = {}
    for statement in node.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target, value = statement.targets[0], statement.value
        elif isinstance(statement, ast.AnnAssign) and statement.value is not None:
            target, value = statement.target, statement.value
        else:
            continue
        if not (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == me):
            continue
        if target.attr in vars(obj) or target.attr in found:
            continue
        if any(isinstance(n, ast.Name) and n.id in other_locals for n in ast.walk(value)):
            continue  # it needs an argument or a local variable of __init__
        try:
            found[target.attr] = eval(compile(ast.Expression(value), init.__code__.co_filename, "eval"),  # noqa: S307
                                      init.__globals__, {me: obj})
        except Exception:  # noqa: BLE001 - the attribute just stays missing
            continue
    return found


def _merge_state(obj: Any, fresh: Any) -> Tuple[List[str], List[str]]:
    """Copies into ``obj`` the attributes it lacks and the new defaults of untouched plain values."""
    entry = _initial.get(id(obj))
    initial = entry[1] if entry is not None and entry[0]() is obj else None
    values = vars(obj)
    added: List[str] = []
    updated: List[str] = []
    fresh_values = vars(fresh)
    for name in _state_names(fresh):
        value = fresh_values[name]
        if isinstance(value, types.MethodType) and value.__self__ is fresh:
            value = types.MethodType(value.__func__, obj)  # `self.on_done = self.close` in __init__
        if name not in values:
            values[name] = value
            added.append(name)
        elif initial is not None and name in initial and _plain(value):
            if _same(values[name], initial[name]) and not _same(value, initial[name]):
                values[name] = value
                updated.append(name)
    _initial.pop(id(obj), None)
    remember(obj)
    if id(obj) in _initial:  # the new defaults are what later edits compare against
        _initial[id(obj)] = (_initial[id(obj)][0], _snapshot(fresh))
    return added, updated


def _imported_names(module: types.ModuleType) -> Set[str]:
    """The modules that ``module``'s source imports (``import a.b`` gives ``a`` and ``a.b``)."""
    file = _module_file(module)
    try:
        tree = ast.parse(file.read_text(encoding="utf-8")) if file else None
    except (OSError, SyntaxError, ValueError):
        return set()
    if tree is None:
        return set()
    package = getattr(module, "__package__", None) or ""
    found: Set[str] = set()

    def add(name: str) -> None:
        parts = name.split(".")
        found.update(".".join(parts[: i + 1]) for i in range(len(parts)))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                anchor = package.split(".")[: max(0, len(package.split(".")) - node.level + 1)] if package else []
                base = ".".join([*anchor, base] if base else anchor)
            if base:
                add(base)
                for alias in node.names:
                    add(f"{base}.{alias.name}")  # `from pkg import submodule`
    return found


class Reloader:
    """Watches the project's files and reloads changed code into a running app.

    ``app`` is the running ``App`` instance. ``paths`` are extra folders or files to
    watch; by default the folder of the module that defines the app's class is watched.
    ``interval`` is how often, in seconds, files are checked for changes.

    Most programs never create one directly: ``pz.run(app, reload=True)`` does it.
    """

    def __init__(self, app: Any, paths: Sequence[Any] = (), *, interval: float = 0.25):
        self.app = app
        self.interval = interval
        self.roots: List[Path] = []
        main = sys.modules.get(type(app).__module__)
        main_file = _module_file(main) if main else None
        if main_file is not None:
            self.roots.append(main_file.parent)
        for path in paths:
            self.roots.append(Path(path).resolve())
        self._excluded = [d for d in _library_dirs() if not any(_within(r, d) for r in self.roots)]
        self._mtimes: Dict[Path, float] = {}
        self._extra: Dict[Path, List[Callable[[Path], Any]]] = {}
        self._pending: Set[Path] = set()
        self._posted = False
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        #: The traceback of the last failed reload, or ``None``.
        self.error: Optional[str] = None
        #: How many reloads succeeded (useful in tests and status bars).
        self.count = 0
        #: What the last reload changed, one ``Change`` per class that changed.
        self.changes: List[Change] = []
        #: Print what each reload changed (to standard error).
        self.verbose = True
        remember(app)

    # -- watching ------------------------------------------------------------
    def watch(self, path: Any, callback: Callable[[Path], Any]) -> None:
        """Calls ``callback(path)`` on the UI thread whenever ``path`` changes.

        Use it for files that are not Python modules, such as a layout or data file the
        app loads. The window redraws after the callback.
        """
        file = Path(path).resolve()
        self._extra.setdefault(file, []).append(callback)
        self._mtimes.setdefault(file, self._mtime(file))

    def project_modules(self) -> Dict[Path, types.ModuleType]:
        """The loaded modules whose files belong to the project, by file path."""
        found: Dict[Path, types.ModuleType] = {}
        for module in list(sys.modules.values()):
            if not isinstance(module, types.ModuleType):
                continue
            file = _module_file(module)
            if file is None or file in found:
                continue
            if any(_within(file, d) for d in self._excluded):
                continue
            if any(file == r or _within(file, r) for r in self.roots):
                found[file] = module
        return found

    @staticmethod
    def _mtime(file: Path) -> float:
        try:
            return file.stat().st_mtime_ns
        except OSError:
            return 0

    def scan(self) -> Set[Path]:
        """Checks every watched file once and returns the ones that changed."""
        changed = set()
        files = set(self.project_modules()) | set(self._extra)
        for file in files:
            mtime = self._mtime(file)
            previous = self._mtimes.get(file)
            self._mtimes[file] = mtime
            if previous is not None and mtime != previous:
                changed.add(file)
        return changed

    def start(self) -> "Reloader":
        """Starts the watcher thread and makes this the current reloader."""
        global _current
        _current = self
        self.scan()
        self._thread = threading.Thread(target=self._loop, name="pyzed-hot-reload", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        """Stops watching files."""
        global _current, _failed
        self._stop.set()
        if _current is self:
            _current = None
        if _failed is self:
            _failed = None

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            changed = self.scan()
            if changed:
                # Editors often write a file in several steps; wait for it to settle.
                time.sleep(min(self.interval, 0.1))
                changed |= self.scan()
            with self._lock:
                self._pending |= changed
                if not self._pending or self._posted:
                    continue
                try:
                    # Runs `_apply_pending` on the UI thread, then the window redraws.
                    _core.post(self._apply_pending)
                    self._posted = True
                except RuntimeError:
                    pass  # the app is not running (yet, or anymore): try again later

    def _apply_pending(self) -> Any:
        with self._lock:
            changed, self._pending = self._pending, set()
            self._posted = False
        return self.reload(changed)

    # -- reloading -------------------------------------------------------------
    def reload(self, changed: Iterable[Any]) -> Any:
        """Reloads the code in ``changed`` files now (call it on the UI thread).

        Returns what the ``on_reload`` hooks returned (commands for the runtime). Errors
        are stored in ``error`` and shown in the window instead of being raised.
        """
        global _failed
        changed = {Path(p).resolve() for p in changed}
        results: List[Any] = []
        self.changes = []
        try:
            for file in sorted(changed & set(self._extra)):
                for callback in self._extra[file]:
                    results.append(callback(file))
            modules = self.project_modules()
            touched = [modules[f] for f in changed if f in modules]
            if touched:
                results.extend(self._reload_modules(touched, modules))
        except Exception as err:  # noqa: BLE001 - shown in the window, never crash the app
            self.error = _format_error(err, self.roots[0] if self.roots else None)
            print(self.error, file=sys.stderr)
            _failed = self
            return None
        self.error = None
        if _failed is self:
            _failed = None
        self.count += 1
        commands = [r for r in results if isinstance(r, _core.Command)]
        return commands or None

    def _reload_modules(self, touched: List[types.ModuleType], modules: Dict[Path, types.ModuleType]) -> List[Any]:
        order = [m for m in sys.modules.values() if m in set(modules.values())]
        targets = self._with_dependents(set(touched), order)
        old: Dict[str, Dict[str, Any]] = {m.__name__: dict(vars(m)) for m in targets}
        global _reloading
        _reloading = True
        try:
            for module in order:
                if module in targets:
                    self._reexec(module)
        finally:
            _reloading = False
        mapping: Dict[type, type] = {}
        for module in targets:
            before = old[module.__name__]
            for name, value in vars(module).items():
                previous = before.get(name)
                if isinstance(value, type) and isinstance(previous, type) and previous is not value:
                    self._map_classes(previous, value, mapping)
                elif isinstance(value, types.FunctionType) and isinstance(previous, types.FunctionType):
                    _patch_function(previous, value)  # module functions kept elsewhere (`partial(save)`)
        # Compared before the old functions get the new code.
        touched_classes = {new for old_cls, new in mapping.items() if _fingerprint(old_cls) != _fingerprint(new)}
        changes = {new: self._update_class(old_cls, new) for old_cls, new in mapping.items()}
        for obj in self._swap_instances(mapping):
            if not any(klass in touched_classes for klass in type(obj).__mro__):
                continue
            try:
                fresh = _fresh(obj)
            except Exception as err:  # noqa: BLE001 - the reload still applies; say why the state was not updated
                print(f"pyzed: {type(obj).__qualname__}.__init__ failed while reloading its state "
                      f"({type(err).__name__}: {err}); define on_reload() or reload_init = False", file=sys.stderr)
                continue
            if fresh is not None:
                added, updated = _merge_state(obj, fresh)
            elif hasattr(obj, "__pyzed_fresh__"):
                continue  # reload_init = False
            else:
                defaults = _init_defaults(obj)
                vars(obj).update(defaults)
                added, updated = list(defaults), []
            change = changes[type(obj)]
            change.new_state.extend(n for n in added if n not in change.new_state)
            change.updated_state.extend(n for n in updated if n not in change.updated_state)
        self.changes = [c for c in changes.values() if c]
        if self.verbose:
            for change in self.changes:
                print(f"pyzed: reloaded {change}", file=sys.stderr)
        hooks = []
        for obj in [self.app, *[w for w in list(_windows) if w is not self.app]]:
            hook = getattr(obj, "on_reload", None)
            if callable(hook):
                hooks.append(hook())
        return hooks

    @staticmethod
    def _update_class(old: type, new: type) -> Change:
        """Compares two versions of a class and gives the old functions the new code."""
        change = Change(new.__qualname__)
        old_vars, new_vars = vars(old), vars(new)
        for name, value in new_vars.items():
            new_functions = _functions(value)
            if not new_functions:
                continue
            old_functions = _functions(old_vars.get(name))
            if not old_functions:
                change.added.append(name)
                continue
            if [_code_key(f.__code__) for f in old_functions] != [_code_key(f.__code__) for f in new_functions]:
                change.changed.append(name)
            for previous, current in zip(old_functions, new_functions):
                _patch_function(previous, current)
        change.removed.extend(n for n, v in old_vars.items() if _functions(v) and not _functions(new_vars.get(n)))
        return change

    @staticmethod
    def _with_dependents(touched: Set[types.ModuleType], order: List[types.ModuleType]) -> Set[types.ModuleType]:
        """``touched`` plus every project module that imports from them (transitively)."""
        imports = {m: _imported_names(m) for m in order}
        targets = set(touched)
        grew = True
        while grew:
            grew = False
            names = {m.__name__ for m in targets}
            for module in order:
                if module not in targets and imports[module] & names:
                    targets.add(module)
                    grew = True
        return targets

    @staticmethod
    def _reexec(module: types.ModuleType) -> None:
        name = module.__name__
        if name == "__main__" or getattr(module, "__spec__", None) is None:
            # The main script has no import spec: run its source again in its own
            # namespace, under a different name so the `__main__` block is skipped.
            file = _module_file(module)
            source = file.read_text(encoding="utf-8")
            code = compile(source, str(file), "exec")
            namespace = vars(module)
            namespace["__name__"] = _REPLAY_NAME
            try:
                exec(code, namespace)  # noqa: S102 - this is the user's own script
            finally:
                namespace["__name__"] = name
            for value in list(namespace.values()):
                if getattr(value, "__module__", None) == _REPLAY_NAME:
                    try:
                        value.__module__ = name
                    except (AttributeError, TypeError):
                        pass
        else:
            # A same-size edit saved within the same second as the cached bytecode
            # would otherwise load the stale .pyc.
            file = _module_file(module)
            if file is not None:
                try:
                    os.remove(importlib.util.cache_from_source(str(file)))
                except (OSError, NotImplementedError, ValueError):
                    pass
            importlib.reload(module)

    @staticmethod
    def _map_classes(old: type, new: type, mapping: Dict[type, type]) -> None:
        mapping[old] = new
        # Nested classes (a Window defined inside the App, for example).
        for name, value in vars(old).items():
            replacement = vars(new).get(name)
            if isinstance(value, type) and isinstance(replacement, type) and value is not replacement:
                if value.__qualname__.startswith(old.__qualname__ + "."):
                    Reloader._map_classes(value, replacement, mapping)

    def _swap_instances(self, mapping: Dict[type, type]) -> List[Any]:
        """Switches every live instance of an old class to its new class; returns them."""
        if not mapping:
            return []
        candidates = [self.app, *list(_windows)]
        candidates.extend(o for o in gc.get_objects() if type(o) in mapping)
        seen: Set[int] = set()
        swapped: List[Any] = []
        for obj in candidates:
            new = mapping.get(type(obj))
            if new is None or id(obj) in seen:
                continue
            seen.add(id(obj))
            try:
                obj.__class__ = new
                swapped.append(obj)
            except TypeError as err:
                print(f"pyzed: could not reload {type(obj).__qualname__} instance: {err}", file=sys.stderr)
        return swapped


def note_window(window: Any) -> None:
    """Records a drawn window so reloads reach it (called by ``Window`` while drawing)."""
    if window not in _windows:
        _windows.add(window)
        if _current is not None:
            remember(window)


def check() -> None:
    """Raises ``ReloadError`` while the last reload failed (called before each ``view()``)."""
    if _failed is not None and _failed.error:
        raise ReloadError(_failed.error)


def enable(app: Any, paths: Sequence[Any] = (), *, interval: float = 0.25) -> Reloader:
    """Starts hot reload for ``app`` (a running ``App`` instance) and returns the reloader."""
    if _current is not None:
        _current.stop()
    return Reloader(app, paths, interval=interval).start()

