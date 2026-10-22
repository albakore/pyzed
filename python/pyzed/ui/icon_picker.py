"""An icon picker: a search box, categories and a grid of every bundled Lucide icon.

    ui.IconPicker(value=self.icon, on_change=lambda e: setattr(self, "icon", e.value))

Put it in a dialog with ``ui.icon_picker_dialog``, the way an "icon" property is picked::

    ui.dialog_layer(page, ui.icon_picker_dialog(self.icon, self.pick, on_close=self.close) if self.picking else None,
                    on_dismiss=self.close)
"""

from __future__ import annotations

import inspect
from typing import Any, List, Optional

from .. import _core
from .. import icons as _icons
from ..component import Component
from ..i18n import t as _t
from ..icons import icon as _icon
from ..theme import Theme
from ..theme import current as _current_theme
from .base import _theme, icon_button, label, tooltip_text
from .controls import select
from .inputs import input as _input
from .lists import virtual_list
from .overlays import modal

CELL = 34
GAP = 2


def icon_grid(
    names: List[str],
    on_pick: Any,
    *,
    selected: Optional[str] = None,
    columns: int = 8,
    cell: float = CELL,
    height: Any = 288,
    id: Optional[str] = None,  # noqa: A002
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A scrolling grid of icons that only builds the rows in view; ``on_pick(name)`` runs on a click.

    Events:
        ``on_pick(name)``: Called with the clicked name.
    """
    t = _theme(theme)
    columns = max(int(columns), 1)
    rows = [names[i:i + columns] for i in range(0, len(names), columns)]

    def cell_widget(name: str) -> Any:
        chosen = name == selected
        button = _core.button(
            _core.container(_icon(name, size=cell * 0.5), center=True),
            lambda: on_pick(name),
            padding=0,
            width=cell,
            height=cell,
            radius=t.radius_sm,
            bg=t.element_selected if chosen else "transparent",
            hover_bg=t.element_hover,
            color=t.text if chosen else t.icon,
            border_color=t.border_focused if chosen else "transparent",
            border_width=1.0,
        )
        return tooltip_text(button, name, theme=t)

    def row(names_in_row: List[str]) -> Any:
        return _core.row([cell_widget(n) for n in names_in_row], spacing=GAP)

    return virtual_list(rows, row, item_height=cell, spacing=GAP, height=height,
                        width=columns * (cell + GAP) + 10, id=id, theme=t)


class IconPicker(Component):
    """Picks a Lucide icon from a searchable grid, by name, tag or category.

    Events:
        ``on_change(event)``: Receives ``event.value``.
    """

    value: str = ""
    columns: int = 8
    height: float = 288
    clearable: bool = False
    autofocus: bool = False
    events = {"change": "An icon was picked (``event.value`` is its name, ``\"\"`` when cleared)."}
    icon = "smile-plus"
    label = "Icon picker"
    category = "Forms"
    size = (300, 340)

    def setup(self) -> None:
        self.query = ""
        self.group = ""
        self.ids = (f"icon-picker-search-{id(self)}", f"icon-picker-grid-{id(self)}")

    def on_mount(self) -> Any:
        """Scrolls the grid to the picked icon, and focuses the search box with ``autofocus``."""
        commands = [_core.Command.focus(self.ids[0])] if self.autofocus else []
        names = self.matches()
        if self.value in names:
            row = names.index(self.value) // max(int(self.columns), 1)
            commands.append(_core.Command.scroll_to(self.ids[1], y=max(row - 2, 0) * (CELL + GAP)))
        return _core.Command.batch(commands) if commands else None

    def set_query(self, text: str) -> None:
        """Filters the grid by ``text`` (names and tags)."""
        self.query = text

    def set_group(self, key: str) -> None:
        """Shows only the icons of category ``key`` (``""`` for every icon)."""
        self.group = key if key in _icons.CATEGORIES else ""

    def matches(self) -> List[str]:
        """The icons shown: those of the chosen category that match the search, best first."""
        pool = _icons.category(self.group) if self.group else None
        return _icons.search(self.query, pool)

    def pick(self, name: str) -> Any:
        """Selects ``name`` and emits ``change``."""
        self.value = name
        return self.emit("change", name)

    def render(self) -> Any:
        t = _current_theme()
        names = self.matches()
        labels = {_t("pyzed.icons.all"): ""}
        labels.update({_t(f"pyzed.icons.categories.{k}"): k for k in _icons.CATEGORIES})
        current = next(label_ for label_, key in labels.items() if key == self.group)
        search = _input(self.query, self.set_query, placeholder=_t("pyzed.icons.search"), icon="search", size="sm",
                        on_submit=(lambda: self.pick(names[0])) if names else None, id=self.ids[0], theme=t)
        header = _core.row([
            _core.container(search, width="fill"),
            select(list(labels), current, lambda chosen: self.set_group(labels[chosen]), size="sm", width=132,
                   theme=t),
        ], spacing=6, align="center")
        if names:
            body: Any = icon_grid(names, self.pick, selected=self.value or None, columns=self.columns,
                                  height=self.height, id=self.ids[1], theme=t)
        else:
            body = _core.container(label(_t("pyzed.icons.none_found", query=self.query), size="sm",
                                         color="text_muted", theme=t),
                                   width="fill", height=self.height, center=True)
        shown = self.value if self.value in _icons.CODEPOINTS else ""
        footer = _core.row([
            _icon(shown or "circle-dashed", size=16, color=None if shown else t.icon_muted),
            _core.text(shown or _t("pyzed.icons.no_icon"), size=12.5, font="mono" if shown else None,
                       color=t.text if shown else t.text_muted, wrap=False),
            _core.space(width="fill"),
            _core.text(_t("pyzed.icons.count", count=len(names)), size=12, color=t.text_muted, wrap=False),
            icon_button("x", lambda: self.pick(""), size="xs", tooltip=_t("pyzed.icons.clear"), theme=t)
            if self.clearable and shown else None,
        ], spacing=6, align="center")
        return _core.column([header, body, footer], spacing=8, width=self.columns * (CELL + GAP) + 10)


_P = inspect.Parameter
IconPicker.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
    [_P("value", _P.POSITIONAL_OR_KEYWORD, default="")]
    + [_P(n, _P.KEYWORD_ONLY, default=d) for n, d in
       [("columns", 8), ("height", 288), ("clearable", False), ("autofocus", False), ("on_change", None)]])


def icon_picker_dialog(
    value: str,
    on_pick: Any,
    *,
    on_close: Any = None,
    title: Optional[str] = None,
    columns: int = 10,
    clearable: bool = True,
    key: Any = "icon-picker",
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A dialog with an ``IconPicker``; ``on_pick(name)`` runs when an icon is clicked (``""`` when cleared).

    Use it as the dialog of ``ui.dialog_layer``. Enter in the search box picks the first match.

    Events:
        ``on_pick(name)``: Called with the clicked icon's name (``""`` when cleared).
        ``on_close()``: The close button.
    """
    t = _theme(theme)
    picker = IconPicker(value=value or "", columns=columns, clearable=clearable, autofocus=True, key=key,
                        on_change=lambda e: on_pick(e.value))
    return modal(picker, title=title or _t("pyzed.icons.title"), on_close=on_close,
                 width=columns * (CELL + GAP) + 10 + 32, theme=t)
