"""Drag and drop: pick things up, move them, drop them somewhere else.

Three building blocks cover what apps such as Trello, form builders, page builders or Figma
do with the mouse (and the finger)::

    pz.draggable(card, "card-1", data=card_data)        # something the pointer picks up
    pz.droppable(trash, "trash", on_drop=self.delete)   # a place that takes it
    pz.sortable(cards, "todo", keys=ids, group="cards", on_reorder=self.move)  # a list that reorders

Everything that moves while dragging runs natively, frame by frame, without calling Python:
the preview that follows the pointer (lifted with a shadow), the items that slide aside to
open a gap, the shadow (or translucent ghost) where the item will land, snapping to a grid and
alignment guides, the wire of a node editor, scrolling near the edges and the flight to the
landing place on drop (or back home when cancelled with Escape). Python hears about the
moments that matter, with a :class:`DragEvent`:

- the draggable's ``on_drag_start``, ``on_drag_move`` and ``on_drag_end`` (``event.dropped``),
- the target's ``on_enter``, ``on_over`` (the landing place changed), ``on_leave`` and
  ``on_drop`` (a sortable's ``on_reorder``).

Who can drop where is decided by ``type`` (on the draggable, a sortable's ``group``) and
``accepts`` (on the target), and by ``can_drop``, a function asked once per drag. Sortables add
``pull`` (``False``: items can't leave; ``"clone"``: they are copied, like a palette), ``put``,
``sort`` and ``max_items``. Handles (:func:`drag_handle`), axis locks, bounds, delays for touch
screens and keyboard reordering are options of their own.

:func:`move` and :func:`reorder` apply a drop to your lists, so most handlers are one line.
"""

from __future__ import annotations

import copy as _copy
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from . import _core
from .events import accepts_argument
from .theme import Theme, alpha, current as _current_theme

__all__ = [
    "DragEvent",
    "cancel",
    "current",
    "drag_handle",
    "draggable",
    "droppable",
    "move",
    "reorder",
    "sortable",
]

drag_handle = _core.drag_handle

Style = Union[None, bool, str, Dict[str, Any]]


class DragEvent:
    """What a drag and drop handler receives.

    ``type`` is what happened: ``"start"``, ``"move"``, ``"enter"``, ``"over"``, ``"leave"``,
    ``"drop"``, ``"end"`` or ``"cancel"`` (and ``"check"`` for ``can_drop``).

    About the dragged item: ``source`` (the draggable's id or the sortable item's key), ``data``
    (its ``data``, or the item of a sortable built from ``items``; ``item`` is the same),
    ``types``, ``from_list``/``from_index`` (when it comes from a sortable), ``width``/``height``
    and ``copy`` (the source list copies, or Alt is held).

    About the target (``None`` outside one): ``target`` (its id), ``index`` (where it goes in a
    sortable, counted without the item itself), ``combine`` (the key of the item it is dropped
    onto, with ``combine=True``), ``x``/``y`` (the pointer inside the target) and
    ``item_x``/``item_y`` (the item's top-left inside the target, snapped and aligned: where to
    put it on a free canvas).

    Also ``window_x``/``window_y`` (the pointer in the window), ``dx``/``dy`` (moved since the
    start), ``dropped`` (for ``"end"``) and the modifiers ``shift``, ``ctrl``, ``alt``, ``logo``.
    """

    __slots__ = ("type", "source", "data", "types", "target", "index", "combine", "from_list",
                 "from_index", "copy", "x", "y", "item_x", "item_y", "window_x", "window_y", "dx",
                 "dy", "width", "height", "dropped", "shift", "ctrl", "alt", "logo")

    def __init__(self, type: str = "drop", *, source: Any = None, data: Any = None,  # noqa: A002
                 types: Sequence[str] = (), target: Optional[str] = None, index: Optional[int] = None,
                 combine: Optional[str] = None, from_list: Optional[str] = None,
                 from_index: Optional[int] = None, copy: bool = False, x: float = 0.0, y: float = 0.0,
                 item_x: float = 0.0, item_y: float = 0.0, window_x: float = 0.0, window_y: float = 0.0,
                 dx: float = 0.0, dy: float = 0.0, width: float = 0.0, height: float = 0.0,
                 dropped: bool = False, shift: bool = False, ctrl: bool = False, alt: bool = False,
                 logo: bool = False) -> None:
        self.type = type
        self.source, self.data, self.types = source, data, tuple(types)
        self.target, self.index, self.combine = target, index, combine
        self.from_list, self.from_index, self.copy = from_list, from_index, copy
        self.x, self.y, self.item_x, self.item_y = x, y, item_x, item_y
        self.window_x, self.window_y, self.dx, self.dy = window_x, window_y, dx, dy
        self.width, self.height, self.dropped = width, height, dropped
        self.shift, self.ctrl, self.alt, self.logo = shift, ctrl, alt, logo

    @property
    def item(self) -> Any:
        """The dragged item (same as ``data``)."""
        return self.data

    @property
    def within(self) -> bool:
        """Whether it is dropped on the sortable it comes from (a reorder, not a move)."""
        return self.from_list is not None and self.from_list == self.target

    @property
    def position(self) -> Tuple[float, float]:
        """``(x, y)``: the pointer inside the target."""
        return (self.x, self.y)

    @property
    def item_position(self) -> Tuple[float, float]:
        """``(item_x, item_y)``: the item's top-left inside the target."""
        return (self.item_x, self.item_y)

    def __repr__(self) -> str:
        shown = [f"{n}={getattr(self, n)!r}" for n in self.__slots__[1:]
                 if getattr(self, n) not in (None, (), 0.0, False) and n not in ("data",)]
        return f"DragEvent({self.type!r}, {', '.join(shown)})"


def _adapt(handler: Any) -> Any:
    """``handler`` as something the native side calls with the event."""
    if handler is None or not callable(handler):
        return None if handler is None else (lambda _event, message=handler: message)
    if accepts_argument(handler):
        return handler
    return lambda _event, fn=handler: fn()


def _check(predicate: Callable[..., Any], event: DragEvent) -> bool:
    """Asks a ``can_drop`` (with or without the event) whether the drag may drop."""
    return bool(predicate(event) if accepts_argument(predicate) else predicate())


def _look(value: Style, default: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """A highlight option: ``True``/``"auto"`` (the default look), ``False``/``None``, a color
    (the border) or a dict of ``background``, ``border_color``, ``border_width``, ``radius``."""
    if value is True or value == "auto":
        return dict(default)
    if not value:
        return None
    if isinstance(value, str):
        return {**default, "border_color": value}
    return {**default, **value}


def _theme(theme: Optional[Theme]) -> Theme:
    return theme or _current_theme()


def _common(t: Theme, opts: Dict[str, Any]) -> None:
    shadow = opts.get("shadow", True)
    opts["shadow"] = ("#00000059" if shadow is True else shadow) or None
    if opts.get("wire_color") is None:
        opts["wire_color"] = t.accent


def draggable(
    content: Any,
    id: Any,  # noqa: A002
    *,
    data: Any = None,
    type: Union[str, Sequence[str]] = "item",  # noqa: A002
    preview: Any = None,
    handle: bool = False,
    disabled: bool = False,
    axis: Optional[str] = None,
    bounds: Optional[str] = None,
    grid: Union[None, float, Tuple[float, float]] = None,
    threshold: float = 4,
    delay: float = 0,
    source: Optional[str] = None,
    source_opacity: float = 0.35,
    lift: float = 1.03,
    shadow: Union[bool, str] = True,
    opacity: float = 1.0,
    radius: float = 6,
    wire_color: Optional[str] = None,
    wire_width: float = 2,
    drop_animation: float = 180,
    from_children: bool = False,
    cursor: bool = True,
    on_drag_start: Any = None,
    on_drag_move: Any = None,
    on_drag_end: Any = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """Lets the pointer pick ``content`` up and drop it on a :func:`droppable` or :func:`sortable`.

    ``id`` names it (unique in the window) and ``data`` is what targets get as ``event.data``.
    ``type`` (a name or several) is what targets match with ``accepts``.

    Look while dragged: ``preview`` is what follows the pointer (by default a copy of
    ``content``; another widget; ``"wire"``, a curve from where it started, for connecting nodes;
    or ``"none"``), lifted to ``lift`` times its size with a ``shadow`` (a color, or ``False``)
    and ``opacity``. ``source`` is how the original looks meanwhile: ``"ghost"`` (faded to
    ``source_opacity``, the default), ``"hide"`` (gone: the item itself seems to move) or
    ``"keep"`` (the default for wires).
    On drop the preview flies to its landing place in ``drop_animation`` milliseconds.

    Limits: ``handle=True`` starts the drag only from a :func:`drag_handle` inside;
    ``axis="x"``/``"y"`` locks the movement; ``bounds="parent"`` keeps it inside the closest
    target around it (``"window"`` inside the window); ``grid`` (pixels, or ``(x, y)``) moves it
    in steps; ``threshold`` is how far the pointer moves before a press becomes a drag and
    ``delay`` (milliseconds) asks for a long press instead (touch screens, lists that scroll).
    Presses that a button or input inside takes don't start drags unless ``from_children``.
    ``disabled`` turns it off. ``cursor=False`` keeps the pointer's own cursor.

    Events:
    - `on_drag_start(event)`: The drag began.
    - `on_drag_move(event)`: The pointer moved while dragging (``event.window_x``, ``event.dx``...).
    - `on_drag_end(event)`: The drag ended: ``event.dropped`` says if a target took it.
    """
    t = _theme(theme)
    if source is None:
        source = "keep" if preview in ("wire", "none") else "ghost"
    opts: Dict[str, Any] = dict(
        id=str(id), data=data, type=type, handle=handle, disabled=disabled, axis=axis, bounds=bounds,
        grid=grid, threshold=threshold, delay=delay, source=source, source_opacity=source_opacity,
        lift=lift, shadow=shadow, opacity=opacity, radius=radius, wire_color=wire_color,
        wire_width=wire_width, drop_animation=drop_animation, from_children=from_children,
        cursor=cursor, on_drag_start=_adapt(on_drag_start), on_drag_move=_adapt(on_drag_move),
        on_drag_end=_adapt(on_drag_end),
    )
    widget = None
    if isinstance(preview, str):
        opts["preview_mode"] = preview
    elif preview is not None:
        widget = preview
    _common(t, opts)
    return _core._draggable(content, widget, opts)


def _target_defaults(t: Theme) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    over = {"background": alpha(t.accent, 0.08), "border_color": t.accent, "border_width": 1.5, "radius": 6}
    active = {"border_color": alpha(t.accent, 0.45), "border_width": 1, "radius": 6}
    shadow = {"background": alpha(t.accent, 0.12), "border_color": alpha(t.accent, 0.55), "border_width": 1.5,
              "radius": 6}
    return over, active, shadow


def droppable(
    content: Any,
    id: Any,  # noqa: A002
    *,
    accepts: Union[None, str, Sequence[str]] = None,
    can_drop: Optional[Callable[..., bool]] = None,
    disabled: bool = False,
    snap: Union[None, float, Tuple[float, float]] = None,
    guides: bool = False,
    snap_preview: Optional[bool] = None,
    placeholder: str = "none",
    placeholder_style: Style = True,
    ghost_opacity: float = 0.4,
    over_style: Style = True,
    active_style: Style = False,
    guide_color: Optional[str] = None,
    on_drop: Any = None,
    on_enter: Any = None,
    on_leave: Any = None,
    on_over: Any = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """Makes ``content`` a place where dragged items can be dropped.

    ``accepts`` lists the draggable ``type``\\ s it takes (``None``: all; ``"*"`` too) and
    ``can_drop(event)`` decides with any rule of yours (asked once per drag; ``event.data`` is
    the dragged item). ``disabled`` refuses everything. A refused drag shows a "not allowed"
    cursor over it.

    Free canvases (Figma-like): the drop event's ``item_x``/``item_y`` is where the item's
    top-left lands inside the target. ``snap`` (pixels or ``(x, y)``) rounds it to a grid and
    ``guides=True`` aligns it with the edges and centers of the other draggables inside (and of
    the target), drawing the guides in ``guide_color``. With ``snap_preview`` (on by default
    when snapping) the preview itself jumps to that place.

    Look: ``over_style`` while a drag it takes is over it and ``active_style`` while one is in
    progress anywhere (``True``: the theme's look; a color; a dict of ``background``,
    ``border_color``, ``border_width``, ``radius``; ``False``). ``placeholder="shadow"`` shows
    where the item would land (``placeholder_style``) and ``"ghost"`` a translucent copy.

    Events:
    - `on_drop(event)`: An item was dropped on it.
    - `on_enter(event)`: A drag it takes came over it.
    - `on_over(event)`: The landing place changed (``event.item_x``, ``event.x``...).
    - `on_leave(event)`: The drag left it (or was cancelled).
    """
    t = _theme(theme)
    over, active, shadow = _target_defaults(t)
    opts: Dict[str, Any] = dict(
        id=str(id), accepts=accepts, can_drop=can_drop, disabled=disabled, snap=snap, guides=guides,
        snap_preview=bool(snap or guides) if snap_preview is None else snap_preview,
        placeholder=placeholder, placeholder_style=_look(placeholder_style, shadow), ghost_opacity=ghost_opacity,
        over_style=_look(over_style, over), active_style=_look(active_style, active),
        guide_color=guide_color or "#e04fa0",
        on_drop=_adapt(on_drop), on_enter=_adapt(on_enter), on_leave=_adapt(on_leave), on_over=_adapt(on_over),
    )
    return _core._droppable(content, opts)


def _default_key(item: Any) -> Any:
    if isinstance(item, dict) and "id" in item:
        return item["id"]
    ident = getattr(item, "id", None)
    return item if ident is None else ident


# The item each keyboard-sortable list has picked up (``space``), by list id.
_PICKED: Dict[str, str] = {}


def _keyboard(child: Any, list_id: str, key: str, index: int, count: int, data: Any, direction: str,
              handler: Any, group: Any) -> Any:
    back, forward = (("left", "right") if direction == "horizontal" else ("up", "down"))
    keys = [f"alt-{back}", f"alt-{forward}", "space", "escape", back, forward]

    def on_key(combo: str) -> Any:
        picked = _PICKED.get(list_id) == key
        step = 0
        if combo == "space":
            if picked:
                _PICKED.pop(list_id, None)
            else:
                _PICKED[list_id] = key
            return None
        if combo == "escape":
            _PICKED.pop(list_id, None)
            return None
        if combo in (f"alt-{back}", f"alt-{forward}") or (picked and combo in (back, forward)):
            step = -1 if combo.endswith(back) else 1
        if not step:
            return _core.Command.focus_previous() if combo == back else _core.Command.focus_next()
        to = min(max(index + step, 0), count - 1)
        if to == index or handler is None:
            return None
        event = DragEvent("drop", source=key, data=data, types=(group,) if isinstance(group, str) else tuple(group or ()),
                          target=list_id, index=to, from_list=list_id, from_index=index)
        return handler(event)

    return _core.focusable(child, on_key, keys=keys, id=f"{list_id}:{key}")


def sortable(
    children: Optional[Iterable[Any]] = None,
    id: Any = "list",  # noqa: A002
    *,
    items: Optional[Sequence[Any]] = None,
    item: Optional[Callable[[Any], Any]] = None,
    key: Optional[Callable[[Any], Any]] = None,
    keys: Optional[Sequence[Any]] = None,
    data: Optional[Sequence[Any]] = None,
    group: Union[None, str, Sequence[str]] = None,
    accepts: Union[None, str, Sequence[str]] = None,
    direction: str = "vertical",
    spacing: float = 8,
    line_spacing: Optional[float] = None,
    width: Any = None,
    height: Any = None,
    padding: Any = None,
    align: Optional[str] = None,
    handle: bool = False,
    lock_axis: bool = False,
    sort: bool = True,
    pull: Union[bool, str] = True,
    put: bool = True,
    max_items: Optional[int] = None,
    combine: bool = False,
    locked: Optional[Iterable[Any]] = None,
    disabled: bool = False,
    draggable: bool = True,
    can_drop: Optional[Callable[..., bool]] = None,
    placeholder: str = "shadow",
    placeholder_style: Style = True,
    ghost_opacity: float = 0.4,
    over_style: Style = False,
    active_style: Style = False,
    source: str = "hide",
    preview: Optional[str] = None,
    lift: float = 1.03,
    shadow: Union[bool, str] = True,
    opacity: float = 1.0,
    radius: float = 6,
    threshold: float = 4,
    delay: float = 0,
    drop_animation: float = 180,
    animation: float = 200,
    from_children: bool = False,
    keyboard: bool = False,
    on_reorder: Any = None,
    on_drop: Any = None,
    on_enter: Any = None,
    on_leave: Any = None,
    on_over: Any = None,
    on_drag_start: Any = None,
    on_drag_end: Any = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A list (or row, or wrapping grid) whose items can be dragged to a new place.

    Give the children with ``keys`` (stable ids: they keep each item's animation while the
    order changes), or ``items`` with ``item(x)`` to draw one and ``key(x)`` to name it (its
    ``id`` by default). Python keeps the order: ``on_reorder(event)`` says where an item went
    (``event.from_index`` → ``event.index``, both counted in the final list) and
    :func:`reorder`/:func:`move` apply it. Until then the other items slide out of the way, a
    ``placeholder`` (``"shadow"``, ``"ghost"`` or ``"none"``) shows the landing place and, when
    the order changes, items glide to their new places in ``animation`` milliseconds (also when
    the order changes from code; ``draggable=False`` keeps only that).

    ``direction`` is ``"vertical"``, ``"horizontal"`` or ``"wrap"`` (rows that wrap: a grid of
    cards), with ``spacing``, ``line_spacing``, ``width``, ``height``, ``padding`` and
    ``align`` (``"start"``, ``"center"``, ``"end"`` across the list).

    Several lists: the same ``group`` lets items move between them (a Kanban board); ``accepts``
    takes other groups or draggable types (drop a :func:`draggable` from a palette into the
    list). ``pull=False`` keeps items in their list, ``pull="clone"`` copies them out (the
    palette of a form builder), ``put=False`` takes nothing in, ``sort=False`` doesn't reorder
    inside, ``max_items`` caps how many it holds, ``can_drop(event)`` adds your own rule and
    ``locked`` lists keys that can't be dragged. ``combine=True`` lets an item be dropped onto
    another one (``event.combine`` is its key): folders, groups, merging.

    Items: ``handle=True`` drags them only from a :func:`drag_handle`; ``lock_axis`` keeps them
    on the list's axis and inside it; ``source``, ``preview``, ``lift``, ``shadow``,
    ``opacity``, ``radius``, ``threshold``, ``delay`` and ``drop_animation`` are as in
    :func:`draggable` (``preview="none"`` moves the items without a preview; ``source="ghost"``
    shows the faded item at its landing place, as ``placeholder="ghost"``).
    ``keyboard=True`` lets the focused item move with Alt+arrows (or Space, arrows, Space).

    Events:
    - `on_reorder(event)`: An item was dropped in the list (``on_drop`` is the same).
    - `on_enter(event)`: A drag it takes came over the list.
    - `on_over(event)`: The landing index changed (``event.index``, ``event.combine``).
    - `on_leave(event)`: The drag left the list.
    - `on_drag_start(event)`: One of its items started moving.
    - `on_drag_end(event)`: One of its items was dropped (anywhere) or the drag was cancelled.
    """
    t = _theme(theme)
    list_id = str(id)
    if items is not None:
        items = list(items)
        name = key or _default_key
        if keys is None:
            keys = [name(x) for x in items]
        if data is None:
            data = items
        if children is None:
            if item is None:
                raise TypeError("sortable(items=...) needs item=: a function that draws one item")
            children = [item(x) for x in items]
    children = list(children or [])
    if keys is None:
        keys = list(range(len(children)))
    keys = [str(k) for k in keys]
    if len(keys) != len(children):
        raise ValueError(f"sortable got {len(children)} children and {len(keys)} keys")
    if len(set(keys)) != len(keys):
        raise ValueError("sortable keys must be unique")
    if source == "ghost":
        # The others close the item's slot, so its faded copy shows where it will land instead.
        source = "hide"
        placeholder = "ghost"
        ghost_opacity = min(ghost_opacity, 0.4)
    handler = _adapt(on_reorder if on_reorder is not None else on_drop)
    if keyboard:
        children = [
            _keyboard(c, list_id, k, i, len(children), None if data is None else data[i], direction, handler,
                      group if group is not None else f"sortable:{list_id}")
            for i, (c, k) in enumerate(zip(children, keys))
        ]
    over, active, shadow_look = _target_defaults(t)
    opts: Dict[str, Any] = dict(
        id=list_id, keys=keys, data=data, group=group, accepts=accepts, direction=direction, spacing=spacing,
        line_spacing=line_spacing, width=width, height=height, padding=padding, align=align, handle=handle,
        lock_axis=lock_axis, sort=sort, pull=pull, put=put, max_items=max_items, combine=combine,
        locked=None if locked is None else [str(k) for k in locked], disabled=disabled, draggable=draggable,
        can_drop=can_drop, placeholder=placeholder, placeholder_style=_look(placeholder_style, shadow_look),
        ghost_opacity=ghost_opacity, over_style=_look(over_style, over), active_style=_look(active_style, active),
        source=source, preview_mode=preview, lift=lift, shadow=shadow, opacity=opacity, radius=radius,
        threshold=threshold, delay=delay, drop_animation=drop_animation, animation=animation,
        from_children=from_children, on_drop=handler, on_enter=_adapt(on_enter), on_leave=_adapt(on_leave),
        on_over=_adapt(on_over), on_drag_start=_adapt(on_drag_start), on_drag_end=_adapt(on_drag_end),
    )
    if isinstance(group, str):
        opts["group"] = [group]
    if accepts is not None and group is not None:
        # A list with a group and accepts takes both.
        own = [group] if isinstance(group, str) else list(group)
        extra = [accepts] if isinstance(accepts, str) else list(accepts)
        opts["accepts"] = own + [a for a in extra if a not in own]
    _common(t, opts)
    return _core._sortable(children, opts)


def current() -> Optional[DragEvent]:
    """The drag in progress (a :class:`DragEvent` of type ``"current"``), or ``None``.

    Use it in ``view()`` to change what is shown while something is dragged: a trash can that
    appears, hints over the places that take the item... (the view is built again when a drag
    starts and ends if a handler changes something, such as ``on_drag_start``).
    """
    return _core._current()


def cancel() -> None:
    """Cancels the drag in progress: the preview flies back and ``on_drag_end`` reports it."""
    _core._cancel()


def reorder(items: List[Any], from_index: int, to_index: int) -> List[Any]:
    """Moves ``items[from_index]`` to ``to_index`` (in place) and returns ``items``."""
    if from_index == to_index:
        return items
    entry = items.pop(from_index)
    items.insert(max(0, min(to_index, len(items))), entry)
    return items


def move(
    lists: Union[Dict[str, List[Any]], List[Any]],
    event: DragEvent,
    *,
    make: Optional[Callable[[Any], Any]] = None,
) -> Any:
    """Applies a drop to your lists and returns the item that landed.

    ``lists`` maps the sortables' ids to their lists (or is the one list of a single sortable).
    The item leaves ``lists[event.from_list]`` (unless the source copies, ``pull="clone"``) and
    goes into ``lists[event.target]`` at ``event.index``. Items from a :func:`draggable` (no
    ``from_list``) or copies are ``make(event.data)`` when given (a new card from a palette
    template), else a deep copy of ``event.data``. Drops with ``event.combine`` are not moved:
    handle those yourself (``event.combine`` is the key of the item it was dropped onto).
    """
    if event.combine is not None:
        return None
    if isinstance(lists, list):
        lists = {str(event.target): lists}
        if event.from_list is not None:
            lists.setdefault(str(event.from_list), lists[str(event.target)])
    target = lists[str(event.target)]
    index = len(target) if event.index is None else event.index
    source = lists.get(str(event.from_list)) if event.from_list is not None else None
    if source is not None and not event.copy and event.from_index is not None:
        if source is target:
            reorder(target, event.from_index, index)
            return target[min(index, len(target) - 1)]
        entry = source.pop(event.from_index)
    else:
        template = event.data if source is None or event.from_index is None else source[event.from_index]
        entry = make(template) if make is not None else _copy.deepcopy(template)
    target.insert(max(0, min(index, len(target))), entry)
    return entry
