"""Help screens any app can show: a keyboard shortcut reference and an "About" box.

    ui.layer(body, ui.modal(ui.shortcuts(SHORTCUTS, query=q, on_query=set_q), title="Keyboard shortcuts"))
    ui.layer(body, ui.about("My App", "1.2.0", "Does useful things.", links=[("Website", open_site)]))
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Sequence, Tuple

from .. import _core
from ..icons import icon as _icon
from ..theme import Theme
from .base import _theme, button, kbd, label
from .inputs import search_input


def shortcuts(
    groups: Sequence[Tuple[str, Sequence[Tuple[str, str]]]],
    *,
    query: str = "",
    on_query: Any = None,
    height: float = 380,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A searchable list of key bindings: ``[("File", [("Save", "ctrl-s"), ...]), ...]``."""
    t = _theme(theme)
    needle = query.strip().lower()
    rows: List[Any] = []
    for title, items in groups:
        matching = [(text, keys) for text, keys in items
                    if not needle or needle in text.lower() or needle in keys.lower()]
        if not matching:
            continue
        rows.append(_core.container(label(title.upper(), size="xs", weight="semibold", color="text_muted", theme=t),
                                    padding=(10, 4, 4, 4)))
        for text, keys in matching:
            rows.append(_core.container(_core.row([label(text, size="sm", theme=t), _core.space(width="fill"),
                                                   kbd(keys, theme=t)], align="center"),
                                        padding=(3, 4), width="fill"))
    if not rows:
        rows.append(_core.container(label("No shortcut matches.", size="sm", color="text_muted", theme=t),
                                    padding=8))
    top = [search_input(query, on_query, placeholder="Search shortcuts…", theme=t)] if on_query is not None else []
    return _core.column([*top, _core.container(_core.scrollable(_core.column(rows, width="fill",
                                                                             padding=(0, 8, 0, 0))),
                                               height=height)], spacing=8, width="fill")


def about(
    name: str,
    version: str = "",
    description: str = "",
    *,
    icon: str = "app-window",
    details: Iterable[Tuple[str, str]] = (),
    links: Iterable[Tuple[str, Any]] = (),
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """An "About" box: icon, name, version, a description, a few ``(label, value)`` details and link buttons."""
    t = _theme(theme)
    detail_rows = [_core.row([label(k, size="sm", color="text_muted", theme=t), _core.space(width="fill"),
                              label(v, size="sm", mono=True, theme=t)], align="center") for k, v in details]
    link_row = [button(text, action, variant="ghost", size="sm", theme=t) for text, action in links]
    return _core.column([
        _core.container(_icon(icon, size=36, color=t.accent), width="fill", center=True, padding=(4, 0)),
        _core.container(label(name, size="xl", weight="semibold", theme=t), width="fill", center=True),
        _core.container(label(version, size="sm", color="text_muted", theme=t), width="fill", center=True)
        if version else None,
        _core.container(label(description, size="sm", align_x="center", theme=t), width="fill", center=True,
                        padding=(4, 8)) if description else None,
        _core.column(detail_rows, spacing=4, width="fill") if detail_rows else None,
        _core.container(_core.row(link_row, spacing=4), width="fill", center=True) if link_row else None,
    ], spacing=8, width="fill")
