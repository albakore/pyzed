"""The Animation panel: a timeline editor for the form's clips, like Godot's Animation dock.

- The toolbar picks, creates, renames, duplicates and deletes clips, sets their length, loop
  and autoplay, and plays the preview (backwards, play/pause, stop).
- Each track is a row: its name, buttons to mute it, hold its values or add a key at the
  playhead, and a lane with its keys. The ruler and the lanes are one area: press anywhere to
  move the playhead, press near a key to grab it and drag it (it snaps to the keys of other
  tracks, the start and the end), double-click a lane to add a key, right-click a key to
  delete it. Calls to the form's handlers sit on their own lane and drag the same way.
- The selected key's time, value and easing are edited below the tracks. With the pointer
  over the panel, Delete removes the selected key, Space plays, the arrows nudge.

The canvas follows the playhead (see ``TimelineEditor.target``), so scrubbing shows each
frame of the animation on the form.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List

from .. import _core, ui
from ..animation_player import LOOPS
from ..theme import Theme
from . import motion
from . import timeline
from .locale import tr
from .timeline import ORIGIN, ROW, RULER

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

LEFT = 240.0
#: The size of a key's diamond (the pointer grabs it from ``timeline.HIT`` pixels away).
KEY = 12.0
LOOP_LABELS = {"none": "Once", "loop": "Loop", "pingpong": "Ping-pong"}


def _lane_width(e: timeline.TimelineEditor) -> float:
    clip = e.clip
    return max((clip.length if clip else 1.0) * e.px + ORIGIN + 32, 640)


def _toolbar(d: "Designer", e: timeline.TimelineEditor, t: Theme) -> Any:
    clip = e.clip
    names = [c.name for c in e.clips]
    start: List[Any] = []
    if names:
        start.append(ui.select(names, clip.name if clip else None, e.select_clip, size="sm", width=130, theme=t))
    start.append(ui.icon_button("plus", e.new_clip, size="sm", tooltip=tr("New animation"), theme=t))
    if clip is not None:
        start += [
            ui.icon_button("copy", e.duplicate_clip, size="sm", tooltip=tr("Duplicate animation"), theme=t),
            ui.icon_button("trash-2", e.delete_clip, size="sm", tooltip=tr("Delete animation"), theme=t),
            ui.divider(vertical=True, theme=t),
            ui.icon_button("skip-back", e.stop, size="sm", tooltip=tr("Back to the start"), theme=t),
            ui.icon_button("rewind", lambda: e.play(backwards=True), size="sm", tooltip=tr("Play backwards"),
                           theme=t),
            ui.icon_button("pause" if e.playing else "play", e.toggle, size="sm", selected=e.playing,
                           tooltip=tr("Play or pause"), theme=t),
            ui.label(f"{e.position:.2f} / {clip.length:.2f} s", size="sm", mono=True, color="text_muted",
                     theme=t),
        ]
    end: List[Any] = []
    if clip is not None:
        end += [
            ui.input(clip.name if e.name_draft is None else e.name_draft, e.edit_name, on_submit=e.submit_name,
                     size="sm", width=110, id="timeline-clip-name", theme=t),
            ui.number_field(clip.length, e.set_length, min=0.05, max=600, step=0.1, width=96, suffix="s", theme=t),
            ui.select([tr(LOOP_LABELS[loop]) for loop in LOOPS], tr(LOOP_LABELS[clip.loop]),
                      lambda label: e.set_loop(next(k for k, v in LOOP_LABELS.items() if tr(v) == label)),
                      size="sm", width=110, theme=t),
            ui.icon_button("zap", e.toggle_autoplay, size="sm", selected=d.doc.form.autoplay == clip.name,
                           tooltip=tr("Play when the form opens"), theme=t),
            ui.divider(vertical=True, theme=t),
            ui.icon_button("zoom-out", lambda: e.set_zoom(e.zoom / 1.5), size="sm", tooltip=tr("Zoom out"), theme=t),
            ui.icon_button("zoom-in", lambda: e.set_zoom(e.zoom * 1.5), size="sm", tooltip=tr("Zoom in"), theme=t),
        ]
    return ui.toolbar(start, end, height=36, theme=t)


def _ruler(e: timeline.TimelineEditor, width: float, t: Theme) -> Any:
    layers: List[Any] = [_core.container(width=width, height=RULER, bg=t.elevated)]
    for x, text in e.ticks(width):
        layers.append(_core.pin(_core.container(width=1, height=8, bg=t.border), x=ORIGIN + x, y=RULER - 8))
        layers.append(_core.pin(_core.text(text, size=10, color=t.text_muted), x=ORIGIN + x + 3, y=3))
    head = ORIGIN + e.position * e.px
    layers.append(_core.pin(_core.container(width=11, height=11, bg=t.accent, radius=2), x=head - 5, y=RULER - 12))
    return _core.stack(layers, width=width, height=RULER)


def _after_end(e: timeline.TimelineEditor, width: float, t: Theme) -> List[Any]:
    """The line at the clip's end and the dimmed time after it."""
    clip = e.clip
    if clip is None:
        return []
    end = ORIGIN + clip.length * e.px
    return [_core.pin(_core.container(width=max(width - end, 0), height=ROW, bg=t.background).style(opacity=0.5),
                      x=end, y=0),
            _core.pin(_core.container(width=1, height=ROW, bg=t.border_variant), x=end, y=0)]


def _diamond(e: timeline.TimelineEditor, path: str, time: float, enabled: bool, t: Theme) -> Any:
    selected = e.selected is not None and e.selected[0] == path and abs(e.selected[1] - time) < 1e-6
    hovered = e.hover is not None and e.hover[0] == "key" and e.hover[1] == path and abs(e.hover[2] - time) < 1e-6
    size = KEY + 2 if hovered or selected else KEY
    color = t.accent if selected else (t.text if enabled else t.text_muted)
    mark = _core.container(width=size - 2, height=size - 2, bg=color, radius=1,
                           border_color=t.accent if hovered else t.background, border_width=1).style(rotate=45)
    return _core.container(mark, width=KEY + 6, height=KEY + 6, align_x="center", align_y="center")


def _key_label(e: timeline.TimelineEditor, track: Any, time: float, t: Theme) -> Any:
    """A chip with the time and value of the key under the pointer (or being dragged)."""
    key = next((k for k in track.keys if abs(k.time - time) < 1e-6), None)
    value = "" if key is None else key.value
    if isinstance(value, float):
        value = f"{value:.3g}"
    text = f"{time:.2f}s · {value}"
    return _core.container(_core.text(text, size=10, color=t.text), padding=(1, 5), bg=t.elevated, radius=3,
                           border_color=t.border, border_width=1)


def _lane(e: timeline.TimelineEditor, track: Any, width: float, t: Theme, odd: bool) -> Any:
    layers: List[Any] = [_core.container(width=width, height=ROW, bg=t.element if odd else t.background)]
    layers += _after_end(e, width, t)
    for key in track.keys:
        layers.append(_core.pin(_diamond(e, track.path, key.time, track.enabled, t),
                                x=ORIGIN + key.time * e.px - (KEY + 6) / 2, y=(ROW - KEY - 6) / 2))
    layers.append(_core.pin(_core.container(width=1, height=ROW, bg=t.accent), x=ORIGIN + e.position * e.px, y=0))
    shown = e.selected if e.dragging is not None else (e.hover[1:] if e.hover and e.hover[0] == "key" else None)
    if shown is not None and shown[0] == track.path:
        layers.append(_core.pin(_key_label(e, track, shown[1], t), x=ORIGIN + shown[1] * e.px + KEY, y=6))
    return _core.stack(layers, width=width, height=ROW)


def _track_head(e: timeline.TimelineEditor, track: Any, t: Theme) -> Any:
    held = track.interpolation == "discrete"
    return _core.container(_core.row([
        ui.icon_button("eye" if track.enabled else "eye-off", lambda: e.toggle_track(track.path), size="xs",
                       tooltip=tr("Mute or play this track"), theme=t),
        _core.container(ui.label(timeline.label(track.path), size="sm", color="text" if track.enabled else "text_muted",
                                 wrap=False, theme=t), width="fill", clip=True),
        ui.icon_button("step-forward" if held else "spline", lambda: e.set_interpolation(
            track.path, "linear" if held else "discrete"), size="xs", selected=held,
            tooltip=tr("Hold each value until the next key"), theme=t),
        ui.icon_button("key-round", lambda: e.add_key(track.path), size="xs", tooltip=tr("Add a key at the playhead"),
                       theme=t),
        ui.icon_button("x", lambda: e.remove_track(track.path), size="xs", tooltip=tr("Remove track"), theme=t),
    ], spacing=2, align="center"), width=LEFT, height=ROW, padding=(0, 6))


def _calls_lane(e: timeline.TimelineEditor, width: float, t: Theme) -> Any:
    clip = e.clip
    layers: List[Any] = [_core.container(width=width, height=ROW, bg=t.elevated)]
    layers += _after_end(e, width, t)
    if clip is not None:
        for index, call in enumerate(clip.calls):
            hovered = e.hover == ("call", index) or e.dragging_call == index
            chip = _core.container(_core.text(f"{call.method}()", size=10, color=t.background), padding=(3, 6),
                                   bg=t.accent, radius=3, border_color=t.text if hovered else t.accent,
                                   border_width=1)
            layers.append(_core.pin(chip, x=ORIGIN + call.time * e.px, y=6))
    layers.append(_core.pin(_core.container(width=1, height=ROW, bg=t.accent), x=ORIGIN + e.position * e.px, y=0))
    return _core.stack(layers, width=width, height=ROW)


def _lanes(e: timeline.TimelineEditor, lanes: List[Any], width: float) -> Any:
    """The ruler and the lanes as one pointer area (see ``TimelineEditor.pointer_press``)."""
    return _core.mouse_area(_core.column(lanes, width=width), on_move=e.pointer_move, on_press=e.pointer_press,
                            on_release=e.pointer_release, on_double_click=e.pointer_double_click,
                            on_right_press=e.pointer_right_press, cursor=e.cursor())


def _add_track(d: "Designer", e: timeline.TimelineEditor, t: Theme) -> Any:
    """The "add track" button and, while it is open, the properties of the selected control."""
    control = d.doc.primary
    if not e.adding:
        text = tr("Add track for {name}", name=control.name) if control is not None else tr("Select a control to animate it")
        return _core.container(ui.button(text, lambda: setattr(e, "adding", True), icon="plus", variant="ghost",
                                         size="sm", disabled=control is None, theme=t), width=LEFT, padding=(4, 6))
    items: List[Any] = [tr("Animate {name}", name=control.name) if control else tr("Select a control to animate it")]
    if control is not None:
        clip = e.clip
        for path, text in timeline.track_paths(control):
            exists = clip is not None and clip.track(path) is not None
            items.append(ui.MenuItem(text, lambda p=path: e.add_track(p), checked=exists,
                                     icon="box" if ":" in path and not path.startswith(":") else "sliders-horizontal"))
    items += [ui.SEPARATOR, ui.MenuItem(tr("Cancel"), lambda: setattr(e, "adding", False), icon="x")]
    return _core.container(ui.menu(items, width=LEFT - 12, theme=t), width=LEFT, padding=(4, 6))


def _value_editor(e: timeline.TimelineEditor, key: Any, t: Theme) -> Any:
    value = key.value
    if isinstance(value, bool):
        return ui.switch(value, e.set_key_value, theme=t)
    if isinstance(value, (int, float)):
        step = 0.01 if isinstance(value, float) and abs(value) <= 2 else 1
        return ui.number_field(float(value), e.set_key_value, step=step, width=140, theme=t)
    return ui.input("" if value is None else str(value), e.set_key_value, size="sm", width=180, theme=t)


def play_line(name: str) -> str:
    """The line of handler code that plays clip ``name``."""
    return f'form.animations.play("{name}")'


def _how_it_plays(d: "Designer", e: timeline.TimelineEditor, t: Theme) -> Any:
    """What starts the clip: autoplay, or the line a handler calls (with a copy button)."""
    clip = e.clip
    if clip is None:
        return _core.space(width=0)
    if d.doc.form.autoplay == clip.name:
        return ui.label(tr("Plays when the form opens."), size="sm", color="text_muted", wrap=False, theme=t)
    line = play_line(clip.name)
    return _core.row([
        ui.label(tr("Play it from a handler:"), size="sm", color="text_muted", wrap=False, theme=t),
        _core.container(ui.label(line, size="sm", mono=True, wrap=False, theme=t), padding=(1, 6), bg=t.element,
                        radius=t.radius_sm),
        ui.icon_button("copy", lambda: _core.Command.copy(line), size="xs", tooltip=tr("Copy"), theme=t),
    ], spacing=6, align="center")


def _inspector(d: "Designer", e: timeline.TimelineEditor, t: Theme) -> Any:
    key = e.key()
    if key is None:
        hint = tr("Click to move the playhead, drag a key to move it, double-click a lane to add a key, "
                  "right-click a key to delete it.")
        return _core.container(_core.row([
            _core.container(ui.label(hint, size="sm", color="text_muted", theme=t), width="fill"),
            _how_it_plays(d, e, t),
        ], spacing=12, align="center"), padding=(6, 10), width="fill")
    easings = ["track", *motion.EASINGS]
    current = key.easing if isinstance(key.easing, str) else "track"
    return _core.container(_core.row([
        ui.label(timeline.label(e.selected[0]), size="sm", weight="semibold", theme=t),  # type: ignore[index]
        ui.label(tr("Time"), size="sm", color="text_muted", theme=t),
        ui.number_field(key.time, e.set_key_time, min=0, step=0.05, width=110, suffix="s", theme=t),
        ui.label(tr("Value"), size="sm", color="text_muted", theme=t),
        _value_editor(e, key, t),
        ui.label(tr("Easing"), size="sm", color="text_muted", theme=t),
        ui.select([tr(motion.label(x)) if x != "track" else tr("Track's") for x in easings],
                  tr(motion.label(current)) if current != "track" else tr("Track's"),
                  lambda label: e.set_key_easing(next(
                      (x for x in easings if (tr(motion.label(x)) if x != "track" else tr("Track's")) == label), "track")),
                  size="sm", width=160, theme=t),
        ui.icon_button("trash-2", e.delete_key, size="sm", tooltip=tr("Delete key"), theme=t),
    ], spacing=8, align="center"), padding=(4, 10))


def view(d: "Designer", t: Theme) -> Any:
    """The Animation panel's body."""
    e = d.timeline
    clip = e.clip
    toolbar = _toolbar(d, e, t)
    if clip is None:
        empty = ui.empty_state(tr("No animations yet"), tr("Create one to animate this form's controls over time."),
                               icon="clapperboard", actions=[ui.button(tr("New animation"), e.new_clip, icon="plus", size="sm", theme=t)],
                               theme=t)
        steps = _core.column([
            ui.label(tr(text), size="sm", color="text_muted", theme=t) for text in (
                "1. Select a control on the form and press Add track.",
                "2. Move the playhead and double-click the lane to add keys; edit each key's value below.",
                "3. Press ▶ to preview it. Turn on ⚡ to play it when the form opens, or call "
                "form.animations.play(\"name\") from a handler.",
            )], spacing=4)
        return _core.column([toolbar, _core.container(_core.column([empty, steps], spacing=16, align="center"),
                                                      width="fill", height="fill", align_x="center",
                                                      align_y="center", padding=16)], width="fill", height="fill")
    width = _lane_width(e)
    heads: List[Any] = [_core.container(ui.label(tr("Tracks"), size="sm", weight="semibold", theme=t), width=LEFT,
                                        height=RULER, padding=(4, 8))]
    lanes: List[Any] = [_ruler(e, width, t)]
    for i, track in enumerate(clip.tracks):
        heads.append(_track_head(e, track, t))
        lanes.append(_lane(e, track, width, t, i % 2 == 1))
    heads.append(_core.container(_core.row([
        ui.label(tr("Calls"), size="sm", color="text_muted", theme=t),
        _core.space(width="fill"),
        ui.input(e.call_draft, e.edit_call, on_submit=e.submit_call, placeholder=tr("handler name"), size="sm",
                 width=120, id="timeline-call", theme=t),
    ], align="center", spacing=6), width=LEFT, height=ROW, padding=(0, 6)))
    lanes.append(_calls_lane(e, width, t))
    body = _core.row([
        _core.column([*heads, _add_track(d, e, t)], width=LEFT),
        ui.divider(vertical=True, theme=t),
        _core.scrollable(_lanes(e, lanes, width), direction="horizontal", width="fill"),
    ], width="fill")
    return _core.column([
        toolbar,
        ui.divider(theme=t),
        _core.scrollable(body, height="fill", width="fill"),
        ui.divider(theme=t),
        _inspector(d, e, t),
    ], width="fill", height="fill")
