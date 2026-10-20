"""Using a shader graph in an app: load a ``.pzshad``, change its variables, draw it.

    from pyzed import shading

    fire = shading.load("shaders/fire.pzshad")

    def view(self):
        fire["speed"] = self.speed                 # a mutable variable: no recompiling
        return fire.widget(width=320, height=200)  # or pz.shader(fire, ...)

``pz.shader("shaders/fire.pzshad", uniforms={"speed": 2})`` works too. A loaded shader
reloads by itself when its file changes, so editing it in Pyzed Design shows up in a
running app.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from .compiler import Compiled, compile as _compile
from .graph import Graph, GraphError, load as _load_graph


class Shader:
    """A shader graph ready to draw, with its own values for the graph's variables."""

    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        #: Values set with ``set`` (or ``shader[name] = value``), by variable name.
        self.values: Dict[str, Any] = {}
        self._mtime: Optional[float] = _mtime(graph.path)

    def __repr__(self) -> str:
        return f"<Shader {self.graph.name!r}>"

    @property
    def name(self) -> str:
        return self.graph.name

    @property
    def variables(self) -> Dict[str, Any]:
        """Every variable's current value, by name."""
        return {v.name: self.values.get(v.name, v.value) for v in self.graph.variables}

    def set(self, name: Optional[str] = None, value: Any = None, **values: Any) -> "Shader":
        """Sets variables: ``set("speed", 2)`` or ``set(speed=2, tint="#ff0000")``. Mutable ones only change
        what the shader is drawn with; constants rebuild its code."""
        if name is not None:
            values[name] = value
        for key, v in values.items():
            if self.graph.variable(key) is None:
                raise GraphError(f"{self.graph.name} has no variable {key!r} (it has "
                                 f"{', '.join(v.name for v in self.graph.variables) or 'none'})")
            self.values[key] = v
        return self

    def get(self, name: str) -> Any:
        """The current value of a variable."""
        var = self.graph.variable(name)
        if var is None:
            raise GraphError(f"{self.graph.name} has no variable {name!r}")
        return self.values.get(name, var.value)

    def __getitem__(self, name: str) -> Any:
        return self.get(name)

    def __setitem__(self, name: str, value: Any) -> None:
        self.set(name, value)

    def reload(self) -> bool:
        """Reads the file again if it changed since it was loaded; returns whether it did."""
        path = self.graph.path
        mtime = _mtime(path)
        if path is None or mtime is None or mtime == self._mtime:
            return False
        try:
            graph = _load_graph(path)
        except (OSError, ValueError, KeyError):
            return False
        self.graph = graph
        self._mtime = mtime
        return True

    def compiled(self) -> Compiled:
        """The code and uniforms for the current values (constants that changed are built into the code)."""
        self.reload()
        consts = {k: v for k, v in self.values.items()
                  if (var := self.graph.variable(k)) is not None and not var.mutable}
        return _compile(self.graph, values=consts or None)

    @property
    def wgsl(self) -> str:
        """The WGSL code of the shader."""
        return self.compiled().code

    def __pyzed_shader__(self, uniforms: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any], Dict[str, str],
                                                                                 Dict[str, Any]]:
        """What ``pz.shader`` draws: ``(code, uniforms, textures, defaults)`` with ``uniforms`` given as
        variable names (``{"speed": 2}``)."""
        compiled = self.compiled()
        values = {**{k: v for k, v in self.values.items() if k in compiled.names}, **(uniforms or {})}
        unknown = [k for k in (uniforms or {}) if self.graph.variable(k) is None]
        if unknown:
            raise GraphError(f"{self.graph.name} has no variable {unknown[0]!r}")
        preview = self.graph.preview
        defaults: Dict[str, Any] = {}
        if not compiled.uses_time:
            defaults["animate"] = False
        if preview.get("animate") is False:
            defaults["animate"] = False
        if preview.get("fallback"):
            defaults["fallback"] = preview["fallback"]
        return compiled.code, compiled.uniform_values(values), compiled.textures, defaults

    def widget(self, *, width: Any = None, height: Any = None, **options: Any) -> Any:
        """A ``pz.shader`` widget drawing this shader. Keyword arguments named like a variable set it for this
        widget only; the rest (``animate``, ``time``, ``fallback``) go to ``pz.shader``."""
        import pyzed as pz

        uniforms = {k: options.pop(k) for k in list(options) if self.graph.variable(k) is not None}
        return pz.shader(self, uniforms=uniforms, width=width, height=height, **options)


def _mtime(path: Optional[Path]) -> Optional[float]:
    if path is None:
        return None
    try:
        return Path(path).stat().st_mtime
    except OSError:
        return None


_LOADED: Dict[str, Shader] = {}


def load(path: Union[str, Path], *, fresh: bool = False) -> Shader:
    """The shader in a ``.pzshad`` file. The same path gives the same ``Shader`` (so calling this in
    ``view`` is cheap) unless ``fresh``; it reloads by itself when the file changes."""
    key = str(Path(path).resolve())
    shader = None if fresh else _LOADED.get(key)
    if shader is None:
        shader = Shader(_load_graph(path))
        if not fresh:
            _LOADED[key] = shader
    return shader


def widget(source: Union[str, Path, Graph, Shader], **options: Any) -> Any:
    """``load(source).widget(**options)``: a ``.pzshad`` drawn as a widget (``source`` can be a ``Graph``)."""
    if isinstance(source, Graph):
        source = Shader(source)
    elif not isinstance(source, Shader):
        source = load(source)
    return source.widget(**options)


def resolve(source: Any) -> Optional[Shader]:
    """The ``Shader`` for what ``pz.shader`` was given, or ``None`` when it is WGSL code."""
    if isinstance(source, Shader):
        return source
    if isinstance(source, Graph):
        return Shader(source)
    if isinstance(source, Path) or (isinstance(source, str) and source.strip().endswith(".pzshad")
                                    and "\n" not in source):
        return load(source)
    return None


def run_file(path: Union[str, Path]) -> None:
    """``pyzed run fire.pzshad``: the shader filling a window (see ``app``)."""
    from ..app import run as run_app

    run_app(app(path))


def app(path: Union[str, Path]) -> Any:
    """An app that shows the shader at ``path`` filling its window, with a slider for each mutable number
    (``V`` shows or hides them). Saving the file in Pyzed Design updates the window."""
    from .. import _core
    from ..app import App

    shader = load(path, fresh=True)
    preview = shader.graph.preview

    class ShaderApp(App):
        title = f"{shader.name} — Pyzed"
        size = (int(preview.get("width") or 640), int(preview.get("height") or 400))
        show_variables = False

        def subscriptions(self) -> Any:
            return [_core.every(0.5, shader.reload, key="pzshad-reload")]

        def on_key(self, combo: str) -> None:
            if combo == "v":
                self.show_variables = not self.show_variables

        def view(self) -> Any:
            art = shader.widget(width="fill", height="fill")
            mutable = [v for v in shader.graph.variables if v.mutable and v.type in ("float", "int")]
            if not self.show_variables or not mutable:
                return art
            rows = []
            for v in mutable:
                low = v.min if v.min is not None else 0.0
                high = v.max if v.max is not None else max(1.0, float(v.value or 0) * 2)
                rows.append(_core.row([
                    _core.text(v.name, size=12, color="#ffffff", font="mono", width=90),
                    _core.slider(float(low), float(high), float(shader[v.name]),
                                 on_change=lambda value, name=v.name: shader.set(name, value), width=180),
                ], spacing=8, align="center"))
            panel = _core.container(_core.column(rows, spacing=6), padding=10, bg="#000000aa", radius=8)
            return _core.stack([art, _core.container(panel, padding=12)], width="fill", height="fill")

    return ShaderApp()
