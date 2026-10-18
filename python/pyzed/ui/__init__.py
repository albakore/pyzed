"""Ready-made, themeable components inspired by the Zed editor.

All of them are plain functions returning widgets, so they compose freely and
every color comes from the current ``Theme`` (override any of them via kwargs
or pass ``theme=``).
"""

from .base import (
    avatar,
    badge,
    button,
    card,
    divider,
    format_keys,
    heading,
    icon_button,
    indicator,
    kbd,
    label,
    muted,
    tooltip_text as tooltip,
)
from .editor import ansi, editor, language_token, terminal
from .inputs import checkbox, field, input, progress, search_input, segmented, slider, switch
from .lists import SEPARATOR, MenuItem, TreeNode, list_header, list_item, menu, tree
from .navigation import Tab, breadcrumbs, tab, tab_bar, toolbar
from .overlays import (
    PaletteItem,
    command_palette,
    fuzzy_filter,
    fuzzy_match,
    highlighted,
    layer,
    modal,
    picker,
    toast,
    toasts,
)
from .workspace import panel, panel_header, status_bar, status_item, title_bar, title_button, workspace

__all__ = [
    "SEPARATOR", "MenuItem", "PaletteItem", "Tab", "TreeNode", "ansi", "avatar", "badge", "breadcrumbs",
    "button", "card", "checkbox", "command_palette", "divider", "editor", "field", "format_keys",
    "fuzzy_filter", "fuzzy_match", "heading", "highlighted", "icon_button", "indicator", "input", "kbd",
    "label", "language_token", "layer", "list_header", "list_item", "menu", "modal", "muted", "panel",
    "panel_header", "picker", "progress", "search_input", "segmented", "slider", "status_bar",
    "status_item", "switch", "tab", "tab_bar", "terminal", "title_bar", "title_button", "toast", "toasts",
    "toolbar", "tooltip", "tree", "workspace",
]
