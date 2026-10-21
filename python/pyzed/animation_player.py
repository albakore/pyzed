"""Timeline animations, like Godot's AnimationPlayer: clips with tracks, keys and method calls.

A ``Clip`` is a timeline (``length`` seconds) whose ``tracks`` change one property each,
key by key, and whose ``calls`` run methods at given times::

    intro = pz.Clip("intro", length=1.2, tracks=[
        pz.Track("card:opacity", {0: 0, 0.4: 1}),
        pz.Track("card:y", [(0, 24, "ease_out_cubic"), (0.4, 0)]),
        pz.Track("title:scale", {0.3: 0.8, 0.6: 1.1, 0.8: 1}),
        pz.Track(":score", {0.4: 0, 1.2: 1500}),          # an attribute of the app
    ], calls=[pz.Call(1.2, "play_sound", "ding")])

A track's path is ``"target:property"``:

- ``"card:opacity"`` animates a widget property (``pz.animation.PROPERTIES``: opacity, x, y,
  scale, rotate, blur, colors, radius, glow, width, height, padding, font_size...) of every
  widget that plays the ``card`` target, natively at full frame rate.
- ``":score"`` (no target) animates an attribute of the app (``":player.hp"`` follows dots),
  so any parameter of any widget can be animated: use the attribute in ``view()``.

An ``AnimationPlayer`` plays clips. Keep it on the app and give widgets their target::

    class Game(pz.App):
        def __init__(self):
            self.score = 0
            self.player = pz.AnimationPlayer(intro, autoplay="intro")

        def view(self):
            return pz.column([
                pz.text("Level 1").animate(self.player["title"]),
                pz.text(f"{self.score:.0f}").style(...).animate(self.player["card"]),
                ui.button("Replay", lambda: self.player.play("intro", restart=True)),
            ])

``play``, ``play_backwards``, ``pause``, ``resume``, ``stop``, ``seek``, ``queue`` and
``speed`` control it; ``on_finished`` and ``on_started`` say when clips end and start.
Clips live in an ``AnimationLibrary`` saved as a ``.pzanim`` file (JSON) and loaded again
with ``pz.load_animations`` (or by giving the path to the player), so animations are
reusable across forms and apps; ``Clip.retarget`` moves a clip onto other widgets and
``Clip.animation(target)`` turns one target's tracks into a ``pz.Animation``.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from . import _core
from . import animation as _animation
from . import style as _style

#: The ``.pzanim`` file format.
FORMAT = "pyzed.animations/1"
SUFFIX = ".pzanim"
#: How a clip repeats: once, from the start again, or back and forth.
LOOPS = ("none", "loop", "pingpong")
#: How a track goes from key to key: eased (each key's ``easing``) or holding each value.
INTERPOLATIONS = ("linear", "discrete")

PathLike = Union[str, "os.PathLike[str]"]


# ---------------------------------------------------------------------------
# Values
# ---------------------------------------------------------------------------

def _seconds(value: Any, what: str) -> float:
    """Seconds from a number or ``"300ms"``/``"0.3s"``."""
    if isinstance(value, str):
        return _animation._ms(value, what) / 1000.0
    if isinstance(value, bool) or not isinstance(value, (int, float)) or math.isnan(value):
        raise ValueError(f"invalid {what} {value!r}: use seconds (0.3) or a string like '300ms'")
    if value < 0:
        raise ValueError(f"{what} can't be negative")
    return float(value)


def _split(path: str) -> Tuple[str, str]:
    """``"card:opacity"`` -> ``("card", "opacity")``; ``":score"`` -> ``("", "score")``."""
    if not isinstance(path, str) or ":" not in path:
        raise ValueError(f"invalid track path {path!r}: use 'widget:property' or ':attribute'")
    target, _, prop = path.partition(":")
    target, prop = target.strip(), prop.strip()
    if not prop:
        raise ValueError(f"invalid track path {path!r}: it names no property")
    if target and prop not in _animation.PROPERTIES:
        raise ValueError(f"{prop!r} is not an animatable widget property; available: "
                         f"{', '.join(_animation.PROPERTIES)} (use ':attribute' to animate app state)")
    if not target and not all(part.isidentifier() for part in prop.split(".")):
        raise ValueError(f"invalid attribute path {prop!r}: use names separated by dots")
    return target, prop


def _rgba(value: Any) -> Optional[Tuple[float, float, float, float]]:
    if isinstance(value, str) and value.startswith("#"):
        try:
            return _style._rgba(value)
        except ValueError:
            return None
    return None


def _lerp(a: Any, b: Any, t: float) -> Any:
    """``a`` to ``b`` at ``t``: numbers, colors and sequences of numbers mix; anything else holds."""
    if t <= 0.0:
        return a
    if t >= 1.0:
        return b
    number = (int, float)
    if isinstance(a, number) and isinstance(b, number) and not isinstance(a, bool) and not isinstance(b, bool):
        return a + (b - a) * t
    ca, cb = _rgba(a), _rgba(b)
    if ca is not None and cb is not None:
        return _style._hex(*(x + (y - x) * t for x, y in zip(ca, cb)))
    if (isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)) and len(a) == len(b)
            and all(isinstance(v, number) for v in (*a, *b))):
        return type(a)(x + (y - x) * t for x, y in zip(a, b))
    return a


# ---------------------------------------------------------------------------
# Keys, tracks, calls and clips
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Key:
    """A value at a time on a track; ``easing`` is the curve to the next key (the track's when ``None``)."""


    time: float
    value: Any
    easing: Any = None

    def __post_init__(self):
        object.__setattr__(self, "time", _seconds(self.time, "key time"))
        if self.easing is not None:
            _animation._easing(self.easing)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-ready data (``Key.from_dict`` reads it back)."""
        out = {"time": self.time, "value": list(self.value) if isinstance(self.value, tuple) else self.value}
        if self.easing is not None:
            out["easing"] = list(self.easing) if isinstance(self.easing, tuple) else self.easing
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Key":
        """Rebuilds a key saved with ``to_dict``."""
        easing = data.get("easing")
        return cls(data["time"], data.get("value"), tuple(easing) if isinstance(easing, list) else easing)


def _keys(keys: Any) -> Tuple[Key, ...]:
    """Keys from ``{time: value}``, ``[(time, value[, easing]), ...]``, dicts or ``Key`` objects."""
    if isinstance(keys, Mapping):
        items: Iterable[Any] = keys.items()
    else:
        items = keys or ()
    out = []
    for item in items:
        if isinstance(item, Key):
            out.append(item)
        elif isinstance(item, Mapping):
            out.append(Key.from_dict(item))
        elif isinstance(item, (tuple, list)) and len(item) in (2, 3):
            out.append(Key(*item))
        else:
            raise ValueError(f"invalid key {item!r}: use (time, value), (time, value, easing) or a dict")
    return tuple(sorted(out, key=lambda k: k.time))


@dataclass(frozen=True)
class Track:
    """One property changing over time: ``Track("card:opacity", {0: 0, 0.5: 1})``.

    ``keys`` is ``{time: value}``, a list of ``(time, value)`` or ``(time, value, easing)``
    tuples, or ``Key`` objects. ``easing`` is the default curve between keys (``"linear"``,
    like Godot) and ``interpolation="discrete"`` holds each value until the next key.
    ``enabled=False`` keeps a track in the clip without playing it.
    """

    path: str
    keys: Any = ()
    easing: Any = "linear"
    interpolation: str = "linear"
    enabled: bool = True

    def __post_init__(self):
        target, prop = _split(self.path)
        object.__setattr__(self, "keys", _keys(self.keys))
        _animation._easing(self.easing)
        if self.interpolation not in INTERPOLATIONS:
            raise ValueError(f"unknown interpolation {self.interpolation!r}; available: {', '.join(INTERPOLATIONS)}")
        if target:
            for key in self.keys:
                _animation._value(prop, key.value)

    @property
    def target(self) -> str:
        """The widget target (``""`` for an app attribute)."""
        return _split(self.path)[0]

    @property
    def property(self) -> str:
        """The property or attribute path it changes."""
        return _split(self.path)[1]

    def value_at(self, time: float) -> Any:
        """The track's value at ``time`` seconds (``None`` when it has no keys)."""
        keys = self.keys
        if not keys:
            return None
        if time <= keys[0].time:
            return keys[0].value
        for a, b in zip(keys, keys[1:]):
            if time < b.time:
                if self.interpolation == "discrete":
                    return a.value
                span = b.time - a.time
                t = 1.0 if span <= 0 else (time - a.time) / span
                return _lerp(a.value, b.value, _animation.ease(a.easing or self.easing, t))
        return keys[-1].value

    def with_keys(self, keys: Any) -> "Track":
        """A copy with other keys."""
        return replace(self, keys=keys)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-ready data (``Track.from_dict`` reads it back)."""
        out: Dict[str, Any] = {"path": self.path, "keys": [k.to_dict() for k in self.keys]}
        if self.easing != "linear":
            out["easing"] = list(self.easing) if isinstance(self.easing, tuple) else self.easing
        if self.interpolation != "linear":
            out["interpolation"] = self.interpolation
        if not self.enabled:
            out["enabled"] = False
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Track":
        """Rebuilds a track saved with ``to_dict``."""
        easing = data.get("easing", "linear")
        return cls(data["path"], data.get("keys", ()), tuple(easing) if isinstance(easing, list) else easing,
                   data.get("interpolation", "linear"), bool(data.get("enabled", True)))


@dataclass(frozen=True)
class Call:
    """A method called at ``time`` seconds: ``Call(1.2, "play_sound", "ding")``.

    ``method`` is the name of a method of the app (the player's ``owner``) or a callable;
    ``args`` are passed to it. What it returns (a ``Command``, a message...) is handled
    like a callback's.
    """

    time: float
    method: Any
    args: Tuple[Any, ...] = ()

    def __init__(self, time: Any, method: Any, *args: Any):
        object.__setattr__(self, "time", _seconds(time, "call time"))
        if not (isinstance(method, str) and method.isidentifier()) and not callable(method):
            raise ValueError(f"a call needs a method name or a callable, not {method!r}")
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "args", tuple(args))

    def to_dict(self) -> Dict[str, Any]:
        """JSON-ready data (only calls to methods by name can be saved)."""
        if not isinstance(self.method, str):
            raise ValueError("only calls to methods by name can be saved")
        out: Dict[str, Any] = {"time": self.time, "method": self.method}
        if self.args:
            out["args"] = list(self.args)
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Call":
        """Rebuilds a call saved with ``to_dict``."""
        return cls(data["time"], data["method"], *data.get("args", ()))


@dataclass(frozen=True)
class Clip:
    """A named timeline of ``length`` seconds with ``tracks`` and ``calls`` (see the module docs).

    ``loop`` is ``"none"`` (plays once and holds the last frame), ``"loop"`` or
    ``"pingpong"``. ``length`` defaults to the time of the last key or call.
    """

    name: str
    length: Optional[float] = None
    tracks: Tuple[Track, ...] = ()
    calls: Tuple[Call, ...] = ()
    loop: str = "none"
    description: str = ""

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name or "/" in self.name:
            raise ValueError(f"invalid clip name {self.name!r}: use a non-empty name without '/'")
        tracks = tuple(t if isinstance(t, Track) else Track.from_dict(t) for t in self.tracks)
        calls = tuple(sorted((c if isinstance(c, Call) else Call.from_dict(c) for c in self.calls),
                             key=lambda c: c.time))
        object.__setattr__(self, "tracks", tracks)
        object.__setattr__(self, "calls", calls)
        if self.loop not in LOOPS:
            raise ValueError(f"unknown loop {self.loop!r}; available: {', '.join(LOOPS)}")
        end = max([k.time for t in tracks for k in t.keys] + [c.time for c in calls] + [0.0])
        length = end if self.length is None else _seconds(self.length, "length")
        object.__setattr__(self, "length", length)

    # -- reading ----------------------------------------------------------------------

    @property
    def targets(self) -> Tuple[str, ...]:
        """The widget targets its tracks animate, in order."""
        return tuple(dict.fromkeys(t.target for t in self.tracks if t.target))

    @property
    def attributes(self) -> Tuple[str, ...]:
        """The app attributes its tracks animate (``":score"`` -> ``"score"``)."""
        return tuple(dict.fromkeys(t.property for t in self.tracks if not t.target))

    def track(self, path: str) -> Optional[Track]:
        """The track with ``path`` (``None`` when there is none)."""
        return next((t for t in self.tracks if t.path == path), None)

    def values(self, time: float, target: Optional[str] = None) -> Dict[str, Any]:
        """``{path: value}`` of the enabled tracks at ``time`` (only ``target``'s, as ``{property: value}``)."""
        out = {}
        for t in self.tracks:
            if not t.enabled or not t.keys:
                continue
            if target is None:
                out[t.path] = t.value_at(time)
            elif t.target == target:
                out[t.property] = t.value_at(time)
        return out

    # -- editing (clips are immutable: these return copies) ---------------------------

    def with_track(self, track: Track) -> "Clip":
        """A copy with ``track`` added, or replacing the track with the same path."""
        tracks = [t for t in self.tracks if t.path != track.path]
        index = next((i for i, t in enumerate(self.tracks) if t.path == track.path), len(tracks))
        tracks.insert(index, track)
        return replace(self, tracks=tuple(tracks))

    def without_track(self, path: str) -> "Clip":
        """A copy without the track ``path``."""
        return replace(self, tracks=tuple(t for t in self.tracks if t.path != path))

    def with_key(self, path: str, time: Any, value: Any, easing: Any = None) -> "Clip":
        """A copy with a key at ``time`` on ``path`` (replacing one at the same time; adds the track)."""
        key = Key(time, value, easing)
        track = self.track(path) or Track(path)
        keys = [k for k in track.keys if abs(k.time - key.time) > 1e-6] + [key]
        return self.with_track(track.with_keys(keys))

    def without_key(self, path: str, time: float) -> "Clip":
        """A copy without the key at ``time`` on ``path``."""
        track = self.track(path)
        if track is None:
            return self
        return self.with_track(track.with_keys([k for k in track.keys if abs(k.time - time) > 1e-6]))

    def retarget(self, mapping: Mapping[str, str], name: Optional[str] = None) -> "Clip":
        """A copy whose tracks animate other widgets: ``clip.retarget({"card": "panel"})``."""
        tracks = []
        for t in self.tracks:
            target = mapping.get(t.target, t.target) if t.target else ""
            tracks.append(replace(t, path=f"{target}:{t.property}"))
        return replace(self, name=name or self.name, tracks=tuple(tracks))

    # -- native playback --------------------------------------------------------------

    def _native_tracks(self, target: str) -> List[Tuple[str, List[Tuple[float, Any, Any]]]]:
        """``[(prop, [(offset, value, easing), ...]), ...]`` for ``target``'s enabled tracks."""
        out = []
        length = self.length or 0.0
        for t in self.tracks:
            if t.target != target or not t.enabled or not t.keys:
                continue
            step = ("steps", 1)
            frames = []
            for i, k in enumerate(t.keys):
                easing = step if t.interpolation == "discrete" else _animation._easing(k.easing or t.easing)
                offset = 0.0 if length <= 0 else min(k.time / length, 1.0)
                frames.append((offset, _animation._value(t.property, k.value), easing))
            # Hold the first and last values, like Godot (natively a missing end means "the
            # widget's own value").
            if frames[0][0] > 0.0:
                frames.insert(0, (0.0, frames[0][1], frames[0][2]))
            if frames[-1][0] < 1.0:
                frames.append((1.0, frames[-1][1], None))
            out.append((t.property, frames))
        return out

    def animation(self, target: str, *, on: str = "mount", **options: Any) -> _animation.Animation:
        """``target``'s tracks as a ``pz.Animation`` (to play without a player, or ``define_animation``)."""
        frames = []
        for prop, keys in self._native_tracks(target):
            for offset, value, easing in keys:
                frame = {"offset": offset, prop: list(value) if isinstance(value, tuple) else value}
                if easing is not None:
                    frame["easing"] = easing
                frames.append(_unnative(prop, frame))
        if not frames:
            raise ValueError(f"clip {self.name!r} has no tracks for {target!r}")
        repeat = 1 if self.loop == "none" else "infinite"
        direction = "alternate" if self.loop == "pingpong" else "normal"
        return _animation.Animation(frames, duration=(self.length or 0) * 1000, easing="linear", repeat=repeat,
                                    direction=direction, on=on, **options)

    # -- saving -----------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """JSON-ready data (``Clip.from_dict`` reads it back)."""
        out: Dict[str, Any] = {"name": self.name, "length": self.length}
        if self.loop != "none":
            out["loop"] = self.loop
        if self.description:
            out["description"] = self.description
        out["tracks"] = [t.to_dict() for t in self.tracks]
        if self.calls:
            out["calls"] = [c.to_dict() for c in self.calls]
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Clip":
        """Rebuilds a clip saved with ``to_dict``."""
        return cls(data["name"], data.get("length"), tuple(Track.from_dict(t) for t in data.get("tracks", ())),
                   tuple(Call.from_dict(c) for c in data.get("calls", ())), data.get("loop", "none"),
                   data.get("description", ""))


def _unnative(prop: str, frame: Dict[str, Any]) -> Dict[str, Any]:
    """A compiled keyframe back in ``pz.Animation`` terms (``("pct", 0.5)`` -> ``"50%"``)."""
    value = frame.get(prop)
    if isinstance(value, list) and len(value) == 2 and value[0] == "pct":
        frame[prop] = f"{value[1] * 100}%"
    easing = frame.get("easing")
    if isinstance(easing, tuple) and easing[0] == "steps":
        frame["easing"] = f"steps({easing[1]})"
    elif isinstance(easing, tuple) and easing[0] == "cubic_bezier":
        frame["easing"] = tuple(easing[1:])
    return frame


# ---------------------------------------------------------------------------
# Libraries (.pzanim files)
# ---------------------------------------------------------------------------

class AnimationLibrary:
    """Named clips that are saved together in a ``.pzanim`` file and reused.

    ``AnimationLibrary([intro, idle], name="ui")``; ``lib["intro"]``, ``lib.add(clip)``,
    ``lib.remove("idle")``, ``lib.save("ui.pzanim")`` and ``AnimationLibrary.load(path)``.
    A player given a library with a ``name`` calls its clips ``"ui/intro"``, like Godot.
    """

    def __init__(self, clips: Iterable[Clip] = (), *, name: str = ""):
        self.name = name
        self._clips: Dict[str, Clip] = {}
        for clip in clips:
            self.add(clip)

    def add(self, clip: Clip) -> Clip:
        """Adds ``clip`` (replacing one with its name) and returns it."""
        if not isinstance(clip, Clip):
            clip = Clip.from_dict(clip)
        self._clips[clip.name] = clip
        return clip

    def remove(self, name: str) -> None:
        """Removes the clip ``name`` (nothing happens when there is none)."""
        self._clips.pop(name, None)

    def rename(self, old: str, new: str) -> Clip:
        """Renames the clip ``old`` to ``new`` and returns it."""
        clip = replace(self._clips.pop(old), name=new)
        self._clips[new] = clip
        return clip

    @property
    def names(self) -> List[str]:
        """The names of its clips, in order."""
        return list(self._clips)

    def __getitem__(self, name: str) -> Clip:
        try:
            return self._clips[name]
        except KeyError:
            raise KeyError(f"no clip named {name!r}; clips: {', '.join(self._clips) or 'none'}") from None

    def __contains__(self, name: object) -> bool:
        return name in self._clips

    def __iter__(self):
        return iter(self._clips.values())

    def __len__(self) -> int:
        return len(self._clips)

    def __repr__(self) -> str:
        return f"AnimationLibrary({self.names!r}{f', name={self.name!r}' if self.name else ''})"

    def to_dict(self) -> Dict[str, Any]:
        """The ``.pzanim`` data (``AnimationLibrary.from_dict`` reads it back)."""
        out: Dict[str, Any] = {"format": FORMAT}
        if self.name:
            out["name"] = self.name
        out["clips"] = [c.to_dict() for c in self._clips.values()]
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AnimationLibrary":
        """Rebuilds a library from ``.pzanim`` data."""
        fmt = data.get("format", FORMAT)
        if not str(fmt).startswith("pyzed.animations/"):
            raise ValueError(f"not a Pyzed animation library (format {fmt!r})")
        return cls((Clip.from_dict(c) for c in data.get("clips", ())), name=data.get("name", ""))

    def save(self, path: PathLike) -> Path:
        """Writes the library as JSON (a ``.pzanim`` file) and returns the path."""
        path = Path(path)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: PathLike) -> "AnimationLibrary":
        """Reads a ``.pzanim`` file (raises ``ValueError`` when it isn't one)."""
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} is not a valid animation library: {exc}") from None
        return cls.from_dict(data)


def load_animations(path: PathLike) -> AnimationLibrary:
    """The library saved in a ``.pzanim`` file."""
    return AnimationLibrary.load(path)


# ---------------------------------------------------------------------------
# The player
# ---------------------------------------------------------------------------

class _Target:
    """What ``player["card"]`` gives ``animate()``: the clip's tracks for one widget target."""

    __slots__ = ("player", "name", "only")

    def __init__(self, player: "AnimationPlayer", name: str, only: Optional[Tuple[str, ...]] = None):
        self.player = player
        self.name = name
        self.only = only

    def _pyzed_compiled(self) -> List[Dict[str, Any]]:
        return self.player._compiled(self.name, self.only)

    def __repr__(self) -> str:
        return f"<animation target {self.name!r}>"


class AnimationPlayer:
    """Plays ``Clip``s on widgets and app state, with play, pause, seek, speed and a queue.

    ``sources`` are clips, ``AnimationLibrary`` objects and ``.pzanim`` paths. Give widgets
    their target with ``widget.animate(player["card"])``; tracks of app attributes
    (``":score"``) and ``Call``s run on the player's ``owner``, which is the app (or window)
    that holds the player in an attribute, found automatically, or the one you pass.

    - ``autoplay``: the clip that plays when the player is created.
    - ``speed``: the playback speed of every clip (``play`` multiplies it).
    - ``on_started(name)``/``on_finished(name)``: called when a clip starts and when it
      ends (never for looping clips); they may take no argument.
    - ``fps``: how often app attributes update while a clip with attribute tracks plays.

    Events:
        ``on_started()``:
        ``on_finished()``:
    """

    def __init__(self, *sources: Any, autoplay: Optional[str] = None, speed: float = 1.0,
                 on_started: Optional[Callable[..., Any]] = None, on_finished: Optional[Callable[..., Any]] = None,
                 owner: Any = None, fps: float = 60.0):
        self._clips: Dict[str, Clip] = {}
        self.speed = float(speed)
        self.on_started = on_started
        self.on_finished = on_finished
        self.owner = owner
        self.fps = float(fps)
        self._clock: Callable[[], float] = time.monotonic
        self._current: Optional[str] = None
        self._progress = 0.0       # clip time along the playing direction (grows while playing)
        self._anchor: Optional[float] = None  # clock time when `_progress` was taken (None: not moving)
        self._rate = 1.0           # the speed `play` asked for
        self._backwards = False
        self._finished = False
        self._fired = 0.0          # progress up to which calls ran
        self._queue: List[str] = []
        self._generation = 0
        self._wakes = 0
        self._cache: Dict[Any, List[Dict[str, Any]]] = {}
        for source in sources:
            self.add(source)
        if autoplay:
            self.play(autoplay)

    # -- clips --------------------------------------------------------------------------

    def add(self, source: Any, *, prefix: Optional[str] = None) -> None:
        """Adds a clip, a library (its clips as ``"name/clip"`` when it has a name) or a ``.pzanim`` path."""
        if isinstance(source, (str, os.PathLike)):
            source = AnimationLibrary.load(source)
        if isinstance(source, Clip):
            self._clips[f"{prefix}/{source.name}" if prefix else source.name] = source
        elif isinstance(source, AnimationLibrary):
            prefix = source.name if prefix is None else prefix
            for clip in source:
                self._clips[f"{prefix}/{clip.name}" if prefix else clip.name] = clip
        elif isinstance(source, (list, tuple)):
            for item in source:
                self.add(item, prefix=prefix)
        else:
            raise TypeError(f"an animation player plays clips, libraries and .pzanim paths, not {type(source).__name__}")
        self._changed()

    def remove(self, name: str) -> None:
        """Removes the clip ``name`` (stopping it when it is the current one)."""
        if name == self._current:
            self.stop(reset=True)
        self._clips.pop(name, None)

    @property
    def names(self) -> List[str]:
        """The names of the clips it can play."""
        return list(self._clips)

    def has(self, name: str) -> bool:
        """Whether it has a clip called ``name``."""
        return name in self._clips

    def clip(self, name: Optional[str] = None) -> Clip:
        """The clip named ``name`` (the current one by default)."""
        name = name or self._current
        if name is None:
            raise KeyError("no clip is playing")
        try:
            return self._clips[name]
        except KeyError:
            raise KeyError(f"no clip named {name!r}; clips: {', '.join(self._clips) or 'none'}") from None

    def __getitem__(self, target: str) -> _Target:
        """The widget target ``target`` for ``widget.animate(player[target])``."""
        return _Target(self, target)

    def target(self, target: str, *, only: Optional[Sequence[str]] = None) -> _Target:
        """Like ``player[target]``; ``only`` keeps some properties (``("opacity", "x", "y")``), for
        example to move what sits inside an animated container along with it."""
        return _Target(self, target, None if only is None else tuple(only))

    # -- state --------------------------------------------------------------------------

    @property
    def current(self) -> Optional[str]:
        """The clip playing or paused (``None`` when stopped)."""
        return self._current

    @property
    def playing(self) -> bool:
        """Whether time is moving."""
        return self._anchor is not None

    @property
    def paused(self) -> bool:
        """Whether a clip is paused (stopped clips and finished ones aren't)."""
        return self._current is not None and self._anchor is None and not self._finished

    @property
    def finished(self) -> bool:
        """Whether the current clip reached its end."""
        return self._finished

    @property
    def length(self) -> float:
        """The length of the current clip in seconds (0 when none)."""
        return self.clip().length if self._current else 0.0

    @property
    def position(self) -> float:
        """Seconds into the current clip."""
        return self._local(self._now_progress()) if self._current else 0.0

    @property
    def queued(self) -> List[str]:
        """The clips that play after the current one, in order."""
        return list(self._queue)

    def value(self, path: str) -> Any:
        """The value the current clip gives ``path`` (``"card:opacity"``, ``":score"``) right now."""
        if not self._current:
            return None
        track = self.clip().track(path)
        return None if track is None else track.value_at(self.position)

    # -- control ------------------------------------------------------------------------

    def play(self, name: Optional[str] = None, *, speed: float = 1.0, backwards: bool = False,
             from_end: bool = False, restart: bool = False) -> None:
        """Plays ``name`` (the current or paused clip by default) from where it is.

        A clip that is already playing keeps going unless ``restart``; a finished one
        starts again. ``backwards`` plays it in reverse (``from_end`` starts at its end).
        """
        name = name or self._current
        if name is None:
            raise ValueError("play() needs a clip name: nothing was playing")
        self.clip(name)
        same = name == self._current
        if same and self.playing and not restart and backwards == self._backwards and speed == self._rate:
            return
        if not same or restart or self._finished:
            start = self._clips[name].length if from_end else 0.0
            self._current = name
            self._backwards = backwards
            self._progress = (self._clips[name].length - start) if backwards else start
            self._finished = False
            self._fired = self._progress
            self._rate = speed
            self._emit(self.on_started, name)
        elif backwards != self._backwards:
            local = self.position
            self._backwards = backwards
            self._progress = self._progress_for(local)
            self._fired = self._progress
            self._rate = speed
        else:
            self._progress = self._now_progress()
            self._rate = speed
        self._anchor = self._clock()
        self._changed()
        self._apply_state()

    def play_backwards(self, name: Optional[str] = None, *, speed: float = 1.0) -> None:
        """Plays ``name`` in reverse from its end (or the current clip from where it is)."""
        restart = name is not None and name != self._current
        self.play(name, speed=speed, backwards=True, from_end=restart or self._current is None or self._finished,
                  restart=restart)

    def pause(self) -> None:
        """Stops time where it is (``play()`` or ``resume()`` goes on)."""
        if self._anchor is None:
            return
        self._progress = self._now_progress()
        self._anchor = None
        self._changed()

    def resume(self) -> None:
        """Goes on from where the clip was paused."""
        if self._current and not self.playing:
            self.play()

    def toggle(self) -> None:
        """Pauses when playing, plays otherwise."""
        self.pause() if self.playing else self.play()

    def stop(self, *, reset: bool = False) -> None:
        """Stops at the start of the clip (showing its first frame); ``reset`` lets widgets
        go back to their own values and forgets the clip. Clears the queue."""
        self._queue.clear()
        self._anchor = None
        self._finished = False
        if reset or not self._current:
            self._current = None
            self._progress = 0.0
        else:
            self._progress = self._progress_for(0.0)
        self._fired = self._progress
        self._changed()
        self._apply_state()

    def seek(self, seconds: Any) -> None:
        """Jumps to ``seconds`` into the current clip (calls on the way don't run)."""
        if not self._current:
            raise ValueError("seek() needs a clip: play one first")
        local = min(_seconds(seconds, "position"), self.length)
        self._progress = self._progress_for(local)
        self._fired = self._progress
        self._finished = False
        if self._anchor is not None:
            self._anchor = self._clock()
        self._changed()
        self._apply_state()

    def advance(self, seconds: float) -> List[Any]:
        """Moves the current clip ``seconds`` forward (calls run, state updates), like Godot's ``advance``."""
        if not self._current:
            return []
        self._progress = self._now_progress() + max(0.0, float(seconds)) * self._speed()
        if self._anchor is not None:
            self._anchor = self._clock()
        self._changed()
        return self._process()

    def queue(self, name: str) -> None:
        """Plays ``name`` after the current clip ends (or now when nothing plays)."""
        self.clip(name)
        if self._current is None or self._finished:
            self.play(name)
        else:
            self._queue.append(name)

    def clear_queue(self) -> None:
        """Forgets the queued clips."""
        self._queue.clear()

    # -- time ---------------------------------------------------------------------------

    def _speed(self) -> float:
        return max(0.0, self.speed * self._rate)

    def _now_progress(self) -> float:
        if self._anchor is None:
            return self._progress
        return self._progress + (self._clock() - self._anchor) * self._speed()

    def _local(self, progress: float) -> float:
        """Seconds into the clip at ``progress`` (loops and direction applied)."""
        clip = self.clip()
        length = clip.length or 0.0
        if length <= 0:
            return 0.0
        if clip.loop == "none":
            local = min(max(progress, 0.0), length)
        elif clip.loop == "loop":
            local = progress % length
        else:
            index = math.floor(progress / length)
            frac = progress - index * length
            local = length - frac if index % 2 else frac
        return length - local if self._backwards else local

    def _progress_for(self, local: float) -> float:
        return self.clip().length - local if self._backwards else local

    def _process(self) -> List[Any]:
        """Runs the calls crossed since the last time, updates app state and ends finished clips."""
        if not self._current:
            return []
        clip = self.clip()
        now = self._now_progress()
        results = [r for r in self._run_calls(clip, self._fired, now) if r is not None]
        self._fired = now
        if clip.loop == "none" and now >= clip.length and not self._finished:
            self._progress = clip.length
            self._anchor = None
            self._finished = True
            self._fired = clip.length
            self._changed()
            self._apply_state()
            name = self._current
            results.append(self._emit(self.on_finished, name))
            if self._queue:
                self.play(self._queue.pop(0))
                results.extend(self._process())
        else:
            self._apply_state()
        return [r for r in results if r is not None]

    def _run_calls(self, clip: Clip, start: float, end: float) -> List[Any]:
        if not clip.calls or end <= start or clip.length <= 0:
            return []
        length = clip.length
        if clip.loop == "none":
            end = min(end, length)
        out = []
        index = math.floor(start / length)
        while index * length <= end and len(out) < 10_000:
            a, b = max(start, index * length), min(end, (index + 1) * length)
            if b > a or (b == a == end == length and clip.loop == "none"):
                la, lb = self._local_in(clip, index, a), self._local_in(clip, index, b)
                lo, hi = min(la, lb), max(la, lb)
                closed_end = clip.loop == "none" and b >= length
                calls = [c for c in clip.calls if (lo <= c.time < hi) or (closed_end and c.time == hi)
                         or (lo == hi and c.time == lo)]
                if la > lb:
                    calls.reverse()
                for call in calls:
                    out.append(self._call(call))
            index += 1
            if clip.loop == "none":
                break
        return out

    def _local_in(self, clip: Clip, index: int, progress: float) -> float:
        frac = progress - index * clip.length
        local = clip.length - frac if (clip.loop == "pingpong" and index % 2) else frac
        return clip.length - local if self._backwards else local

    # -- effects ------------------------------------------------------------------------

    def _call(self, call: Call) -> Any:
        method = call.method
        if isinstance(method, str):
            if self.owner is None:
                raise RuntimeError(f"Call to {method!r}: the player has no owner (keep it on the app or pass owner=)")
            method = getattr(self.owner, method)
        return method(*call.args)

    def _emit(self, handler: Any, name: str) -> Any:
        if handler is None:
            return None
        from .events import accepts_argument

        return handler(name) if accepts_argument(handler) else handler()

    def _apply_state(self) -> None:
        """Writes the current values of app-attribute tracks to the owner."""
        if not self._current or self.owner is None:
            return
        clip = self.clip()
        if not clip.attributes:
            return
        local = self.position
        for track in clip.tracks:
            if track.target or not track.enabled or not track.keys:
                continue
            obj = self.owner
            *parents, last = track.property.split(".")
            for part in parents:
                obj = getattr(obj, part)
            setattr(obj, last, track.value_at(local))

    def _changed(self) -> None:
        self._generation += 1
        self._cache.clear()

    def _compiled(self, target: str, only: Optional[Tuple[str, ...]] = None) -> List[Dict[str, Any]]:
        """The native animation ``target``'s widgets play right now (``only`` some properties)."""
        cached = self._cache.get((target, only))
        if cached is not None:
            return cached
        out: List[Dict[str, Any]] = []
        if self._current:
            clip = self.clip()
            tracks = [t for t in clip._native_tracks(target) if only is None or t[0] in only]
            if tracks:
                direction = {("none", False): "normal", ("loop", False): "normal", ("pingpong", False): "alternate",
                             ("none", True): "reverse", ("loop", True): "reverse",
                             ("pingpong", True): "alternate_reverse"}[(clip.loop, self._backwards)]
                speed = self._speed()
                out.append({
                    "trigger": "mount",
                    "key": f"{id(self)}:{self._generation}",
                    "active": False,
                    "duration": (clip.length or 0.0) * 1000.0,
                    "delay": 0.0,
                    "iterations": 1.0 if clip.loop == "none" else math.inf,
                    "direction": direction,
                    "fill": "both",
                    "easing": "linear",
                    "tracks": tracks,
                    "on_start": None,
                    "on_end": None,
                    "seek": max(0.0, self._progress) * 1000.0,
                    "speed": speed if speed > 0 else 1.0,
                    "paused": self._anchor is None or speed <= 0,
                })
        self._cache[(target, only)] = out
        return out

    # -- runtime ------------------------------------------------------------------------

    def _needs_ticks(self) -> bool:
        clip = self.clip()
        return bool(clip.attributes) and self.owner is not None

    def _next_wake(self) -> Optional[float]:
        """Seconds until the next call or the end of the clip (``None``: nothing to wait for)."""
        clip = self.clip()
        speed = self._speed()
        if speed <= 0:
            return None
        now = self._now_progress()
        candidates = []
        if clip.loop == "none":
            candidates.append(clip.length - now)
        if clip.calls and clip.length > 0:
            if clip.loop == "none":
                candidates += [self._progress_for(c.time) - now for c in clip.calls]
            else:
                # The next time each call comes, in this cycle or the next one.
                first = math.floor(now / clip.length)
                for index in (first, first + 1):
                    mirrored = (clip.loop == "pingpong" and index % 2 == 1) != self._backwards
                    for c in clip.calls:
                        frac = clip.length - c.time if mirrored else c.time
                        candidates.append(index * clip.length + frac - now)
        ahead = [c for c in candidates if c > 1e-6]
        if not ahead:
            return 0.0 if clip.loop == "none" else None
        return min(ahead) / speed

    def _on_frame(self, dt: float = 0.0) -> Any:
        results = self._process()
        return results or None

    def _on_timer(self) -> Any:
        self._wakes += 1
        results = self._process()
        return results or None

    def subscriptions(self) -> List[Any]:
        """What keeps the player's calls, attribute tracks and queue going (added for you when
        the player is an attribute of the app or a window)."""
        if not self.playing or not self._current:
            return []
        if self._needs_ticks():
            return [_core.frames(self._on_frame, key=f"pyzed-anim:{id(self)}", max_fps=self.fps)]
        wait = self._next_wake()
        if wait is None:
            return []
        return [_core.every(max(wait, 0.001), self._on_timer, key=f"pyzed-anim:{id(self)}:{self._generation}:{self._wakes}")]

    def __repr__(self) -> str:
        state = "playing" if self.playing else "paused" if self.paused else "finished" if self._finished else "stopped"
        return f"AnimationPlayer({self.names!r}, {state}{f' {self._current!r}' if self._current else ''})"


def _player_subscriptions(obj: Any) -> List[Any]:
    """The subscriptions of the animation players kept in ``obj``'s attributes (called by the runtime)."""
    try:
        values = vars(obj).values()
    except TypeError:
        return []
    out: List[Any] = []
    for value in values:
        if isinstance(value, AnimationPlayer):
            if value.owner is None:
                value.owner = obj
                value._apply_state()
            out.extend(value.subscriptions())
    return out


__all__ = ["AnimationLibrary", "AnimationPlayer", "Call", "Clip", "FORMAT", "INTERPOLATIONS", "Key", "LOOPS",
           "SUFFIX", "Track", "load_animations"]
