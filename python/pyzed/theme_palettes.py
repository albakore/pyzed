"""Pyzed's own themes, each made from a small palette the way Zed's theme families are.

A palette names a handful of colors: the editor background, the chrome around it, text, an accent
and six hues for status and syntax. ``from_palette`` turns it into a complete ``Theme``: surfaces
step a little away from the editor (lighter on dark themes, darker on light ones), borders and
hover states are mixed from those, and syntax takes the hues the way One Dark does.

    from pyzed import theme_palettes
    theme = theme_palettes.from_palette("Mine", "dark", editor="#1b1d24", chrome="#23262f", text="#d8dbe2",
                                        accent="#7aa2f7", red="#f7768e", orange="#ff9e64", yellow="#e0af68",
                                        green="#9ece6a", cyan="#7dcfff", purple="#bb9af7")
"""

from __future__ import annotations

from typing import List

from .theme import ONE_DARK, ONE_LIGHT, Theme, alpha, mix


def from_palette(name: str, appearance: str, *, editor: str, chrome: str, text: str, accent: str, red: str,
                 orange: str, yellow: str, green: str, cyan: str, purple: str) -> Theme:
    """A complete theme from a palette: ``editor`` is where code and forms sit, ``chrome`` the title bar,
    panels and tab bar around it, ``text`` the main text color and the rest the accent and hues."""
    dark = appearance == "dark"
    base = ONE_DARK if dark else ONE_LIGHT
    # light themes need text closer to full strength to stay readable on their pale chrome
    muted = mix(text, chrome, 0.35 if dark else 0.25)
    faint = mix(text, chrome, 0.55 if dark else 0.42)
    border = mix(chrome, text, 0.14)
    border_variant = mix(chrome, text, 0.07)
    hover = mix(chrome, text, 0.07)
    active = mix(chrome, text, 0.13)
    comment = mix(text, editor, 0.5)
    on_accent = editor if dark else "#ffffff"
    return base.derive(
        name=name,
        background=chrome,
        surface=chrome,
        elevated=mix(chrome, text, 0.03),
        editor=editor,
        title_bar=chrome,
        status_bar=chrome,
        tab_bar=chrome,
        tab_active=editor,
        tab_inactive=chrome,
        panel=chrome,
        terminal=editor,
        border=border,
        border_variant=border_variant,
        border_focused=mix(accent, chrome, 0.35),
        border_selected=mix(accent, chrome, 0.65),
        element=mix(chrome, editor, 0.5),
        element_hover=hover,
        element_active=active,
        element_selected=active,
        ghost_hover=hover,
        ghost_active=active,
        ghost_selected=active,
        text=text,
        text_muted=muted,
        text_placeholder=faint,
        text_disabled=faint,
        text_accent=accent,
        icon=text,
        icon_muted=muted,
        accent=accent,
        on_accent=on_accent,
        error=red,
        warning=yellow,
        success=green,
        info=accent,
        hint=mix(accent, muted, 0.5),
        created=green,
        modified=yellow,
        deleted=red,
        conflict=orange,
        ignored=faint,
        editor_text=mix(text, editor, 0.12),
        line_number=mix(text, editor, 0.7),
        line_number_active=text,
        active_line=alpha(chrome, 0.75),
        selection=alpha(accent, 0.24),
        scrollbar=alpha(text, 0.3),
        scrollbar_hover=alpha(text, 0.5),
        search_match=alpha(accent, 0.4),
        syntax={
            "primary": mix(text, editor, 0.12),
            "attribute": accent,
            "boolean": orange,
            "comment": comment,
            "comment.doc": mix(text, editor, 0.4),
            "constant": yellow,
            "constructor": accent,
            "emphasis": (accent, "italic"),
            "emphasis.strong": (orange, "bold"),
            "enum": red,
            "function": accent,
            "keyword": purple,
            "label": accent,
            "link_uri": cyan,
            "number": orange,
            "operator": cyan,
            "property": red,
            "punctuation": mix(text, editor, 0.2),
            "punctuation.bracket": mix(text, editor, 0.15),
            "punctuation.list_marker": red,
            "string": green,
            "string.escape": comment,
            "string.regex": orange,
            "string.special": orange,
            "tag": accent,
            "text.literal": green,
            "title": red,
            "type": cyan,
            "variable": mix(text, editor, 0.12),
            "variable.special": orange,
            "created": green,
            "deleted": red,
            "modified": yellow,
        },
        players=(accent, red, orange, purple, cyan, green, yellow, mix(red, purple)),
        ansi={"black": editor, "red": red, "green": green, "yellow": yellow, "blue": accent, "magenta": purple,
              "cyan": cyan, "white": text, "bright_black": comment, "dim": faint},
    )


#: Pyzed's own themes: four dark and two light.
PYZED_THEMES: List[Theme] = [
    from_palette("Pyzed Midnight", "dark", editor="#191c26", chrome="#21252f", text="#d6dae4", accent="#7aa2f7",
                 red="#f07a8c", orange="#f29e6a", yellow="#e5c07b", green="#9fce7a", cyan="#73cbe0",
                 purple="#b99af5"),
    from_palette("Pyzed Graphite", "dark", editor="#1e1e1e", chrome="#262626", text="#dcdcdc", accent="#5fa8f5",
                 red="#e5737a", orange="#e09b5d", yellow="#dcc27c", green="#94c47d", cyan="#6cc1c8",
                 purple="#c48ee0"),
    from_palette("Pyzed Forest", "dark", editor="#1b211e", chrome="#222a26", text="#d5ddd7", accent="#7fc8a0",
                 red="#e3796f", orange="#e0a060", yellow="#d9c37a", green="#a6cf7f", cyan="#78c4c0",
                 purple="#bd9ad8"),
    from_palette("Pyzed Rosé", "dark", editor="#211b24", chrome="#2a222d", text="#e3d8e3", accent="#e58fb6",
                 red="#ef7f8b", orange="#efa77a", yellow="#e7c886", green="#a8cf92", cyan="#86c7d3",
                 purple="#b9a0f0"),
    from_palette("Pyzed Dawn", "light", editor="#fbf8f3", chrome="#efeae1", text="#3b3732", accent="#a85a1f",
                 red="#c8414f", orange="#c26b2c", yellow="#9d7a12", green="#4f8a3a", cyan="#2a8590",
                 purple="#8a4fb8"),
    from_palette("Pyzed Glacier", "light", editor="#f8fafc", chrome="#e8edf3", text="#2d3640", accent="#2f74d0",
                 red="#c9404e", orange="#b8652a", yellow="#8f7414", green="#3d8a4e", cyan="#1f8597",
                 purple="#7c4fc4"),
]


def _brand(name: str, appearance: str, *, background: str, surface: str, panel: str, raised: str, border: str,
           text: str, muted: str, faint: str, accent: str, accent_text: str, tint: str, error: str, warning: str,
           success: str, info: str, syntax: dict, ansi: dict, instruments: dict) -> Theme:
    dark = appearance == "dark"
    base = ONE_DARK if dark else ONE_LIGHT
    return base.derive(
        name=name, appearance=appearance,
        background=background, surface=panel, elevated=raised if dark else surface, editor=surface,
        title_bar=panel, status_bar=panel, tab_bar=panel, tab_active=surface, tab_inactive=panel, panel=panel,
        terminal=surface,
        border=border, border_variant=mix(panel, border, 0.5), border_focused=accent_text,
        border_selected=alpha(accent_text, 0.32),
        element=surface, element_hover=raised, element_active=border, element_selected=border,
        ghost_hover=raised, ghost_active=border, ghost_selected=tint,
        text=text, text_muted=muted, text_placeholder=faint, text_disabled=faint, text_accent=accent_text,
        icon=text, icon_muted=muted, accent=accent, on_accent="#ffffff",
        error=error, warning=warning, success=success, info=info, hint=syntax["comment"],
        created=success, modified=warning, deleted=error, conflict=warning, ignored=faint,
        editor_text=syntax["primary"], line_number=faint, line_number_active=text, active_line=alpha(panel, 0.75),
        selection=alpha(accent_text, 0.24), scrollbar=alpha(text, 0.2), scrollbar_hover=alpha(text, 0.4),
        search_match=alpha(accent_text, 0.32), shadow="#00000080" if dark else "#0f172a24",
        syntax=syntax,
        players=(accent_text, info, success, warning, instruments["guide"], syntax["type"], syntax["keyword"], error),
        ansi=ansi, radius=8.0, radius_sm=5.0, **instruments,
    )


#: The brand's themes (assets/brand/tokens.json): graphite surfaces in layers like a code editor, indigo for the
#: brand and amber kept for LEDs and displays. ``Pyzed Dark`` is the default theme.
PYZED_DARK = _brand(
    "Pyzed Dark", "dark", background="#0d0e11", surface="#14161b", panel="#191c22", raised="#222630",
    border="#2a2f39", text="#e7e9ee", muted="#9aa1ae", faint="#5c6370", accent="#5b50f0", accent_text="#8b83ff",
    tint="#8b83ff1f", error="#f26d85", warning="#f5a524", success="#3fcf8e", info="#6fc3ff",
    syntax={
        "primary": "#dcdfe5", "attribute": "#8b83ff", "boolean": "#f5b547", "comment": "#7c8491",
        "comment.doc": "#8e96a3", "constant": "#f5b547", "constructor": "#6fc3ff", "emphasis": ("#8b83ff", "italic"),
        "emphasis.strong": ("#f5b547", "bold"), "enum": "#62d2c4", "function": "#6fc3ff", "keyword": "#b4a9ff",
        "label": "#8b83ff", "link_uri": "#6fc3ff", "number": "#f5b547", "operator": "#9aa1ae", "property": "#f28fad",
        "punctuation": "#9aa1ae", "punctuation.bracket": "#b3b9c4", "punctuation.list_marker": "#8b83ff",
        "string": "#9fd88b", "string.escape": "#f5b547", "string.regex": "#f5b547", "string.special": "#f5b547",
        "tag": "#8b83ff", "text.literal": "#9fd88b", "title": ("#8b83ff", "bold"), "type": "#62d2c4",
        "variable": "#dcdfe5", "variable.special": "#f28fad", "created": "#3fcf8e", "deleted": "#f26d85",
        "modified": "#f5a524",
    },
    ansi={"black": "#14161b", "red": "#f26d85", "green": "#3fcf8e", "yellow": "#f5a524", "blue": "#6fc3ff",
          "magenta": "#b4a9ff", "cyan": "#62d2c4", "white": "#e7e9ee", "bright_black": "#5c6370", "dim": "#9aa1ae"},
    instruments={"led": "#f5a524", "led_off": "#3a3f4a", "display": "#07080a", "display_text": "#f5b547",
                 "canvas": "#101216", "canvas_grid": "#262a33", "guide": "#ff6b9a"},
)

PYZED_LIGHT = _brand(
    "Pyzed Light", "light", background="#f6f7f9", surface="#ffffff", panel="#f1f3f6", raised="#e7eaf0",
    border="#dce0e7", text="#14161b", muted="#576070", faint="#9aa1ae", accent="#4f46e5", accent_text="#4f46e5",
    tint="#eef0ff", error="#d0344f", warning="#b45f00", success="#12805c", info="#0b6bcb",
    syntax={
        "primary": "#24272e", "attribute": "#4f46e5", "boolean": "#9a5b00", "comment": "#6b7280",
        "comment.doc": "#576070", "constant": "#9a5b00", "constructor": "#0b6bcb", "emphasis": ("#4f46e5", "italic"),
        "emphasis.strong": ("#9a5b00", "bold"), "enum": "#0f766e", "function": "#0b6bcb", "keyword": "#6d28d9",
        "label": "#4f46e5", "link_uri": "#0b6bcb", "number": "#9a5b00", "operator": "#576070", "property": "#b42359",
        "punctuation": "#576070", "punctuation.bracket": "#424954", "punctuation.list_marker": "#4f46e5",
        "string": "#2f7d32", "string.escape": "#9a5b00", "string.regex": "#9a5b00", "string.special": "#9a5b00",
        "tag": "#4f46e5", "text.literal": "#2f7d32", "title": ("#4f46e5", "bold"), "type": "#0f766e",
        "variable": "#24272e", "variable.special": "#b42359", "created": "#12805c", "deleted": "#d0344f",
        "modified": "#b45f00",
    },
    ansi={"black": "#14161b", "red": "#d0344f", "green": "#12805c", "yellow": "#9a5b00", "blue": "#0b6bcb",
          "magenta": "#6d28d9", "cyan": "#0f766e", "white": "#f6f7f9", "bright_black": "#9aa1ae", "dim": "#576070"},
    instruments={"led": "#f5a524", "led_off": "#c9ced8", "display": "#14161b", "display_text": "#f5b547",
                 "canvas": "#eef0f4", "canvas_grid": "#cdd3dc", "guide": "#e0457b"},
)
