"""Modals, the command palette, pickers and toasts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Optional, Sequence, Tuple

from .. import _core
from ..icons import icon as _icon
from ..theme import Theme, alpha
from .base import _theme, icon_button, kbd
from .inputs import input as _input


def layer(base: Any, overlay: Any = None, *, on_dismiss: Any = None, backdrop: Optional[str] = None,
          align_x: str = "center", align_y: str = "start", offset: float = 72) -> _core.Widget:
    """Stacks ``overlay`` on top of ``base``. Clicking outside the overlay sends ``on_dismiss``.

    Events:
        ``on_dismiss()``: Message or callable sent on close.
    """
    if overlay is None:
        return base
    shade = _core.container(None, width="fill", height="fill", bg=backdrop or "transparent")
    if on_dismiss is not None:
        shade = _core.mouse_area(shade, on_press=on_dismiss)
    top = _core.container(
        _core.opaque(overlay),
        width="fill",
        height="fill",
        align_x=align_x,
        align_y=align_y,
        padding=(offset, 16, 16, 16) if align_y == "start" else 16,
    )
    return _core.stack([base, shade, top], width="fill", height="fill")


def modal(
    content: Any,
    *,
    title: Optional[str] = None,
    on_close: Any = None,
    width: Any = 480,
    footer: Iterable[Any] = (),
    description: Optional[str] = None,
    icon: Optional[str] = None,
    max_height: Optional[float] = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A dialog surface (use it as the ``overlay`` of ``ui.layer``).

    ``width`` is pixels or ``"sm"`` (360), ``"md"`` (480), ``"lg"`` (640) or ``"xl"`` (820).
    ``description`` is a muted line under the title and ``icon`` goes before it;
    ``max_height`` scrolls content taller than that, keeping the header and footer in view.
    The Escape key closes it while it has focus (it is sent ``on_close``).

    Events:
        ``on_close()``: The close button; also sent by Escape while the dialog has focus.
    """
    t = _theme(theme)
    width = {"sm": 360, "md": 480, "lg": 640, "xl": 820}.get(width, width)
    header = None
    if title or on_close is not None:
        heading = _core.text(title or "", size=15, weight="semibold", color=t.text, wrap=False)
        if description:
            heading = _core.column([heading, _core.text(description, size=12.5, color=t.text_muted)], spacing=2)
        header = _core.row(
            [
                _icon(icon, size=16, color=t.icon) if icon else None,
                heading,
                _core.space(width="fill"),
                icon_button("x", on_close, size="sm", theme=t) if on_close is not None else None,
            ],
            align="center",
            spacing=8,
        )
    footer = list(footer)
    if max_height is not None:
        content = _core.container(_core.scrollable(_core.container(content, padding=(0, 12, 0, 0)), height="shrink", scroller=t.scrollbar,
                                                   scroller_hover=t.scrollbar_hover, scrollbar_width=6),
                                  max_height=max_height)
    surface = _core.container(
        _core.column(
            [header, content, _core.row([_core.space(width="fill"), *footer], spacing=8) if footer else None],
            spacing=14,
        ),
        width=width,
        padding=16,
        bg=t.elevated,
        border_color=t.border,
        border_width=1.0,
        radius=t.radius + 4,
        shadow=(t.shadow, (0, 8), 28),
    )
    if on_close is None:
        return surface
    def escape(event: Any) -> Any:
        if event.key != "escape":
            return None
        return on_close() if callable(on_close) else on_close

    return surface.on(key_down=escape)


# ---------------------------------------------------------------------------
# Fuzzy matching (used by the command palette and file finder)
# ---------------------------------------------------------------------------


def fuzzy_match(query: str, candidate: str) -> Optional[Tuple[float, List[int]]]:
    """Returns ``(score, matched_positions)`` if every query char appears in order, else ``None``."""
    if not query:
        return (0.0, [])
    q = query.lower().replace(" ", "")
    c = candidate.lower()
    positions: List[int] = []
    start = 0
    for ch in q:
        idx = c.find(ch, start)
        if idx < 0:
            return None
        positions.append(idx)
        start = idx + 1
    score = 0.0
    for i, pos in enumerate(positions):
        if pos == 0 or not candidate[pos - 1].isalnum():
            score += 3  # word start
        if i and positions[i - 1] == pos - 1:
            score += 2  # consecutive
    score -= positions[-1] * 0.05 + len(candidate) * 0.01
    return (score, positions)


def fuzzy_filter(query: str, items: Sequence[Any], key: Callable[[Any], str] = str):
    """Filters and sorts ``items`` by fuzzy score. Returns ``[(item, positions), ...]``."""
    scored = []
    for order, item in enumerate(items):
        result = fuzzy_match(query, key(item))
        if result is not None:
            scored.append((-result[0], order, item, result[1]))
    if query:
        scored.sort(key=lambda s: (s[0], s[1]))
    return [(item, positions) for _, _, item, positions in scored]


def highlighted(text: str, positions: Sequence[int], *, color: str, match_color: str, size: float = 13.5,
                weight: Optional[str] = None) -> _core.Widget:
    """Text with the characters at ``positions`` emphasized (fuzzy match highlights)."""
    if not positions:
        return _core.text(text, size=size, color=color, weight=weight, wrap=False)
    marks = set(positions)
    runs: List[Tuple[str, bool]] = []
    for i, ch in enumerate(text):
        hit = i in marks
        if runs and runs[-1][1] == hit:
            runs[-1] = (runs[-1][0] + ch, hit)
        else:
            runs.append((ch, hit))
    return _core.row(
        [
            _core.text(run, size=size, color=match_color if hit else color, weight="semibold" if hit else weight, wrap=False)
            for run, hit in runs
        ]
    )


@dataclass
class PaletteItem:
    """One result of a ``ui.command_palette`` or ``ui.picker``: a label with optional shortcut, icon and detail.

    Events:
        ``on_press()``: Message or callable sent when the item is chosen.
    """

    label: str
    on_press: Any = None
    keys: Optional[str] = None
    icon: Optional[str] = None
    detail: Optional[str] = None


def picker(
    query: str,
    on_query: Any,
    items: Sequence[Tuple[PaletteItem, Sequence[int]]],
    *,
    selected: int = 0,
    placeholder: str = "Search…",
    input_id: str = "picker",
    on_submit: Any = None,
    width: float = 560,
    max_height: float = 340,
    empty_text: str = "No matches",
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A searchable list in a floating surface (base of the command palette and file finder).

    ``items`` are ``(PaletteItem, matched_positions)`` pairs, e.g. from ``fuzzy_filter``.

    Events:
        ``on_query(text)``: Callable that receives the new text.
        ``on_submit()``: Message or callable sent when Enter is pressed.
    """
    t = _theme(theme)
    rows: List[Any] = []
    for index, (item, positions) in enumerate(items):
        is_selected = index == selected
        left = _core.row(
            [
                _icon(item.icon, size=14, color=t.icon_muted) if item.icon else None,
                highlighted(item.label, positions, color=t.text, match_color=t.text_accent),
                _core.text(item.detail, size=12.5, color=t.text_placeholder, wrap=False) if item.detail else None,
            ],
            spacing=8,
            align="center",
        )
        rows.append(
            _core.button(
                _core.container(
                    _core.row([left, _core.space(width="fill"), kbd(item.keys, theme=t, size="xs") if item.keys else None],
                              align="center"),
                    height="fill",
                    align_y="center",
                ),
                item.on_press,
                padding=(0, 10),
                width="fill",
                height=30,
                bg=t.ghost_selected if is_selected else "transparent",
                hover_bg=t.ghost_selected if is_selected else t.ghost_hover,
                radius=t.radius_sm,
            )
        )
    if not rows:
        rows.append(_core.container(_core.text(empty_text, size=13.5, color=t.text_muted), padding=(8, 10)))

    search = _core.container(
        _input(query, on_query, placeholder=placeholder, id=input_id, on_submit=on_submit, borderless=True,
               size="lg", theme=t),
        padding=(4, 6),
        width="fill",
    )
    return _core.container(
        _core.column(
            [
                search,
                _core.rule(thickness=1, color=t.border_variant),
                _core.container(
                    _core.scrollable(_core.column(rows, width="fill", spacing=1), height="shrink", scrollbar_width=6,
                                     scroller=t.scrollbar, scroller_hover=t.scrollbar_hover),
                    max_height=max_height,
                    padding=6,
                    width="fill",
                ),
            ]
        ),
        width=width,
        bg=t.elevated,
        border_color=t.border,
        border_width=1.0,
        radius=t.radius + 2,
        shadow=(alpha("#000000", 0.35 if t.is_dark else 0.15), (0, 8), 32),
        clip=True,
    )


def command_palette(
    query: str,
    on_query: Any,
    commands: Sequence[PaletteItem],
    *,
    selected: int = 0,
    on_submit: Any = None,
    placeholder: str = "Execute a command…",
    input_id: str = "command-palette",
    theme: Optional[Theme] = None,
    **kwargs,
) -> _core.Widget:
    """Zed's command palette: fuzzy-filters ``commands`` by ``query`` and shows their key bindings.

    Events:
        ``on_query(text)``: Callable that receives the new text.
        ``on_submit()``: Message or callable sent when Enter is pressed.
    """
    matches = fuzzy_filter(query, commands, key=lambda c: c.label)
    return picker(query, on_query, matches, selected=selected, placeholder=placeholder, input_id=input_id,
                  on_submit=on_submit, theme=theme, **kwargs)


# ---------------------------------------------------------------------------
# Toasts
# ---------------------------------------------------------------------------

_KIND_ICONS = {"info": "info", "success": "circle-check", "warning": "triangle-alert", "error": "circle-x"}


def toast(
    title: str,
    message: Optional[str] = None,
    *,
    kind: str = "info",
    icon: Optional[str] = None,
    on_dismiss: Any = None,
    actions: Iterable[Any] = (),
    width: float = 340,
    progress: Optional[float] = None,
    on_press: Any = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A notification card. kind: "info" | "success" | "warning" | "error".

    ``progress`` (0 to 1) draws a thin bar at the bottom: the time left before it closes,
    or a download. ``on_press`` makes the card clickable (open what it is about).

    Events:
        ``on_dismiss()``: Message or callable sent on close.
        ``on_press()``: Makes the card clickable.
    """
    t = _theme(theme)
    color = t.color(kind)
    actions = list(actions)
    bar = None
    if progress is not None:
        bar = _core.progress_bar(max(0.0, min(progress, 1.0)), min=0.0, max=1.0, width="fill", height=2,
                                 accent=color, bg=alpha(t.text, 0.08), radius=1)
    card = _core.container(
        _core.row(
            [
                _core.container(_icon(icon or _KIND_ICONS.get(kind, "bell"), size=16, color=color), padding=(1, 0, 0, 0)),
                _core.column(
                    [
                        _core.text(title, size=13.5, weight="medium", color=t.text),
                        _core.text(message, size=12.5, color=t.text_muted) if message else None,
                        _core.row(actions, spacing=6) if actions else None,
                        bar,
                    ],
                    spacing=6,
                    width="fill",
                ),
                icon_button("x", on_dismiss, size="xs", theme=t) if on_dismiss is not None else None,
            ],
            spacing=10,
        ),
        width=width,
        padding=12,
        bg=t.elevated,
        border_color=t.border,
        border_width=1.0,
        radius=t.radius + 2,
        shadow=(t.shadow, (0, 4), 18),
    )
    return card if on_press is None else card.on(click=on_press, cursor="pointer")


def toasts(base: Any, items: Sequence[Any], *, spacing: float = 8) -> _core.Widget:
    """Shows ``items`` (usually ``toast(...)``) stacked in the bottom-right corner over ``base``."""
    if not items:
        return base
    column = _core.column([_core.opaque(item) for item in items], spacing=spacing, align="end")
    return _core.stack(
        [base, _core.container(column, width="fill", height="fill", align_x="end", align_y="end", padding=(16, 16, 40, 16))],
        width="fill",
        height="fill",
    )
