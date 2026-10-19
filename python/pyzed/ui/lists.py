"""Lists, trees (project panel) and context menus."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, List, Optional, Sequence, Set, Union

from .. import _core
from ..icons import for_file
from ..icons import icon as _icon
from ..theme import Theme
from .base import _theme, kbd


def list_item(
    content: Any,
    on_press: Any = None,
    *,
    icon: Optional[str] = None,
    icon_color: Optional[str] = None,
    start: Any = None,
    end: Any = None,
    selected: bool = False,
    focused: bool = False,
    indent: float = 0,
    height: float = 26,
    color: Optional[str] = None,
    inset: bool = False,
    disabled: bool = False,
    on_right_press: Any = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """One row of a list (like Zed's ``ListItem``): optional icon, label and trailing slot."""
    t = _theme(theme)
    text_color = t.color(color) if color else (t.text_disabled if disabled else t.text)
    body = content if isinstance(content, _core.Widget) else _core.text(content, size=13.5, color=text_color, wrap=False)
    parts = [
        _core.space(width=indent) if indent else None,
        start,
        _icon(icon, size=14, color=t.color(icon_color) if icon_color else t.icon_muted) if icon else None,
        _core.container(body, width="fill", clip=True),
        end,
    ]
    widget = _core.button(
        _core.container(_core.row(parts, spacing=6, align="center"), height="fill", align_y="center"),
        None if disabled else on_press,
        padding=(0, 8 if inset else 6),
        width="fill",
        height=height,
        bg=t.ghost_selected if selected else "transparent",
        hover_bg=t.ghost_selected if selected else t.ghost_hover,
        pressed_bg=t.ghost_active,
        color=text_color,
        border_color=t.border_focused if focused else None,
        border_width=1.0 if focused else 0.0,
        radius=t.radius_sm if inset else 0,
    )
    if on_right_press is not None:
        widget = _core.mouse_area(widget, on_right_press=on_right_press)
    return widget


def list_header(title: str, *, end: Any = None, theme: Optional[Theme] = None) -> _core.Widget:
    """A small muted section title for a list, with an optional ``end`` widget on the right."""
    t = _theme(theme)
    return _core.container(
        _core.row([_core.text(title, size=12, weight="medium", color=t.text_muted, wrap=False), _core.space(width="fill"), end],
                  align="center"),
        padding=(6, 8, 2, 8),
        width="fill",
    )


# ---------------------------------------------------------------------------
# Tree (project panel)
# ---------------------------------------------------------------------------


@dataclass
class TreeNode:
    """A file or folder. Folders have a ``children`` list (possibly empty)."""

    name: str
    children: Optional[List["TreeNode"]] = None
    id: Optional[str] = None
    status: Optional[str] = None  # "modified" | "created" | "deleted" | "conflict" | "ignored"
    icon: Optional[str] = None
    icon_color: Optional[str] = None

    @property
    def is_folder(self) -> bool:
        """Whether the node is a folder (it has a ``children`` list, even if empty)."""
        return self.children is not None

    @classmethod
    def from_paths(cls, paths: Iterable[str], status: Optional[dict] = None) -> List["TreeNode"]:
        """Builds a tree from ``"src/main.rs"``-style paths. Folders sort first."""
        status = status or {}
        root = cls("", children=[], id="")
        for path in paths:
            node = root
            parts = [p for p in path.split("/") if p]
            for i, part in enumerate(parts):
                is_last = i == len(parts) - 1
                node_id = "/".join(parts[: i + 1])
                existing = next((c for c in node.children if c.name == part), None)
                if existing is None:
                    existing = cls(part, children=None if is_last and not path.endswith("/") else [], id=node_id,
                                   status=status.get(node_id))
                    node.children.append(existing)
                node = existing
        root.sort()
        # Propagate status to folders like Zed does (a folder with changes is tinted).
        def bubble(n: "TreeNode") -> Optional[str]:
            if not n.is_folder:
                return n.status
            found = [bubble(c) for c in n.children]
            if n.status is None:
                for s in ("conflict", "deleted", "modified", "created"):
                    if s in found:
                        n.status = "modified" if s != "created" else "created"
                        break
            return n.status
        for c in root.children:
            bubble(c)
        return root.children

    def sort(self) -> None:
        """Sorts the children recursively: folders first, then by name ignoring case."""
        if self.children:
            self.children.sort(key=lambda c: (not c.is_folder, c.name.lower()))
            for c in self.children:
                c.sort()


def tree(
    nodes: Sequence[TreeNode],
    *,
    expanded: Set[str],
    selected: Optional[str] = None,
    on_toggle: Optional[Callable[[str], Any]] = None,
    on_select: Optional[Callable[[str], Any]] = None,
    indent: float = 14,
    item_height: float = 24,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A collapsible file tree (Zed's project panel).

    ``on_toggle(id)`` is called for folders and ``on_select(id)`` for files; both may return a message.
    """
    t = _theme(theme)
    rows: List[Any] = []

    def status_color(status: Optional[str]) -> Optional[str]:
        return {
            "modified": t.modified,
            "created": t.created,
            "deleted": t.deleted,
            "conflict": t.conflict,
            "ignored": t.ignored,
        }.get(status or "")

    def walk(items: Sequence[TreeNode], depth: int) -> None:
        for node in items:
            node_id = node.id if node.id is not None else node.name
            is_open = node_id in expanded
            color = status_color(node.status)
            if node.is_folder:
                chevron = _icon("chevron-down" if is_open else "chevron-right", size=12, color=t.icon_muted)
                icon_name, icon_color = (node.icon or ("folder-open" if is_open else "folder")), node.icon_color or t.icon_muted
                handler = (lambda i=node_id: on_toggle(i)) if on_toggle else None
            else:
                chevron = _core.space(width=12)
                default_icon, default_color = for_file(node.name)
                icon_name = node.icon or default_icon
                icon_color = node.icon_color or default_color or t.icon_muted
                handler = (lambda i=node_id: on_select(i)) if on_select else None
            rows.append(
                list_item(
                    _core.text(node.name, size=13.5, color=color or t.text, wrap=False),
                    handler,
                    start=chevron,
                    icon=icon_name,
                    icon_color=icon_color,
                    indent=depth * indent,
                    height=item_height,
                    selected=node_id == selected,
                    theme=t,
                )
            )
            if node.is_folder and is_open:
                walk(node.children or [], depth + 1)

    walk(nodes, 0)
    return _core.column(rows, width="fill")


# ---------------------------------------------------------------------------
# Context menu
# ---------------------------------------------------------------------------


@dataclass
class MenuItem:
    label: str
    on_press: Any = None
    icon: Optional[str] = None
    keys: Optional[str] = None
    disabled: bool = False
    danger: bool = False
    checked: Optional[bool] = None


SEPARATOR = "separator"


def menu(
    items: Sequence[Union[MenuItem, str]],
    *,
    width: float = 240,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A floating context menu. Use ``ui.SEPARATOR`` between groups; a plain string is a header."""
    t = _theme(theme)
    rows: List[Any] = []
    for item in items:
        if item == SEPARATOR:
            rows.append(_core.container(_core.rule(thickness=1, color=t.border_variant), padding=(4, 0)))
        elif isinstance(item, str):
            rows.append(list_header(item, theme=t))
        else:
            start = None
            if item.checked is not None:
                start = _icon("check", size=14, color=t.text if item.checked else "transparent")
            rows.append(
                list_item(
                    item.label,
                    item.on_press,
                    icon=item.icon,
                    start=start,
                    end=kbd(item.keys, theme=t, size="xs") if item.keys else None,
                    color="error" if item.danger else None,
                    disabled=item.disabled,
                    inset=True,
                    height=26,
                    theme=t,
                )
            )
    return _core.container(
        _core.column(rows, width="fill"),
        width=width,
        padding=4,
        bg=t.elevated,
        border_color=t.border,
        border_width=1.0,
        radius=t.radius,
        shadow=(t.shadow, (0, 4), 16),
    )
