"""The timeline-animation tools of the MCP server: writing and checking ``.pzanim`` libraries."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Sequence

from .. import animation as _animation
from ..animation_player import FORMAT, LOOPS, AnimationLibrary, Clip


def properties() -> Dict[str, Any]:
    """What a track can animate, the loops and the easings."""
    return {
        "widget_properties": sorted(_animation.PROPERTIES),
        "app_attributes": "a track path without a target (':score', ':hud.hp') animates an app attribute",
        "loops": list(LOOPS),
        "easings": sorted(getattr(_animation, "EASINGS", ())),
    }


def _summary(clip: Clip) -> Dict[str, Any]:
    return {"name": clip.name, "length": clip.length, "loop": clip.loop, "targets": list(clip.targets),
            "attributes": list(clip.attributes), "calls": [c.method for c in clip.calls if isinstance(c.method, str)],
            "tracks": len(clip.tracks)}


def check(source: str) -> Dict[str, Any]:
    """Reads the JSON of a ``.pzanim`` library and reports each clip, or the first problem found."""
    try:
        data = json.loads(source)
    except json.JSONDecodeError as err:
        return {"ok": False, "error": f"not JSON: {err}"}
    if not isinstance(data, Mapping):
        return {"ok": False, "error": "a .pzanim file is a JSON object with a 'clips' list"}
    try:
        library = AnimationLibrary.from_dict(data)
    except (KeyError, TypeError, ValueError) as err:
        return {"ok": False, "error": str(err) if not isinstance(err, KeyError) else f"missing {err}"}
    return {"ok": True, "name": library.name, "clips": [_summary(c) for c in library]}


def new(clips: Sequence[Mapping[str, Any]], name: str = "") -> str:
    """The ``.pzanim`` JSON of ``clips``: each ``{"name", "length"?, "loop"?, "tracks": [{"path", "keys"}],
    "calls"?: [{"time", "method", "args"?}]}``; keys are ``{time: value}`` or ``[[time, value, easing?]]``."""
    built: List[Clip] = []
    for spec in clips:
        tracks = []
        for track in spec.get("tracks", ()):
            keys = track.get("keys", ())
            if isinstance(keys, Mapping):  # JSON object keys are strings
                keys = {float(t): v for t, v in keys.items()}
            elif isinstance(keys, list):
                keys = [tuple(k) if isinstance(k, list) else k for k in keys]
            tracks.append({**track, "keys": keys})
        built.append(Clip.from_dict({**spec, "tracks": tracks}))
    library = AnimationLibrary(built, name=name)
    return json.dumps(library.to_dict(), indent=2, ensure_ascii=False) + "\n"


__all__ = ["FORMAT", "check", "new", "properties"]
