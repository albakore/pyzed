"""The shading tools of the MCP server: the node catalog, checking a ``.pzshad`` and starting one."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .. import shading
from ..shading import nodes as _nodes


def _port(p: Any) -> Dict[str, Any]:
    out = {"name": p.name, "type": p.type}
    default = getattr(p, "default", None)
    if default is not None:
        out["default"] = default
    return out


def list_nodes(query: str = "", category: str = "") -> List[Dict[str, Any]]:
    """The sidebar's entries (``key`` is what ``Graph.add`` and a node's ``type`` + ``params`` take), with
    their node type's inputs, outputs and settings."""
    words = query.lower().split()
    out = []
    for p in _nodes.PRESETS:
        if category and p.category.lower() != category.lower():
            continue
        hay = f"{p.key} {p.title} {p.category} {p.description} {p.keywords}".lower()
        if words and not all(w in hay for w in words):
            continue
        nt = _nodes.TYPES[p.type]
        out.append({
            "key": p.key, "title": p.title, "category": p.category, "type": p.type, "params": dict(p.params),
            "description": p.description,
            "inputs": [_port(i) for i in nt.inputs], "outputs": [_port(o) for o in nt.outputs],
            "settings": [{"name": s.name, "kind": s.kind, "default": s.default,
                          **({"options": list(s.options)} if s.options else {})} for s in nt.params],
        })
    return out


def check(source: str) -> Dict[str, Any]:
    """Compiles the ``.pzshad`` JSON ``source`` and checks the WGSL with the GPU compiler (naga)."""
    graph = shading.Graph.from_json(source)
    compiled = graph.compile()
    errors = dict(compiled.errors or compiled.check())
    wgsl_error = errors.pop("wgsl", None)
    named = {}
    for node_id, message in errors.items():
        node = graph.nodes.get(node_id)
        named[node_id] = {"node": node.type if node else node_id, "error": message}
    return {"ok": not errors, "errors": named, "compiler": wgsl_error, "wgsl": compiled.code,
            "uniforms": compiled.names, "textures": sorted(compiled.textures), "uses_time": compiled.uses_time}


def template(name: str = "blank") -> str:
    """The ``.pzshad`` JSON of one of Pyzed Design's shader templates."""
    from ..designer.shader_doc import new_shader, templates

    names = [t[0] for t in templates()]
    if name not in names:
        raise ValueError(f"no template {name!r}: pick one of {', '.join(names)}")
    return new_shader(name, template=name).graph.to_json()


def templates() -> List[Dict[str, str]]:
    from ..designer.shader_doc import templates as _templates

    return [{"name": n, "title": t, "description": d} for n, t, d in _templates()]


def format_json(data: Any) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False)
