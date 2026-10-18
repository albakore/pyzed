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
   (``obj.__class__ = New``). Instance attributes, and therefore your app's state, stay
   as they were; methods, ``view()`` and class attributes come from the new code.
4. The window redraws. If the new code fails to import, or ``view()`` raises, the error
   is shown in the window until you save a fix.

State is kept, so attributes that ``__init__`` sets are not created again. Give new
attributes a class-level default, or define ``on_reload(self)`` on your app or window
to migrate state after each reload (it may return a ``Command``)::

    class Notes(pz.App):
        def on_reload(self):
            if not hasattr(self, "tags"):
                self.tags = []

Files that are not Python (a form layout, a stylesheet...) can be watched too with
``Reloader.watch(path, callback)``; the callback runs on the UI thread after the file
changes and the window then redraws.
"""

from __future__ import annotations

import ast
import gc
import importlib
import importlib.util
import os
import sys
import sysconfig
import threading
import time
import traceback
import types
import weakref
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set

from . import _core

__all__ = ["Reloader", "ReloadError", "current", "enable", "enabled_by_env", "is_reloading"]

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


class ReloadError(Exception):
    """Raised by ``view()`` while the last reload failed; the window shows its message."""


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
        self._swap_instances(mapping)
        hooks = []
        for obj in [self.app, *[w for w in list(_windows) if w is not self.app]]:
            hook = getattr(obj, "on_reload", None)
            if callable(hook):
                hooks.append(hook())
        return hooks

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

    def _swap_instances(self, mapping: Dict[type, type]) -> None:
        if not mapping:
            return
        candidates = [self.app, *list(_windows)]
        candidates.extend(o for o in gc.get_objects() if type(o) in mapping)
        seen: Set[int] = set()
        for obj in candidates:
            new = mapping.get(type(obj))
            if new is None or id(obj) in seen:
                continue
            seen.add(id(obj))
            try:
                obj.__class__ = new
            except TypeError as err:
                print(f"pyzed: could not reload {type(obj).__qualname__} instance: {err}", file=sys.stderr)


def note_window(window: Any) -> None:
    """Records a drawn window so reloads reach it (called by ``Window`` while drawing)."""
    _windows.add(window)


def check() -> None:
    """Raises ``ReloadError`` while the last reload failed (called before each ``view()``)."""
    if _failed is not None and _failed.error:
        raise ReloadError(_failed.error)


def enable(app: Any, paths: Sequence[Any] = (), *, interval: float = 0.25) -> Reloader:
    """Starts hot reload for ``app`` (a running ``App`` instance) and returns the reloader."""
    if _current is not None:
        _current.stop()
    return Reloader(app, paths, interval=interval).start()

