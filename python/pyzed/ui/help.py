"""Help screens any app can show: a keyboard shortcut reference, an "About" box and the Pyzed reference.

    ui.layer(body, ui.modal(ui.shortcuts(SHORTCUTS, query=q, on_query=set_q), title="Keyboard shortcuts"))
    ui.layer(body, ui.about("My App", "1.2.0", "Does useful things.", links=[("Website", open_site)]))
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Sequence, Tuple

from .. import _core
from ..icons import icon as _icon
from ..theme import Theme
from .base import _theme, badge, button, icon_button, kbd, label
from .display import markdown as _md
from .inputs import search_input
from .lists import list_item


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


def reference_browser(
    browser: Any,
    *,
    on_open_url: Any = None,
    sidebar_width: float = 270,
    width: Any = "fill",
    height: Any = "fill",
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """The built-in reference, like Godot's: a searchable class list next to the page that is open.

    ``browser`` is a ``pyzed.reference.Browser`` (keep it in your app's state); clicking entries,
    links and the back/forward buttons changes it. ``on_open_url(url)`` gets the links that leave
    the reference (the website, GitHub...)::

        self.help = reference.Browser("pyzed.ui.button")
        ...
        ui.reference_browser(self.help, on_open_url=open_in_browser)
    """
    from .. import i18n
    from .. import reference as _reference

    t = _theme(theme)

    def text(key: str, **values: Any) -> str:
        return i18n.t(f"pyzed.reference.{key}", **values)

    def follow(url: str) -> None:
        target = browser.follow(url)
        if target and on_open_url is not None:
            on_open_url(target)

    current = browser.page()
    rows: List[Any] = []

    def entry_row(entry: Any, indent: float = 0) -> Any:
        return list_item(_core.row([
            label(entry.title, size="sm", mono=entry.kind not in ("control", "page"), wrap=False, theme=t),
        ]), lambda i=entry.id: browser.open(i), icon=entry.icon, icon_color="accent" if entry.kind == "control" else None,
            selected=current is not None and current.id == entry.id, indent=indent, height=24, theme=t)

    if browser.query.strip():
        results = browser.results()
        rows.append(_core.container(label(text("results", count=len(results)), size="xs", color="text_muted",
                                          theme=t), padding=(4, 8)))
        if not results:
            rows.append(_core.container(label(text("no_results", query=browser.query.strip()), size="sm",
                                              color="text_muted", theme=t), padding=(8, 8)))
        for entry in results:
            rows.append(_core.column([entry_row(entry),
                                      _core.container(label(entry.summary, size="xs", color="text_muted", wrap=False,
                                                            theme=t), padding=(0, 8, 4, 30), clip=True)
                                      if entry.summary else None], spacing=0))
    else:
        for section, groups in _reference.sections(browser.lang):
            open_ = section in browser.expanded
            rows.append(_core.button(_core.row([
                _icon("chevron-down" if open_ else "chevron-right", size=12, color=t.icon_muted),
                label(section, size="sm", weight="semibold", wrap=False, theme=t),
                _core.space(width="fill"),
                label(str(sum(len(items) for _, items in groups)), size="xs", color="text_muted", theme=t),
            ], spacing=6, align="center"), lambda s=section: browser.toggle(s), padding=(0, 8), height=26,
                width="fill", bg="transparent", hover_bg=t.element_hover, radius=4))
            if not open_:
                continue
            for group, items in groups:
                if group:
                    rows.append(_core.container(label(group.upper(), size="xs", weight="semibold", color="text_muted",
                                                      wrap=False, theme=t), padding=(6, 8, 2, 26)))
                rows += [entry_row(entry, indent=12) for entry in items]
    sidebar = _core.container(_core.column([
        _core.container(search_input(browser.query, browser.set_query, placeholder=text("search")), padding=8,
                        width="fill"),
        _core.scrollable(_core.column(rows, spacing=1, padding=(0, 6, 8, 6), width="fill"), height="fill",
                         scrollbar_width=4),
    ], width="fill", height="fill"), width=sidebar_width, height="fill", bg=t.panel)

    bar = _core.container(_core.row([
        icon_button("arrow-left", browser.back if browser.past else None, size="sm", tooltip=text("back"),
                    disabled=not browser.past, theme=t),
        icon_button("arrow-right", browser.forward if browser.future else None, size="sm", tooltip=text("forward"),
                    disabled=not browser.future, theme=t),
        _core.space(width="fill"),
        button(text("online"), (lambda u=current.url: on_open_url(u)) if on_open_url is not None else None,
               icon="external-link", variant="ghost", size="sm", theme=t)
        if current is not None and current.url and on_open_url is not None else None,
    ], spacing=2, align="center"), padding=(4, 8), width="fill")
    if current is None:
        body: Any = _core.container(_core.column([
            _icon("book-open", size=32, color=t.icon_muted),
            label(text("title"), size="lg", weight="semibold", theme=t),
            label(text("empty"), size="sm", color="text_muted", theme=t),
        ], spacing=8, align="center"), width="fill", height="fill", center=True)
    else:
        entry = current.entry
        header = _core.column([
            _core.row([
                _icon(entry.icon, size=22, color=t.accent),
                label(entry.title, size="xl", weight="semibold", mono=entry.kind not in ("control", "page"),
                      theme=t),
                badge(text(f"kinds.{entry.kind}"), tint="info" if entry.kind == "control" else "accent", theme=t),
            ], spacing=10, align="center"),
            label(" › ".join(x for x in (entry.section, entry.group) if x), size="sm", color="text_muted", theme=t),
        ], spacing=6)
        page = _core.column([
            header,
            _core.container(None, height=1, width="fill", bg=t.border_variant),
            _md(_reference.tables_as_lists(current.body), on_link=follow, width="fill", theme=t),
        ], spacing=14, width="fill", padding=(20, 28, 32, 28))
        body = _core.scrollable(_core.container(page, width="fill", max_width=900), height="fill",
                                id=f"pyzed-reference-{browser.revision}", scrollbar_width=6)
    main = _core.column([bar, _core.container(None, height=1, width="fill", bg=t.border_variant), body],
                        width="fill", height="fill")
    return _core.row([sidebar, _core.container(None, width=1, height="fill", bg=t.border_variant), main],
                     width=width, height=height)
