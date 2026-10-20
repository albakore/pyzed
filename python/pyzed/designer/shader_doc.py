"""A shader graph (``.pzshad``) open in Pyzed Design: the graph, its selection, undo and every editing command.

Like ``Document`` for forms, the shader view only turns clicks and keys into calls on
``ShaderDocument``, so everything can be tested (and scripted) without a window. It is a
``Document`` too, so tabs, Save, Save as and the window title treat it like a form; its
``form`` is an empty stand-in that only carries the shader's name.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from .. import shading
from ..shading import Graph, GraphError
from ..shading import layout as _layout
from .document import Document
from .history import History
from .model import Form

SUFFIX = shading.SUFFIX
#: The ``format`` of nodes copied to the system clipboard.
CLIPBOARD_FORMAT = "pyzed.shader-nodes/1"
#: The smallest zoom "fit" goes to: below it the node previews are too small to read.
FIT_MIN_ZOOM = 0.6
#: How far pasted and duplicated nodes move from the originals.
PASTE_OFFSET = 40.0

_clipboard: Dict[str, Any] = {}


class ShaderDocument(Document):
    """A shader graph being edited. ``selection`` holds node ids; ``variable`` is the variable picked in the
    outline (its settings show in the Properties panel)."""

    is_shader = True
    suffix = SUFFIX

    def __init__(self, graph: Optional[Graph] = None, path: Optional[Union[str, Path]] = None) -> None:
        graph = graph if graph is not None else shading.new(Path(path).stem if path else "shader")
        super().__init__(Form(name=graph.name, title=graph.name), path, code="")
        self.graph = graph
        if self.path is not None:
            graph.path = self.path
        self.history = History(graph)  # type: ignore[arg-type] - a Graph snapshots like a Form
        #: Selected node ids, primary first.
        self.selection: List[str] = []
        #: The variable whose settings the Properties panel shows (``None``: nodes or the shader).
        self.variable: Optional[str] = None
        #: Where the graph is scrolled to (view pixels) and how big it is drawn.
        self.pan: Tuple[float, float] = (60.0, 60.0)
        self.zoom = 1.0
        #: The tab shown: ``"graph"``, ``"preview"`` or ``"code"`` (the generated WGSL).
        self.tab = "graph"
        self._checked: Optional[Tuple[int, Dict[str, str]]] = None
        #: Fit the graph in view the first time the canvas is drawn (its size is known then).
        self.fit_pending = True

    # -- files ----------------------------------------------------------------------
    @classmethod
    def open(cls, path: Union[str, Path]) -> "ShaderDocument":  # type: ignore[override]
        """Opens the ``.pzshad`` at ``path``."""
        path = Path(path)
        doc = cls(shading.load_graph(path), path)
        doc.fit()
        return doc

    @property
    def code_path(self) -> Optional[Path]:
        """Shaders have no handlers module."""
        return None

    @property
    def display_name(self) -> str:
        return self.path.name if self.path else f"{self.graph.name}{SUFFIX}"

    def save(self, path: Optional[Union[str, Path]] = None) -> Path:
        """Writes the graph to its file (or to ``path``, adding ``.pzshad`` when it has no suffix)."""
        if path is not None:
            self.path = Path(path) if Path(path).suffix else Path(path).with_suffix(SUFFIX)
        if self.path is None:
            raise ValueError("this shader has no file yet; pass a path")
        if self.graph.name in ("shader", "") and self.path.stem:
            self.graph.name = self.path.stem
            self.form.name = self.graph.name
        self.graph.save(self.path)
        self.dirty = False
        return self.path

    # -- changes and undo --------------------------------------------------------------
    def commit(self, group: Optional[str] = None) -> None:
        """Records an undo step after a change (``group`` merges repeated changes of one field)."""
        self.graph.touch()
        if self.history.push(self.graph, group):  # type: ignore[arg-type]
            self.dirty = True
        self.revision += 1

    def _restore(self, graph: Optional[Any]) -> bool:  # type: ignore[override]
        if graph is None:
            return False
        graph.path = self.path
        self.graph = graph
        self.form.name = graph.name
        self.selection = [n for n in self.selection if n in graph.nodes]
        if self.variable is not None and graph.variable(self.variable) is None:
            self.variable = None
        self.dirty = True
        self.revision += 1
        return True

    # -- selection -------------------------------------------------------------------------
    @property
    def selected(self) -> List[Any]:  # type: ignore[override]
        """The selected nodes, primary first."""
        return [self.graph.nodes[n] for n in self.selection if n in self.graph.nodes]

    @property
    def primary(self) -> None:  # type: ignore[override]
        """Forms have a primary control; shaders don't (the designer's form tools stay off)."""
        return None

    @property
    def node(self) -> Optional[shading.Node]:
        """The primary selected node, or ``None``."""
        nodes = self.selected
        return nodes[0] if nodes else None

    def is_selected(self, node_id: str) -> bool:
        return node_id in self.selection

    def select(self, ids: Union[str, Iterable[str], None], *, add: bool = False) -> None:
        """Selects nodes by id (``None`` for none); with ``add`` each id is toggled. Picks no variable."""
        if ids is None:
            ids = []
        elif isinstance(ids, str):
            ids = [ids]
        ids = [i for i in ids if i in self.graph.nodes]
        if add:
            for i in ids:
                if i in self.selection:
                    self.selection.remove(i)
                else:
                    self.selection.append(i)
        else:
            self.selection = list(dict.fromkeys(ids))
        if self.selection:
            self.variable = None

    def select_all(self) -> None:
        self.select(list(self.graph.nodes))

    def select_variable(self, name: Optional[str]) -> None:
        """Shows the variable ``name`` in the Properties panel (and selects no node)."""
        self.variable = name if name is None or self.graph.variable(name) is not None else None
        if self.variable is not None:
            self.selection = []

    # -- nodes -------------------------------------------------------------------------------
    def add_node(self, kind: str, at: Optional[Tuple[float, float]] = None, **values: Any) -> str:
        """Adds a node: a type id, a sidebar entry key (``func:sin``) or name (``sin``), at ``at`` (graph
        coordinates). Selects it and returns its id."""
        type_, params = _preset(kind)
        x, y = at if at is not None else self.center()
        ref = self.graph.add(type_, x=x, y=y, **{**params, **values})
        self.select(ref.id)
        self.commit()
        return ref.id

    def add_parameter(self, name: str, at: Optional[Tuple[float, float]] = None) -> Optional[str]:
        """Adds a node that reads the variable ``name``; returns its id."""
        if self.graph.variable(name) is None:
            return None
        return self.add_node("parameter", at, name=name)

    def remove(self, ids: Optional[Iterable[str]] = None) -> int:
        """Removes nodes (the selected ones by default); the Output node stays unless it is the only one
        selected... it can always be added back from the sidebar. Returns how many were removed."""
        ids = list(self.selection if ids is None else ids)
        for i in ids:
            self.graph.remove(i)
        self.selection = [i for i in self.selection if i in self.graph.nodes]
        if ids:
            self.commit()
        return len(ids)

    def delete(self) -> None:
        """Deletes the selected nodes, or the variable shown in the Properties panel."""
        if self.selection:
            self.remove()
        elif self.variable is not None:
            self.remove_variable(self.variable)

    def move(self, ids: Iterable[str], dx: float, dy: float) -> None:
        """Moves nodes by ``(dx, dy)`` graph pixels (no undo step: call ``commit`` when the drag ends)."""
        for i in ids:
            node = self.graph.nodes.get(i)
            if node is not None:
                node.x += dx
                node.y += dy
        self.graph.touch()

    def nudge(self, dx: float, dy: float) -> None:
        """Moves the selected nodes by ``(dx, dy)`` with an undo step."""
        if self.selection:
            self.move(self.selection, dx * 10, dy * 10)
            self.commit("nudge")

    def connect(self, src: str, out: str, dst: str, inp: str) -> Optional[str]:
        """Wires an output to an input; returns ``None``, or why it can't be wired."""
        try:
            self.graph.connect(src, out, dst, inp)
        except GraphError as err:
            return str(err)
        self.commit()
        return None

    def disconnect(self, dst: str, inp: str) -> bool:
        if self.graph.disconnect(dst, inp):
            self.commit()
            return True
        return False

    def disconnect_all(self, node_id: str) -> None:
        """Removes every wire into and out of a node."""
        before = len(self.graph.links)
        self.graph.links = [l for l in self.graph.links if l.src != node_id and l.dst != node_id]
        if len(self.graph.links) != before:
            self.commit()

    def set_input(self, node_id: str, name: str, value: Any) -> None:
        """Sets the value an unconnected input takes."""
        self.graph.set_input(node_id, name, value)
        self.commit(f"input:{node_id}:{name}")

    def set_param(self, node_id: str, name: str, value: Any) -> Optional[str]:
        """Changes a setting of a node; returns why it can't, or ``None``."""
        try:
            self.graph.set_param(node_id, name, value)
        except (GraphError, TypeError, ValueError) as err:
            return str(err)
        self.commit(f"param:{node_id}:{name}")
        return None

    def set_title(self, node_id: str, title: str) -> None:
        self.graph.nodes[node_id].title = title
        self.commit(f"title:{node_id}")

    def toggle_preview(self, node_id: str) -> None:
        node = self.graph.nodes[node_id]
        node.preview = not node.preview
        self.commit()

    def arrange(self) -> None:
        """Lines the nodes up in columns."""
        self.graph.arrange()
        self.commit()
        self.fit()

    # -- clipboard -------------------------------------------------------------------------
    @property
    def clipboard(self) -> Dict[str, Any]:  # type: ignore[override]
        return _clipboard

    def _copied(self, ids: List[str]) -> Dict[str, Any]:
        nodes = [self.graph.nodes[i].to_dict() for i in ids if i in self.graph.nodes]
        keep = {n["id"] for n in nodes}
        links = [l.to_dict() for l in self.graph.links if l.src in keep and l.dst in keep]
        variables = [v.to_dict() for v in self.graph.variables
                     if any(n["type"] == "parameter" and n.get("params", {}).get("name") == v.name for n in nodes)]
        return {"format": CLIPBOARD_FORMAT, "nodes": nodes, "links": links, "variables": variables}

    def copy(self) -> int:
        """Copies the selected nodes (and the wires between them); returns how many."""
        if not self.selection:
            return 0
        _clipboard.clear()
        _clipboard.update(self._copied(self.selection))
        return len(_clipboard["nodes"])

    def cut(self) -> int:
        count = self.copy()
        if count:
            self.remove()
        return count

    def clipboard_text(self) -> str:
        """The copied nodes as text for the system clipboard."""
        return json.dumps(_clipboard)

    def paste_text(self, text: str) -> Optional[List[str]]:
        """Pastes nodes copied as text (in this or another Pyzed Design window); ``None`` if ``text`` holds none."""
        try:
            data = json.loads(text)
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict) or data.get("format") != CLIPBOARD_FORMAT:
            return None
        return self._paste(data)

    def paste(self) -> List[str]:
        return self._paste(_clipboard) if _clipboard else []

    def duplicate(self) -> List[str]:
        """Copies the selected nodes next to them."""
        if not self.selection:
            return []
        return self._paste(self._copied(self.selection))

    def _paste(self, data: Dict[str, Any]) -> List[str]:
        mapping: Dict[str, str] = {}
        g = self.graph
        for v in data.get("variables") or []:
            if g.variable(v["name"]) is None:
                try:
                    g.variables.append(shading.Variable.from_dict(v))
                except (KeyError, ValueError):
                    pass
        for raw in data.get("nodes") or []:
            if raw.get("type") == "output" and g.output_node is not None:  # a shader has one Output
                continue
            node = shading.Node.from_dict(raw)
            node.id = g.new_id()
            node.x += PASTE_OFFSET
            node.y += PASTE_OFFSET
            mapping[str(raw["id"])] = node.id
            g.nodes[node.id] = node
        for raw in data.get("links") or []:
            try:
                g.connect(mapping[str(raw["from"])], raw["out"], mapping[str(raw["to"])], raw["in"])
            except (KeyError, GraphError):
                continue
        ids = list(mapping.values())
        if ids:
            self.selection = ids
            self.variable = None
            self.commit()
            data_nodes = data.get("nodes") or []
            for raw in data_nodes:  # the next paste lands a step further
                raw["x"] = raw.get("x", 0) + PASTE_OFFSET
                raw["y"] = raw.get("y", 0) + PASTE_OFFSET
        return ids

    # -- variables ------------------------------------------------------------------------------
    def new_variable_name(self, base: str = "value") -> str:
        n = 1
        while self.graph.variable(f"{base}{n}") is not None:
            n += 1
        return f"{base}{n}"

    def add_variable(self, type_: str = "float", name: Optional[str] = None, **options: Any) -> str:
        """Adds a variable (mutable unless ``mutable=False``), shows it and returns its name."""
        base = {"color": "color", "texture": "texture", "bool": "flag"}.get(type_, "value")
        name = name or self.new_variable_name(base)
        if type_ in ("float", "int") and "min" not in options:
            options.update({"min": 0, "max": 1 if type_ == "float" else 10})
        value = options.pop("value", 1.0 if type_ == "float" else None)
        self.graph.add_variable(name, type_, value, **options)
        self.select_variable(name)
        self.commit()
        return name

    def set_variable(self, name: str, /, **changes: Any) -> Optional[str]:
        """Changes a variable; returns why it can't, or ``None``. Renaming keeps it shown."""
        try:
            var = self.graph.set_variable(name, **changes)
        except (GraphError, TypeError, ValueError) as err:
            return str(err)
        if self.variable == name:
            self.variable = var.name
        self.commit(f"var:{var.name}:{','.join(sorted(changes))}")
        return None

    def remove_variable(self, name: str) -> None:
        """Removes a variable and the nodes that read it."""
        self.graph.remove_variable(name)
        if self.variable == name:
            self.variable = None
        self.selection = [i for i in self.selection if i in self.graph.nodes]
        self.commit()

    # -- shader settings ---------------------------------------------------------------------------
    def set_name(self, name: str) -> None:
        self.graph.name = name
        self.form.name = name
        self.commit("name")

    def set_preview(self, key: str, value: Any) -> None:
        """Changes how the shader is drawn by default: ``width``, ``height``, ``fallback``, ``animate``."""
        self.graph.preview[key] = value
        self.commit(f"preview:{key}")

    def set_description(self, text: str) -> None:
        self.graph.description = text
        self.commit("description")

    # -- view ----------------------------------------------------------------------------------------
    def to_graph(self, x: float, y: float) -> Tuple[float, float]:
        """A point of the canvas (view pixels) in graph coordinates."""
        px, py = self.pan
        return ((x - px) / self.zoom, (y - py) / self.zoom)

    def to_view(self, x: float, y: float) -> Tuple[float, float]:
        """A point of the graph in canvas pixels."""
        px, py = self.pan
        return (x * self.zoom + px, y * self.zoom + py)

    #: The size of the canvas the last time it was drawn (for centering and fitting).
    view_size: Tuple[float, float] = (900.0, 600.0)

    def center(self) -> Tuple[float, float]:
        """The middle of what the canvas shows, in graph coordinates (where new nodes go)."""
        w, h = self.view_size
        x, y = self.to_graph(w / 2, h / 2)
        return (x - _layout.WIDTH / 2, y - 60)

    def set_zoom(self, zoom: float, around: Optional[Tuple[float, float]] = None) -> None:
        """Zooms to ``zoom`` (0.3 to 2) keeping the point ``around`` (view pixels; the middle by default) still."""
        zoom = max(0.3, min(2.0, zoom))
        cx, cy = around if around is not None else (self.view_size[0] / 2, self.view_size[1] / 2)
        gx, gy = self.to_graph(cx, cy)
        self.zoom = zoom
        self.pan = (cx - gx * zoom, cy - gy * zoom)

    def scroll(self, dx: float, dy: float) -> None:
        """Pans the view by ``(dx, dy)`` view pixels."""
        self.pan = (self.pan[0] + dx, self.pan[1] + dy)

    def bounds(self) -> Optional[Tuple[float, float, float, float]]:
        """The box around every node, in graph coordinates."""
        g = self.graph
        if not g.nodes:
            return None
        boxes = [(n.x, n.y, *_layout.size(g, n)) for n in g.nodes.values()]
        x0 = min(b[0] for b in boxes)
        y0 = min(b[1] for b in boxes)
        x1 = max(b[0] + b[2] for b in boxes)
        y1 = max(b[1] + b[3] for b in boxes)
        return (x0, y0, x1 - x0, y1 - y0)

    def fit(self, whole: bool = False) -> None:
        """Zooms and pans so every node is in view; a big graph opens at a zoom its previews can be read at,
        showing its Output end, unless ``whole`` (the Fit button) zooms out as far as it takes."""
        box = self.bounds()
        if box is None:
            self.pan, self.zoom = (60.0, 60.0), 1.0
            return
        x, y, w, h = box
        vw, vh = self.view_size
        zoom = min(1.0, (vw - 80) / max(w, 1), (vh - 80) / max(h, 1))
        if zoom >= FIT_MIN_ZOOM or whole:
            zoom = max(0.3, zoom)
            self.zoom = zoom
            self.pan = ((vw - w * zoom) / 2 - x * zoom, (vh - h * zoom) / 2 - y * zoom)
            return
        # Too big to read whole: show its end, where the Output is, at a zoom the previews are still clear.
        self.zoom = zoom = FIT_MIN_ZOOM
        out = self.graph.output_node
        if out is not None:
            ow, oh = _layout.size(self.graph, out)
            cx, cy = out.x + ow, out.y + oh / 2
        else:
            cx, cy = x + w, y + h / 2
        self.pan = (vw - 60 - cx * zoom, vh / 2 - cy * zoom)

    def node_at(self, x: float, y: float) -> Optional[str]:
        """The top-most node under the graph point ``(x, y)``."""
        g = self.graph
        for node in reversed(list(g.nodes.values())):
            w, h = _layout.size(g, node)
            if node.x <= x <= node.x + w and node.y <= y <= node.y + h:
                return node.id
        return None

    def port_at(self, x: float, y: float, radius: float = 12.0) -> Optional[Tuple[str, str, bool]]:
        """``(node id, port, is_output)`` of the port nearest the graph point ``(x, y)`` within ``radius``
        view pixels."""
        g = self.graph
        best: Optional[Tuple[float, Tuple[str, str, bool]]] = None
        limit = radius / self.zoom
        for node in g.nodes.values():
            inputs, outputs = g.ports(node)
            for output, ports in ((False, inputs), (True, outputs)):
                for p in ports:
                    px, py = _layout.port_position(g, node, p.name, output)
                    d = abs(px - x) + abs(py - y)
                    if d <= limit * 1.5 and (best is None or d < best[0]):
                        best = (d, (node.id, p.name, output))
        return best[1] if best else None

    # -- problems ---------------------------------------------------------------------------------------
    def diagnostics(self) -> Dict[str, str]:
        """The problems of the graph by node id (``"graph"`` for the whole), checked with the GPU compiler.
        Cached until the graph changes."""
        rev = self.graph.revision
        if self._checked is not None and self._checked[0] == rev:
            return self._checked[1]
        compiled = shading.compile(self.graph)
        errors = dict(compiled.errors)
        if not errors:
            errors = dict(compiled.check())
        self._checked = (rev, errors)
        return errors


def _preset(kind: str) -> Tuple[str, Dict[str, Any]]:
    """A sidebar entry's key (``func:sin``), a node type or an entry name, as ``(type, settings)``."""
    from ..shading.graph import _resolve_type

    return _resolve_type(kind)


def new_shader(name: str = "shader", path: Optional[Union[str, Path]] = None,
               template: Optional[Union[str, Path]] = None) -> ShaderDocument:
    """A new shader document: from a template (a ``.pzshad`` path or the name of one in the designer's
    ``templates/shaders``) or the starting gradient."""
    graph = None
    if template:
        source = Path(template)
        if not source.is_file():
            source = TEMPLATES_DIR / f"{template}{SUFFIX}"
        if source.is_file():
            graph = shading.load_graph(source)
            graph.path = None
            graph.name = name
    graph = graph or shading.new(name)
    doc = ShaderDocument(graph, path)
    doc.fit()
    return doc


#: The shader templates of the "New" dialog.
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates" / "shaders"


def templates() -> List[Tuple[str, str, str]]:
    """``(name, title, description)`` of each shader template, in order."""
    out = []
    for path in sorted(TEMPLATES_DIR.glob(f"*{SUFFIX}")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append((path.stem, str(data.get("title") or path.stem.replace("_", " ").capitalize()),
                    str(data.get("description", ""))))
    order = {"blank": 0}
    out.sort(key=lambda t: (order.get(t[0], 1), t[1]))
    return out
