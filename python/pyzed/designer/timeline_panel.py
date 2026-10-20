"""The Animation panel: a timeline editor for the form's clips, like Godot's Animation dock.

- The toolbar picks, creates, renames, duplicates and deletes clips, sets their length, loop
  and autoplay, and plays the preview (backwards, play/pause, stop).
- Each track is a row: its name, buttons to mute it, hold its values or add a key at the
  playhead, and a lane with its keys. Click the ruler to move the playhead; click a key to
  select it and drag it to move it; double-click a lane to add a key there.
- The selected key's time, value and easing are edited below the tracks; calls to the
  form's handlers sit on their own lane.

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

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

ROW = 26.0
LEFT = 240.0
RULER = 24.0
KEY = 11.0
#: Pixels before time 0, so the first keys show whole.
ORIGIN = 10.0
LOOP_LABELS = {"none": "Once", "loop": "Loop", "pingpong": "Ping-pong"}


def _lane_width(e: timeline.TimelineEditor) -> float:
    clip = e.clip
    return max((clip.length if clip else 1.0) * e.px + ORIGIN + 32, 320)


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
    layers.append(_core.pin(_core.container(width=9, height=9, bg=t.accent, radius=2), x=head - 4, y=RULER - 10))
    return _core.mouse_area(_core.stack(layers, width=width, height=RULER),
                            on_move=lambda x, y: e.scrub_move(x - ORIGIN, y),
                            on_press=e.scrub_press, on_release=e.scrub_release, cursor="pointer")


def _diamond(e: timeline.TimelineEditor, path: str, time: float, enabled: bool, t: Theme) -> Any:
    selected = e.selected is not None and e.selected[0] == path and abs(e.selected[1] - time) < 1e-6
    color = t.accent if selected else (t.text if enabled else t.text_muted)
    mark = _core.container(width=KEY - 2, height=KEY - 2, bg=color, radius=1,
                           border_color=t.background, border_width=1).style(rotate=45)
    mark = _core.container(mark, width=KEY + 4, height=KEY + 4, align_x="center", align_y="center")
    return _core.mouse_area(mark, on_press=lambda: e.start_drag(path, time), cursor="grab")


def _lane(e: timeline.TimelineEditor, track: Any, width: float, t: Theme, odd: bool) -> Any:
    layers: List[Any] = [_core.container(width=width, height=ROW, bg=t.element if odd else t.background)]
    clip = e.clip
    if clip is not None:
        end = ORIGIN + clip.length * e.px
        layers.append(_core.pin(_core.container(width=1, height=ROW, bg=t.border_variant), x=end, y=0))
    for key in track.keys:
        layers.append(_core.pin(_diamond(e, track.path, key.time, track.enabled, t),
                                x=ORIGIN + key.time * e.px - (KEY + 4) / 2, y=(ROW - KEY - 4) / 2))
    layers.append(_core.pin(_core.container(width=1, height=ROW, bg=t.accent), x=ORIGIN + e.position * e.px, y=0))
    return _core.mouse_area(_core.stack(layers, width=width, height=ROW),
                            on_move=lambda x, y: e.lane_move(x - ORIGIN, y),
                            on_release=e.end_drag,
                            on_double_click=lambda: e.add_key_at_pointer(track.path))


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
    if clip is not None:
        for index, call in enumerate(clip.calls):
            chip = _core.container(_core.text(f"{call.method}()", size=10, color=t.background), padding=(2, 5),
                                   bg=t.accent, radius=3)
            layers.append(_core.pin(_core.mouse_area(chip, on_right_press=lambda i=index: e.remove_call(i)),
                                    x=ORIGIN + call.time * e.px, y=4))
    layers.append(_core.pin(_core.container(width=1, height=ROW, bg=t.accent), x=ORIGIN + e.position * e.px, y=0))
    return _core.stack(layers, width=width, height=ROW)


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


def _inspector(e: timeline.TimelineEditor, t: Theme) -> Any:
    key = e.key()
    if key is None:
        hint = tr("Click a key to edit it. Double-click a lane to add one.")
        return _core.container(ui.label(hint, size="sm", color="text_muted", theme=t), padding=(6, 10))
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
                               icon="clapperboard", theme=t)
        return _core.column([toolbar, _core.container(empty, width="fill", height="fill", align_x="center",
                                                      align_y="center")], width="fill", height="fill")
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
        _core.scrollable(_core.column(lanes, width=width), direction="horizontal", width="fill"),
    ], width="fill")
    return _core.column([
        toolbar,
        ui.divider(theme=t),
        _core.scrollable(body, height="fill", width="fill"),
        ui.divider(theme=t),
        _inspector(e, t),
    ], width="fill", height="fill")
