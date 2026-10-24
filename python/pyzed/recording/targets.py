"""What a job records: an app in a file or module, a form made with the designer, or a snippet.

A target is written as text, so job files and the command line can name it:

* ``app.py`` / ``app.py:Counter``: a ``pz.App`` subclass (or instance) in a Python file, or a
  function returning an App or a widget. Without a name, the file's ``app``, ``App`` or the last
  ``pz.App`` subclass it defines.
* ``package.module:Counter``: the same, from an importable module.
* ``login.pzform`` / ``card.pzcomp``: a form or component made with the designer, run as
  ``pyzed run`` runs it.
* ``code:ui.button("Save", None)``: a snippet whose last expression is the widget (``pz``, ``ui``
  and ``draw`` are imported, other free names are do-nothing callbacks).
"""

from __future__ import annotations

import ast
import builtins
import hashlib
import importlib
import importlib.util
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

__all__ = ["as_app", "fingerprint", "load", "snippet_widget"]


def snippet_widget(code: str) -> Callable[[], Any]:
    """A function that runs ``code`` and returns its last expression (the widget)."""
    from .. import draw, ui
    import pyzed as pz

    tree = ast.parse(code)
    *body, last = tree.body
    if not isinstance(last, ast.Expr):
        raise ValueError("the snippet must end with an expression (the widget)")

    def build():
        ns: dict = {"pz": pz, "ui": ui, "draw": draw}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id not in ns and not hasattr(builtins, node.id):
                ns[node.id] = lambda *a, **k: None
        exec(compile(ast.Module(body=body, type_ignores=[]), "snippet.py", "exec"), ns)
        return eval(compile(ast.Expression(last.value), "snippet.py", "eval"), ns)

    return build


def as_app(target: Any, theme_name: Optional[str] = None, bg: Optional[str] = "editor", padding: float = 24) -> Any:
    """An ``App`` for ``target``: an App (instance or class) or a function returning an App or the
    widget (shown centered on the theme's ``bg`` color)."""
    import pyzed as pz

    if isinstance(target, type):
        target = target()
    if not isinstance(target, pz.App) and callable(target):
        made = target()
        if isinstance(made, pz.App):
            target = made
        else:
            build = target
            first = [made]

            class Clip(pz.App):
                theme = pz.themes.get(theme_name or "Pyzed Dark")

                def view(self):
                    widget = first.pop() if first else build()
                    if bg is None:
                        return widget
                    t = self.resolved_theme()
                    return pz.container(widget, center=True, padding=padding, width="fill", height="fill",
                                        bg=getattr(t, bg))

            return Clip()
    if not isinstance(target, pz.App):
        raise TypeError("record a pz.App or a function that returns an App or a widget")
    if theme_name:
        target.theme = pz.themes.get(theme_name)
    return target


def _module_from_file(path: Path) -> Any:
    folder = str(path.parent.resolve())
    if folder not in sys.path:
        sys.path.insert(0, folder)
    name = f"_pyzed_record_{path.stem}_{hashlib.sha1(str(path.resolve()).encode()).hexdigest()[:8]}"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"can't load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _pick(module: Any, attr: Optional[str]) -> Any:
    import pyzed as pz

    if attr:
        obj = module
        for part in attr.split("."):
            obj = getattr(obj, part)
        return obj
    for name in ("app", "App", "main_app"):
        obj = getattr(module, name, None)
        if isinstance(obj, pz.App) or (isinstance(obj, type) and issubclass(obj, pz.App) and obj is not pz.App):
            return obj
    found = [v for v in vars(module).values()
             if isinstance(v, type) and issubclass(v, pz.App) and v.__module__ == module.__name__]
    if not found:
        raise LookupError(f"{module.__name__} defines no pz.App (name one: file.py:MyApp)")
    return found[-1]


def _split(spec: str) -> Tuple[str, str]:
    """``"app.py:Counter"`` as ``("app.py", "Counter")``, keeping a Windows drive (``C:\\app.py``) whole."""
    drive = spec[:2] if re.match(r"^[A-Za-z]:[\\/]", spec) else ""
    path, _, attr = spec[len(drive):].partition(":")
    return drive + path, attr


def _resolve(path: str, base: Optional[Path]) -> Path:
    p = Path(path).expanduser()
    return base / p if base is not None and not p.is_absolute() else p


def load(spec: str, base: Optional[Path] = None) -> Callable[[], Any]:
    """A function that makes a fresh App for ``spec`` (see the module's docs) each time it's called.
    Relative paths are relative to ``base`` (the job file's folder)."""
    if spec.startswith("code:"):
        build = snippet_widget(spec[5:])
        return lambda: build
    path_part, attr = _split(spec)
    path = _resolve(path_part, base)
    if path.suffix in (".pzform", ".pzcomp"):
        if not path.exists():
            raise FileNotFoundError(path)

        def form(theme: Optional[str] = None) -> Any:
            from ..designer.runtime import open_form

            # A form derives its theme (accent, fonts, style) from a base one: preview it with `theme`.
            before = os.environ.get("PYZED_PREVIEW_THEME")
            if theme:
                os.environ["PYZED_PREVIEW_THEME"] = theme
            try:
                instance = open_form(path)
            finally:
                if before is None:
                    os.environ.pop("PYZED_PREVIEW_THEME", None)
                else:
                    os.environ["PYZED_PREVIEW_THEME"] = before
            runtime = getattr(instance, "runtime", None)
            if runtime is not None and hasattr(runtime, "load"):
                runtime.load()
            return instance

        form.themed = True  # type: ignore[attr-defined]  # takes the theme itself (a form derives its own)
        return form
    if path.suffix == ".py" or path.exists():
        if not path.exists():
            raise FileNotFoundError(path)
        module = _module_from_file(path)
    else:
        module = importlib.import_module(path_part)
    obj = _pick(module, attr or None)

    def make() -> Any:
        return obj

    return make


def fingerprint(spec: str, base: Optional[Path] = None) -> str:
    """A hash of what ``spec`` reads (the file's bytes, or the snippet), so a batch can skip outputs
    whose target didn't change."""
    if spec.startswith("code:"):
        return hashlib.sha256(spec.encode()).hexdigest()[:16]
    name, attr = _split(spec)
    path = _resolve(name, base)
    h = hashlib.sha256(f"{path.resolve() if path.exists() else name}:{attr}".encode())
    if path.is_file():
        h.update(path.read_bytes())
        sidecar = path.with_suffix(".py")  # a form's code
        if sidecar != path and sidecar.is_file():
            h.update(sidecar.read_bytes())
    return h.hexdigest()[:16]
