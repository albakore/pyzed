"""Timeline animations of a form: the clips it keeps, how they play and the Animation panel's state.

A form keeps its clips in ``Form.animations`` (``pz.Clip.to_dict()`` data, saved in the
``.pzform``) and plays ``Form.autoplay`` when it opens. A track animates a control:

- ``"title:opacity"``: a widget property of the control ``title`` (``pz.animation.PROPERTIES``),
  played natively;
- ``":title.text"``: one of the control's own properties (any of them: text, value, checked...),
  set while the clip plays.

Handlers drive the player with ``form.animations`` (a ``pz.AnimationPlayer``)::

    def play_click(form, event):
        form.animations.play("intro")

and a ``Call`` on the timeline runs the handler with that name (``event.value`` holds its
arguments). ``TimelineEditor`` is the designer's Animation panel: the clip being edited,
the playhead, the selected key, and the preview on the canvas.
"""

from __future__ import annotations

import math
import re
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple

from .. import _core
from ..animation import PROPERTIES
from ..animation_player import Call, Clip, Key, LOOPS, Track
from ..animation_player import AnimationPlayer
from . import components as _components
from .model import Control, Form

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: Widget properties offered first when adding a track, and their resting values.
REST = {"opacity": 1.0, "x": 0.0, "y": 0.0, "scale": 1.0, "rotate": 0.0, "blur": 0.0, "radius": 0.0,
        "border_width": 0.0, "glow": 0.0, "padding": 0.0, "font_size": 14.0}
COLORS = ("background", "border_color", "color", "glow_color")
#: What a container's tracks also do to the controls inside it (they are drawn on their own).
INHERITED = ("opacity", "x", "y", "blur")


# ---------------------------------------------------------------------------
# Clips of a form
# ---------------------------------------------------------------------------

def clips(form: Form) -> List[Clip]:
    """The form's clips (entries that can't be read are skipped)."""
    out = []
    for data in form.animations:
        try:
            out.append(Clip.from_dict(data))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def get(form: Form, name: Optional[str]) -> Optional[Clip]:
    return next((c for c in clips(form) if c.name == name), None)


def unique_name(form: Form, base: str = "animation") -> str:
    """``base``, or ``base2``, ``base3``... when it is taken."""
    base = re.sub(r"[^\w-]+", "_", base.strip()).strip("_") or "animation"
    taken = {c.name for c in clips(form)}
    if base not in taken:
        return base
    n = 2
    while f"{base}{n}" in taken:
        n += 1
    return f"{base}{n}"


def put(form: Form, clip: Clip, old: Optional[str] = None) -> None:
    """Stores ``clip`` in place of ``old`` (or of the clip with its name), or at the end."""
    data = clip.to_dict()
    names = [d.get("name") for d in form.animations]
    key = old if old in names else clip.name
    if key in names:
        form.animations[names.index(key)] = data
    else:
        form.animations.append(data)
    if old and old != clip.name and form.autoplay == old:
        form.autoplay = clip.name


def remove(form: Form, name: str) -> None:
    form.animations = [d for d in form.animations if d.get("name") != name]
    if form.autoplay == name:
        form.autoplay = ""


def _rename_path(path: str, old: str, new: str) -> str:
    target, _, prop = path.partition(":")
    if target == old:
        return f"{new}:{prop}"
    if not target and (prop == old or prop.startswith(old + ".")):
        return f":{new}{prop[len(old):]}"
    return path


def rename_target(form: Form, old: str, new: str) -> bool:
    """Makes every track of control ``old`` animate ``new``; returns whether any changed."""
    changed = False
    for i, clip in enumerate(clips(form)):
        tracks = tuple(replace(t, path=_rename_path(t.path, old, new)) for t in clip.tracks)
        if tracks != clip.tracks:
            put(form, replace(clip, tracks=tracks))
            changed = True
    return changed


def control_of(path: str) -> str:
    """The control a track path animates (``"title:x"``, ``":title.text"`` -> ``"title"``)."""
    target, _, prop = path.partition(":")
    return target or prop.split(".", 1)[0]


def drop_targets(form: Form, names: Sequence[str]) -> bool:
    """Removes the tracks of the controls ``names`` (they were deleted); returns whether any went."""
    names = set(names)
    changed = False
    for clip in clips(form):
        tracks = tuple(t for t in clip.tracks if control_of(t.path) not in names)
        if tracks != clip.tracks:
            put(form, replace(clip, tracks=tracks))
            changed = True
    return changed


# ---------------------------------------------------------------------------
# Tracks of a control
# ---------------------------------------------------------------------------

def track_paths(control: Control) -> List[Tuple[str, str]]:
    """``[(path, label), ...]`` a control can animate: its widget properties, then its own."""
    out = [(f"{control.name}:{prop}", prop.replace("_", " ")) for prop in PROPERTIES]
    try:
        spec = _components.get(control.type)
    except KeyError:
        return out
    for prop in spec.props:
        out.append((f":{control.name}.{prop.name}", (prop.label or prop.name).lower()))
    return out


def label(path: str) -> str:
    """How a track is shown: ``"title:opacity"`` -> ``"title · opacity"``, ``":title.text"`` -> ``"title.text"``."""
    target, _, prop = path.partition(":")
    return f"{target} · {prop.replace('_', ' ')}" if target else prop


def current_value(form: Form, path: str) -> Any:
    """The value a new key on ``path`` starts from: the control's own value, or the property's resting one."""
    target, _, prop = path.partition(":")
    name = control_of(path)
    control = form.get(name)
    if not target:
        attribute = prop.split(".", 1)[1] if "." in prop else ""
        if control is None or not attribute:
            return None
        if attribute in control.props:
            return control.props[attribute]
        try:
            return _components.get(control.type).defaults().get(attribute)
        except KeyError:
            return None
    if prop in REST:
        if prop in ("radius", "border_width", "font_size") and control is not None:
            style_key = {"radius": "radius", "border_width": "border_width", "font_size": "size"}[prop]
            value = control.style.get(style_key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
        return REST[prop]
    if prop in ("width", "height"):
        return float(getattr(control, prop)) if control is not None else 100.0
    if prop in COLORS:
        value = control.style.get(prop) if control is not None else None
        return value if isinstance(value, str) and value.startswith("#") else "#ffffff"
    return None


def overrides(clip: Optional[Clip], time: float) -> Dict[str, Dict[str, Any]]:
    """``{control: {prop: value}}`` the clip's control-property tracks give at ``time`` (to preview them)."""
    out: Dict[str, Dict[str, Any]] = {}
    if clip is None:
        return out
    for track in clip.tracks:
        if track.target or not track.enabled or not track.keys or "." not in track.property:
            continue
        name, attribute = track.property.split(".", 1)
        if "." not in attribute:
            out.setdefault(name, {})[attribute] = track.value_at(time)
    return out


# ---------------------------------------------------------------------------
# Playing in a running form
# ---------------------------------------------------------------------------

class FormOwner:
    """What a running form's player animates: ``:name.prop`` writes control properties and a
    ``Call("handler")`` runs that handler of the form's code."""

    def __init__(self, runtime: Any) -> None:
        object.__setattr__(self, "_runtime", runtime)

    def __getattr__(self, name: str) -> Any:
        runtime = self._runtime
        handler = runtime.handlers.get(name)
        if handler is not None:
            from .runtime import Event

            proxy = runtime.proxy
            return lambda *args: handler(proxy, Event(proxy, "animation", args[0] if len(args) == 1 else args or None))
        return getattr(runtime.proxy, name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._runtime.proxy, name, value)


def targets(player: Optional[AnimationPlayer], form: Form, name: str) -> List[Any]:
    """What control ``name`` plays: its own tracks, and the opacity and offsets of the containers
    around it (``[]`` when nothing animates it)."""
    if player is None or not player.current:
        return []
    animated = player.clip().targets
    out = [player[name]] if name in animated else []
    for ancestor in form.ancestors(name):
        if ancestor.name in animated:
            out.append(player.target(ancestor.name, only=INHERITED))
    return out


def player_for(form: Form, owner: Any) -> AnimationPlayer:
    """A player with the form's clips, playing its ``autoplay`` clip."""
    player = AnimationPlayer(*clips(form), owner=owner)
    if form.autoplay and player.has(form.autoplay):
        player.play(form.autoplay)
    return player


def reload_player(old: AnimationPlayer, form: Form) -> AnimationPlayer:
    """A player with ``form``'s clips that goes on where ``old`` was (hot reload)."""
    player = AnimationPlayer(*clips(form), owner=old.owner)
    current = old.current
    if current and player.has(current):
        position, playing = old.position, old.playing
        player.play(current)
        if not playing:
            player.pause()
        player.seek(min(position, player.length))
    elif form.autoplay and player.has(form.autoplay):
        player.play(form.autoplay)
    return player


# ---------------------------------------------------------------------------
# The Animation panel
# ---------------------------------------------------------------------------

class TimelineEditor:
    """What the Animation panel shows and edits; edits go through ``d.doc`` so they undo."""

    #: Pixels per second at zoom 1.
    SCALE = 160.0

    def __init__(self, d: "Designer") -> None:
        self.d = d
        self.clip_name: Optional[str] = None
        self.time = 0.0
        self.zoom = 1.0
        #: ``(path, time)`` of the selected key.
        self.selected: Optional[Tuple[str, float]] = None
        #: The track whose "add key" menu or property list is open.
        self.adding = False
        #: The key being dragged: ``(path, time it had)``.
        self.dragging: Optional[Tuple[str, float]] = None
        #: Where the pointer is along the ruler or a lane, in pixels.
        self.pointer_x = 0.0
        self.scrubbing = False
        #: What is typed in the clip name and call fields (``None``: the clip's own name).
        self.name_draft: Optional[str] = None
        self.call_draft = ""
        self._player: Optional[AnimationPlayer] = None
        self._player_clip: Optional[Clip] = None
        #: The panel was opened (it stays available once the form has clips).
        self.open = False

    def show(self) -> None:
        """Opens the Animation panel."""
        self.open = True
        self.d.show_panel("animation")

    # -- reading --------------------------------------------------------------------

    @property
    def form(self) -> Form:
        return self.d.doc.form

    @property
    def clips(self) -> List[Clip]:
        return clips(self.form)

    @property
    def clip(self) -> Optional[Clip]:
        """The clip being edited (the first one when none was chosen)."""
        all_clips = self.clips
        found = next((c for c in all_clips if c.name == self.clip_name), None)
        if found is None and all_clips:
            found = all_clips[0]
            self.clip_name = found.name
        return found

    @property
    def px(self) -> float:
        """Pixels per second."""
        return self.SCALE * self.zoom

    @property
    def playing(self) -> bool:
        return self._player is not None and self._player.playing

    @property
    def position(self) -> float:
        """Where the playhead is (follows the preview while it plays)."""
        if self.playing:
            return self._player.position  # type: ignore[union-attr]
        return self.time

    def key(self) -> Optional[Key]:
        """The selected key."""
        clip = self.clip
        if clip is None or self.selected is None:
            return None
        track = clip.track(self.selected[0])
        if track is None:
            return None
        return next((k for k in track.keys if abs(k.time - self.selected[1]) < 1e-6), None)

    # -- preview --------------------------------------------------------------------

    def player(self) -> Optional[AnimationPlayer]:
        """The player the canvas follows: paused at the playhead, or playing the preview."""
        clip = self.clip
        if clip is None:
            self._player = self._player_clip = None
            return None
        if self._player is None or self._player_clip != clip:
            playing = self.playing
            position = self.position
            self._player = AnimationPlayer(clip)
            self._player_clip = clip
            self._player.play(clip.name)
            if not playing:
                self._player.pause()
            self._player.seek(min(position, clip.length))
        return self._player

    def targets(self, name: str) -> List[Any]:
        """What control ``name`` plays on the canvas (see ``targets``)."""
        clip = self.clip
        if clip is None or not clip.targets:
            return []
        return targets(self.player(), self.form, name)

    def canvas_overrides(self) -> Dict[str, Dict[str, Any]]:
        return overrides(self.clip, self.position)

    def play(self, backwards: bool = False) -> None:
        player = self.player()
        if player is None:
            return
        if player.finished or (not backwards and self.position >= player.length) or \
                (backwards and self.position <= 0):
            player.seek(player.length if backwards else 0.0)
        local = self.position
        player.play(backwards=backwards)
        player.seek(local)

    def pause(self) -> None:
        if self._player is not None and self.playing:
            self._player.pause()
            self.time = self._player.position

    def toggle(self) -> None:
        self.pause() if self.playing else self.play()

    def stop(self) -> None:
        self.pause()
        self.seek(0.0)

    def tick(self, _dt: float = 0.0) -> None:
        """Called while the preview plays: notices the end of the clip."""
        player = self._player
        if player is None:
            return
        player._process()
        if not player.playing:
            self.time = player.position

    def subscriptions(self) -> List[Any]:
        if self.playing:
            return [_core.frames(self.tick, key="designer-timeline", max_fps=30)]
        return []

    def seek(self, time: float) -> None:
        clip = self.clip
        length = clip.length if clip is not None else 0.0
        self.time = max(0.0, min(float(time), length or 0.0))
        if self._player is not None and self._player.current:
            self._player.seek(self.time)

    def seek_x(self, x: float, _y: float = 0.0) -> None:
        """Moves the playhead to ``x`` pixels along the ruler."""
        self.seek(round(max(x, 0.0) / self.px, 2))

    def scrub_move(self, x: float, _y: float = 0.0) -> None:
        self.pointer_x = x
        if self.scrubbing:
            self.seek_x(x)

    def scrub_press(self) -> None:
        self.pause()
        self.scrubbing = True
        self.seek_x(self.pointer_x)

    def scrub_release(self) -> None:
        self.scrubbing = False

    def lane_move(self, x: float, _y: float = 0.0) -> None:
        self.pointer_x = x
        if self.dragging is not None:
            self.drag_to(x)

    def add_key_at_pointer(self, path: str) -> None:
        self.add_key_x(path, self.pointer_x)

    def set_zoom(self, zoom: float) -> None:
        self.zoom = min(max(float(zoom), 0.25), 8.0)

    # -- clips ----------------------------------------------------------------------

    def _store(self, clip: Clip, old: Optional[str] = None, group: Optional[str] = None) -> None:
        self.d.doc.set_clip(clip, old=old, group=group)
        self.clip_name = clip.name

    def select_clip(self, name: str) -> None:
        self.pause()
        self.name_draft = None
        self.clip_name = name
        self.selected = None
        self.time = 0.0

    def new_clip(self) -> None:
        clip = Clip(unique_name(self.form), length=1.0)
        self._store(clip)
        self.select_clip(clip.name)

    def duplicate_clip(self) -> None:
        clip = self.clip
        if clip is not None:
            copy = replace(clip, name=unique_name(self.form, clip.name))
            self._store(copy)
            self.select_clip(copy.name)

    def rename_clip(self, name: str) -> None:
        clip = self.clip
        name = re.sub(r"[^\w-]+", "_", name.strip()).strip("_")
        if clip is None or not name or name == clip.name:
            return
        if get(self.form, name) is not None:
            name = unique_name(self.form, name)
        self._store(replace(clip, name=name), old=clip.name, group=f"clip-name:{clip.name}")

    def edit_name(self, text: str) -> None:
        self.name_draft = text

    def submit_name(self, *_: Any) -> None:
        if self.name_draft is not None:
            self.rename_clip(self.name_draft)
        self.name_draft = None

    def edit_call(self, text: str) -> None:
        self.call_draft = text

    def submit_call(self, *_: Any) -> None:
        self.add_call(self.call_draft.strip())
        self.call_draft = ""

    def delete_clip(self) -> None:
        clip = self.clip
        if clip is not None:
            self.d.doc.remove_clip(clip.name)
            self.clip_name = None
            self.selected = None
            self.time = 0.0

    def set_length(self, length: float) -> None:
        clip = self.clip
        if clip is not None and length > 0:
            self._store(replace(clip, length=round(float(length), 3)), group=f"clip-length:{clip.name}")
            self.seek(self.time)

    def set_loop(self, loop: str) -> None:
        clip = self.clip
        if clip is not None and loop in LOOPS:
            self._store(replace(clip, loop=loop))

    def toggle_autoplay(self) -> None:
        clip = self.clip
        if clip is not None:
            self.d.doc.set_autoplay("" if self.form.autoplay == clip.name else clip.name)

    # -- tracks ---------------------------------------------------------------------

    def add_track(self, path: str) -> None:
        """Adds a track with a key at the playhead holding the control's current value."""
        clip = self.clip
        if clip is None:
            self.new_clip()
            clip = self.clip
        if clip is None:
            return
        self.adding = False
        if clip.track(path) is not None:
            self.add_key(path)
            return
        value = current_value(self.form, path)
        self._store(clip.with_track(Track(path, [(round(self.position, 3), value)])))
        self.selected = (path, round(self.position, 3))

    def remove_track(self, path: str) -> None:
        clip = self.clip
        if clip is not None:
            self._store(clip.without_track(path))
            if self.selected and self.selected[0] == path:
                self.selected = None

    def toggle_track(self, path: str) -> None:
        clip = self.clip
        track = clip.track(path) if clip else None
        if clip is not None and track is not None:
            self._store(clip.with_track(replace(track, enabled=not track.enabled)))

    def set_interpolation(self, path: str, interpolation: str) -> None:
        clip = self.clip
        track = clip.track(path) if clip else None
        if clip is not None and track is not None:
            self._store(clip.with_track(replace(track, interpolation=interpolation)))

    # -- keys -----------------------------------------------------------------------

    def add_key(self, path: str, time: Optional[float] = None) -> None:
        """Adds a key at ``time`` (the playhead) with the value the track has there."""
        clip = self.clip
        track = clip.track(path) if clip else None
        if clip is None or track is None:
            return
        time = round(self.position if time is None else float(time), 3)
        value = track.value_at(time) if track.keys else current_value(self.form, path)
        self._store(clip.with_key(path, time, value))
        self.selected = (path, time)
        if time > clip.length:
            self.set_length(time)

    def add_key_x(self, path: str, x: float, _y: float = 0.0) -> None:
        self.add_key(path, round(max(x, 0.0) / self.px, 2))

    def select_key(self, path: str, time: float) -> None:
        self.selected = (path, time)
        self.seek(time)

    def delete_key(self) -> None:
        clip = self.clip
        if clip is not None and self.selected is not None:
            self._store(clip.without_key(*self.selected))
            self.selected = None

    def _replace_key(self, key: Key, *, time: Optional[float] = None, value: Any = None, easing: Any = None,
                     group: Optional[str] = None) -> None:
        clip = self.clip
        if clip is None or self.selected is None:
            return
        path = self.selected[0]
        new_time = key.time if time is None else round(max(float(time), 0.0), 3)
        new = Key(new_time, key.value if value is None else value, key.easing if easing is None else easing or None)
        edited = clip.without_key(path, key.time).with_key(path, new.time, new.value, new.easing)
        if new.time > clip.length:
            edited = replace(edited, length=new.time)
        self._store(edited, group=group)
        self.selected = (path, new.time)

    def set_key_time(self, time: float) -> None:
        key = self.key()
        if key is not None:
            self._replace_key(key, time=time, group=f"key-time:{self.selected}")

    def set_key_value(self, value: Any) -> None:
        key = self.key()
        if key is not None:
            self._replace_key(key, value=value, group=f"key-value:{self.selected}")

    def set_key_easing(self, easing: str) -> None:
        key = self.key()
        if key is not None:
            self._replace_key(key, easing=easing if easing != "track" else "")

    def start_drag(self, path: str, time: float) -> None:
        self.select_key(path, time)
        self.dragging = (path, time)

    def drag_to(self, x: float, _y: float = 0.0) -> None:
        """Moves the dragged key to ``x`` pixels along its lane (snapped to 1/100 s)."""
        if self.dragging is None:
            return
        key = self.key()
        time = round(max(x, 0.0) / self.px, 2)
        if key is not None and abs(key.time - time) > 1e-6:
            self._replace_key(key, time=time, group=f"key-drag:{self.dragging}")
            self.time = time

    def end_drag(self) -> None:
        self.dragging = None

    # -- calls ----------------------------------------------------------------------

    def add_call(self, method: str) -> None:
        clip = self.clip
        if clip is None or not method.isidentifier():
            return
        calls = tuple(c for c in clip.calls if not (abs(c.time - self.position) < 1e-6 and c.method == method))
        self._store(replace(clip, calls=calls + (Call(round(self.position, 3), method),)))

    def remove_call(self, index: int) -> None:
        clip = self.clip
        if clip is not None and 0 <= index < len(clip.calls):
            self._store(replace(clip, calls=clip.calls[:index] + clip.calls[index + 1:]))

    # -- layout helpers -------------------------------------------------------------

    def ticks(self, width: float) -> List[Tuple[float, str]]:
        """``[(x, label), ...]`` of the ruler's labelled ticks across ``width`` pixels."""
        steps = (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)
        step = next((s for s in steps if s * self.px >= 60), steps[-1])
        count = int(math.ceil(width / (step * self.px))) + 1
        return [(i * step * self.px, f"{i * step:g}s") for i in range(count)]
