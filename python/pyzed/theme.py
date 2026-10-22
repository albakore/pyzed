"""Themes: color tokens modeled after Zed's theme schema.

Every component reads its colors from the *current* theme, so switching
``App.theme`` restyles the whole UI. Ways to get a theme:

    themes.AYU_DARK                                   # built-in (Zed's own themes)
    themes.get("Gruvbox Light")                       # by name
    themes.ONE_DARK.derive(name="Ocean", accent="#4fb3ff")   # tweak tokens
    themes.ONE_DARK.with_accent("#e5c07b")            # recolor accents only
    Theme.generate("Ocean", background="#0f1419", text="#e6e1cf", accent="#39bae6")
    themes.load_zed("my-theme.json")                  # any Zed theme family file
    themes.auto(themes.ONE_LIGHT, themes.ONE_DARK)    # follow the OS appearance

Use a theme for part of the UI with ``with theme:`` (components built inside the
block use it), or pass ``theme=`` to any component.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

SyntaxStyle = Union[str, Tuple[str, str]]


@dataclass(frozen=True)
class Theme:
    """A complete set of design tokens: surfaces, borders, text, status, editor and syntax colors.

    Colors are ``"#rrggbb"`` or ``"#rrggbbaa"`` strings. Themes are immutable; use
    ``derive``/``with_accent`` to make variations.

    Events:
        ``on_accent()``:
    """

    name: str
    appearance: str  # "dark" | "light"

    # Surfaces
    background: str
    surface: str
    elevated: str
    editor: str
    title_bar: str
    status_bar: str
    tab_bar: str
    tab_active: str
    tab_inactive: str
    panel: str
    terminal: str

    # Borders
    border: str
    border_variant: str
    border_focused: str
    border_selected: str

    # Interactive elements
    element: str
    element_hover: str
    element_active: str
    element_selected: str
    ghost_hover: str
    ghost_active: str
    ghost_selected: str

    # Text & icons
    text: str
    text_muted: str
    text_placeholder: str
    text_disabled: str
    text_accent: str
    icon: str
    icon_muted: str
    accent: str
    on_accent: str

    # Status
    error: str
    warning: str
    success: str
    info: str
    hint: str
    created: str
    modified: str
    deleted: str
    conflict: str
    ignored: str

    # Editor
    editor_text: str
    line_number: str
    line_number_active: str
    active_line: str
    selection: str
    scrollbar: str
    scrollbar_hover: str
    search_match: str
    shadow: str

    # Syntax tokens (Zed names) -> color or (color, "italic"/"bold")
    syntax: Dict[str, SyntaxStyle] = field(default_factory=dict)

    # Avatar / collaborator colors
    players: Tuple[str, ...] = ()

    # Terminal ANSI colors
    ansi: Dict[str, str] = field(default_factory=dict)

    # Metrics
    radius: float = 6.0
    radius_sm: float = 4.0
    ui_font_size: float = 14.0
    buffer_font_size: float = 14.0

    @property
    def is_dark(self) -> bool:
        """Whether the theme's appearance is dark."""
        return self.appearance == "dark"

    def derive(self, **changes) -> "Theme":
        """Returns a copy with some tokens replaced. ``syntax`` / ``ansi`` dicts are merged."""
        if "syntax" in changes:
            changes["syntax"] = {**self.syntax, **changes["syntax"]}
        if "ansi" in changes:
            changes["ansi"] = {**self.ansi, **changes["ansi"]}
        return replace(self, **changes)

    def with_accent(self, accent: str) -> "Theme":
        """A copy whose accent color (focus rings, selection, links, primary buttons) is ``accent``."""
        players = (accent, *self.players[1:]) if self.players else (accent,)
        return self.derive(
            accent=accent,
            text_accent=accent,
            info=accent,
            border_focused=accent,
            border_selected=alpha(accent, 0.45),
            selection=alpha(accent, 0.24),
            search_match=alpha(accent, 0.4),
            on_accent=readable_on(accent),
            players=players,
        )

    def tokens(self) -> Dict[str, object]:
        """All tokens as a dict (a shallow copy)."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def to_dict(self) -> Dict[str, Any]:
        """A JSON-friendly dict; ``Theme.from_dict`` reads it back."""
        out = self.tokens()
        out["syntax"] = {k: list(v) if isinstance(v, tuple) else v for k, v in self.syntax.items()}
        out["players"] = list(self.players)
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any], *, base: Optional["Theme"] = None) -> "Theme":
        """Builds a theme from ``to_dict`` output. Missing tokens come from ``base``
        (One Dark or One Light, depending on ``appearance``)."""
        data = dict(data)
        if base is None:
            base = ONE_LIGHT if data.get("appearance") == "light" else ONE_DARK
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"unknown theme tokens: {', '.join(sorted(unknown))}")
        if "syntax" in data:
            data["syntax"] = {k: tuple(v) if isinstance(v, list) else v for k, v in data["syntax"].items()}
        if "players" in data:
            data["players"] = tuple(data["players"])
        return base.derive(**data)

    def save(self, path: Union[str, Path]) -> None:
        """Writes the theme as JSON (Pyzed's own format; see ``Theme.load``)."""
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Union[str, Path]) -> "Theme":
        """Reads a theme written by ``save`` (for Zed theme files use ``Theme.from_zed``)."""
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def __enter__(self) -> "Theme":
        _stack.append(_current)
        use(self)
        return self

    def __exit__(self, *exc) -> None:
        use(_stack.pop())

    # -- constructors -------------------------------------------------------
    @classmethod
    def generate(
        cls,
        name: str,
        *,
        background: str,
        text: str,
        accent: str,
        appearance: Optional[str] = None,
        error: Optional[str] = None,
        warning: Optional[str] = None,
        success: Optional[str] = None,
        syntax: Optional[Dict[str, SyntaxStyle]] = None,
        radius: float = 6.0,
    ) -> "Theme":
        """Derives a full theme from a handful of base colors.

        ``background`` is the editor/canvas color; surfaces, borders, hover states and
        muted text are mixed from it and ``text``. ``appearance`` is guessed from the
        background's brightness when omitted.
        """
        dark = (appearance == "dark") if appearance else luminance(background) < 0.4
        base = ONE_DARK if dark else ONE_LIGHT
        shade = "#ffffff" if dark else "#000000"
        def step(amount: float) -> str:
            return mix(background, shade, amount)
        surface = step(0.04)
        chrome = step(0.08)
        theme = base.derive(
            name=name,
            appearance="dark" if dark else "light",
            background=chrome,
            surface=surface,
            elevated=surface,
            editor=background,
            title_bar=chrome,
            status_bar=chrome,
            tab_bar=surface,
            tab_active=background,
            tab_inactive=surface,
            panel=surface,
            terminal=background,
            border=step(0.16),
            border_variant=step(0.10),
            element=step(0.06),
            element_hover=step(0.10),
            element_active=step(0.15),
            element_selected=step(0.15),
            ghost_hover=step(0.10),
            ghost_active=step(0.15),
            ghost_selected=step(0.15),
            text=text,
            text_muted=mix(text, background, 0.3),
            text_placeholder=mix(text, background, 0.45),
            text_disabled=mix(text, background, 0.5),
            icon=text,
            icon_muted=mix(text, background, 0.3),
            editor_text=mix(text, background, 0.1),
            line_number=mix(text, background, 0.6),
            line_number_active=text,
            active_line=alpha(step(0.05), 0.75),
            scrollbar=alpha(text, 0.3),
            scrollbar_hover=alpha(text, 0.5),
            error=error or base.error,
            warning=warning or base.warning,
            success=success or base.success,
            created=success or base.created,
            modified=warning or base.modified,
            deleted=error or base.deleted,
            conflict=warning or base.conflict,
            ignored=mix(text, background, 0.5),
            radius=radius,
            radius_sm=max(radius - 2, 0),
            syntax={**base.syntax, "primary": mix(text, background, 0.1), **(syntax or {})},
            ansi={**base.ansi, "black": background, "white": text},
        )
        return theme.with_accent(accent)

    @classmethod
    def from_zed(cls, source: Union[str, Path, Dict[str, Any]], name: Optional[str] = None) -> "Theme":
        """Reads a theme from a Zed theme family file (``.json``) or dict.

        A family usually holds several themes (e.g. Ayu Dark/Light/Mirage); ``name``
        picks one (the first one by default). See ``themes.load_zed`` to load them all.
        """
        family = _read_json(source)
        entries = family.get("themes", [family])
        for entry in entries:
            if name is None or entry.get("name") == name:
                return _from_zed_style(entry)
        raise ValueError(f"theme {name!r} not found; available: {[e.get('name') for e in entries]}")

    def color(self, name: str) -> str:
        """Resolves a token name ("accent", "text_muted", "error"...) or passes a hex color through."""
        if name.startswith("#") or name == "transparent":
            return name
        return getattr(self, name)

    def palette(self):
        """The base palette handed to iced for its built-in widget styles."""
        return [self.editor, self.text, self.accent, self.success, self.warning, self.error, self.name]

    def syntax_scopes(self) -> Dict[str, SyntaxStyle]:
        """Maps TextMate scopes (used by the highlighter) to this theme's syntax colors."""
        out: Dict[str, SyntaxStyle] = {}
        for selector, token in SCOPES:
            style = self.syntax.get(token)
            if style is None and "." in token:
                style = self.syntax.get(token.split(".")[0])
            if style is not None:
                out[selector] = style
        return out


# TextMate scope selector -> Zed syntax token. Later, more specific selectors win.
SCOPES = [
    ("source, text", "primary"),
    ("comment, punctuation.definition.comment", "comment"),
    ("comment.block.documentation, comment.line.documentation", "comment.doc"),
    ("string, punctuation.definition.string", "string"),
    ("constant.character.escape", "string.escape"),
    ("string.regexp", "string.regex"),
    ("constant.other.placeholder, string.interpolated", "string.special"),
    ("constant.numeric, keyword.other.unit", "number"),
    ("constant.language", "boolean"),
    ("constant.other, variable.other.constant, entity.name.constant, support.constant", "constant"),
    ("keyword, storage, storage.type, storage.modifier, keyword.control, keyword.declaration", "keyword"),
    ("keyword.operator, punctuation.accessor", "operator"),
    ("keyword.operator.word, keyword.operator.logical.python, keyword.operator.new", "keyword"),
    ("entity.name.function, support.function, variable.function, meta.function-call.generic", "function"),
    ("support.macro, entity.name.macro, support.function.macro", "function"),
    (
        "entity.name.type, entity.name.class, entity.name.struct, entity.name.enum, entity.name.trait, "
        "entity.name.impl, entity.name.union, support.type, support.class, entity.other.inherited-class, "
        "storage.type.rust, storage.type.primitive, storage.type.builtin, support.type.primitive",
        "type",
    ),
    ("entity.name.namespace, entity.name.module", "primary"),
    ("variable, variable.other, variable.parameter", "variable"),
    ("variable.language, variable.language.self, variable.parameter.function.language.special", "variable.special"),
    (
        "variable.other.member, variable.other.property, meta.property, support.variable.property, "
        "variable.other.object.property, support.type.property-name, meta.mapping.key string, "
        "entity.name.tag.yaml, meta.object-literal.key",
        "property",
    ),
    ("entity.name.tag", "tag"),
    ("entity.other.attribute-name", "attribute"),
    (
        "meta.annotation, meta.decorator, entity.name.function.decorator, meta.attribute, "
        "punctuation.definition.annotation, punctuation.definition.decorator",
        "attribute",
    ),
    ("entity.name.label, storage.modifier.lifetime", "label"),
    ("punctuation, meta.brace", "punctuation"),
    ("punctuation.section, punctuation.separator, meta.brace.round, meta.brace.square", "punctuation.bracket"),
    ("markup.heading, entity.name.section, markup.heading punctuation.definition", "title"),
    ("markup.bold", "emphasis.strong"),
    ("markup.italic", "emphasis"),
    ("markup.raw, markup.inline.raw, markup.raw.block", "text.literal"),
    ("markup.underline.link, string.other.link", "link_uri"),
    ("markup.list punctuation.definition.list_item", "punctuation.list_marker"),
    ("markup.inserted", "created"),
    ("markup.deleted", "deleted"),
    ("markup.changed", "modified"),
]


ONE_DARK = Theme(
    name="One Dark",
    appearance="dark",
    background="#3b414d",
    surface="#2f343e",
    elevated="#2f343e",
    editor="#282c33",
    title_bar="#3b414d",
    status_bar="#3b414d",
    tab_bar="#2f343e",
    tab_active="#282c33",
    tab_inactive="#2f343e",
    panel="#2f343e",
    terminal="#282c33",
    border="#464b57",
    border_variant="#363c46",
    border_focused="#47679e",
    border_selected="#293b5b",
    element="#2e343e",
    element_hover="#363c46",
    element_active="#454a56",
    element_selected="#454a56",
    ghost_hover="#363c46",
    ghost_active="#454a56",
    ghost_selected="#454a56",
    text="#dce0e5",
    text_muted="#a9afbc",
    text_placeholder="#878a98",
    text_disabled="#878a98",
    text_accent="#74ade8",
    icon="#dce0e5",
    icon_muted="#a9afbc",
    accent="#74ade8",
    on_accent="#1c2025",
    error="#d07277",
    warning="#dec184",
    success="#a1c181",
    info="#74ade8",
    hint="#788ca6",
    created="#a1c181",
    modified="#dec184",
    deleted="#d07277",
    conflict="#dec184",
    ignored="#878a98",
    editor_text="#acb2be",
    line_number="#4e5a5f",
    line_number_active="#d0d4da",
    active_line="#2f343ebf",
    selection="#74ade83d",
    scrollbar="#c8ccd44c",
    scrollbar_hover="#c8ccd480",
    search_match="#74ade866",
    shadow="#0000004d",
    syntax={
        "primary": "#acb2be",
        "attribute": "#74ade8",
        "boolean": "#bf956a",
        "comment": "#5d636f",
        "comment.doc": "#878e98",
        "constant": "#dfc184",
        "constructor": "#73ade9",
        "emphasis": ("#74ade8", "italic"),
        "emphasis.strong": ("#bf956a", "bold"),
        "enum": "#d07277",
        "function": "#73ade9",
        "keyword": "#b477cf",
        "label": "#74ade8",
        "link_uri": "#6eb4bf",
        "number": "#bf956a",
        "operator": "#6eb4bf",
        "property": "#d07277",
        "punctuation": "#acb2be",
        "punctuation.bracket": "#b2b9c6",
        "punctuation.list_marker": "#d07277",
        "string": "#a1c181",
        "string.escape": "#878e98",
        "string.regex": "#bf956a",
        "string.special": "#bf956a",
        "tag": "#74ade8",
        "text.literal": "#a1c181",
        "title": "#d07277",
        "type": "#6eb4bf",
        "variable": "#acb2be",
        "variable.special": "#bf956a",
        "created": "#a1c181",
        "deleted": "#d07277",
        "modified": "#dec184",
    },
    players=("#74ade8", "#be5046", "#bf956a", "#b477cf", "#6eb4bf", "#d07277", "#dec184", "#a1c181"),
    ansi={
        "black": "#282c33",
        "red": "#d07277",
        "green": "#a1c181",
        "yellow": "#dec184",
        "blue": "#74ade8",
        "magenta": "#b477cf",
        "cyan": "#6eb4bf",
        "white": "#dce0e5",
        "bright_black": "#636d83",
        "dim": "#878a98",
    },
)

ONE_LIGHT = Theme(
    name="One Light",
    appearance="light",
    background="#dcdcdd",
    surface="#ebebec",
    elevated="#ebebec",
    editor="#fafafa",
    title_bar="#dcdcdd",
    status_bar="#dcdcdd",
    tab_bar="#ebebec",
    tab_active="#fafafa",
    tab_inactive="#ebebec",
    panel="#ebebec",
    terminal="#fafafa",
    border="#c9c9ca",
    border_variant="#dfdfe0",
    border_focused="#7d82e8",
    border_selected="#cbcdf6",
    element="#ebebec",
    element_hover="#dfdfe0",
    element_active="#cacaca",
    element_selected="#cacaca",
    ghost_hover="#dfdfe0",
    ghost_active="#cacaca",
    ghost_selected="#cacaca",
    text="#242529",
    text_muted="#58585a",
    text_placeholder="#7e8086",
    text_disabled="#7e8086",
    text_accent="#5c78e2",
    icon="#242529",
    icon_muted="#58585a",
    accent="#5c78e2",
    on_accent="#fafafa",
    error="#d36151",
    warning="#a48819",
    success="#669f59",
    info="#5c78e2",
    hint="#7274a7",
    created="#669f59",
    modified="#a48819",
    deleted="#d36151",
    conflict="#a48819",
    ignored="#7e8086",
    editor_text="#242529",
    line_number="#a2a3a7",
    line_number_active="#242529",
    active_line="#ebebecbf",
    selection="#5c78e23d",
    scrollbar="#2425294c",
    scrollbar_hover="#24252980",
    search_match="#5c78e266",
    shadow="#00000026",
    syntax={
        "primary": "#242529",
        "attribute": "#5c78e2",
        "boolean": "#ad6e25",
        "comment": "#a2a3a7",
        "comment.doc": "#7c7e86",
        "constant": "#c18401",
        "constructor": "#5c78e2",
        "emphasis": ("#5c78e2", "italic"),
        "emphasis.strong": ("#ad6e25", "bold"),
        "enum": "#d3604f",
        "function": "#5b79e3",
        "keyword": "#a449ab",
        "label": "#5c78e2",
        "link_uri": "#3882b7",
        "number": "#ad6e25",
        "operator": "#3882b7",
        "property": "#d3604f",
        "punctuation": "#242529",
        "punctuation.bracket": "#4d4f52",
        "punctuation.list_marker": "#d3604f",
        "string": "#649f57",
        "string.escape": "#7c7e86",
        "string.regex": "#ad6e25",
        "string.special": "#ad6e25",
        "tag": "#5c78e2",
        "text.literal": "#649f57",
        "title": "#d3604f",
        "type": "#3882b7",
        "variable": "#242529",
        "variable.special": "#ad6e25",
        "created": "#669f59",
        "deleted": "#d36151",
        "modified": "#a48819",
    },
    players=("#5c78e2", "#984ea5", "#a44f2d", "#a449ab", "#3a82b7", "#d36151", "#a48819", "#669f59"),
    ansi={
        "black": "#242529",
        "red": "#d36151",
        "green": "#669f59",
        "yellow": "#a48819",
        "blue": "#5c78e2",
        "magenta": "#a449ab",
        "cyan": "#3a82b7",
        "white": "#fafafa",
        "bright_black": "#7e8086",
        "dim": "#7e8086",
    },
)

GRUVBOX_DARK = ONE_DARK.derive(
    name="Gruvbox Dark",
    background="#3a3735",
    surface="#3a3735",
    elevated="#3a3735",
    editor="#282828",
    title_bar="#3a3735",
    status_bar="#3a3735",
    tab_bar="#3a3735",
    tab_active="#282828",
    tab_inactive="#3a3735",
    panel="#3a3735",
    terminal="#282828",
    border="#5b534d",
    border_variant="#494340",
    border_focused="#303a36",
    element="#3a3735",
    element_hover="#494340",
    element_active="#5b524c",
    element_selected="#5b524c",
    ghost_hover="#494340",
    ghost_active="#5b524c",
    ghost_selected="#5b524c",
    text="#fbf1c7",
    text_muted="#c5b597",
    text_placeholder="#998b78",
    text_disabled="#998b78",
    text_accent="#83a598",
    icon="#fbf1c7",
    icon_muted="#c5b597",
    accent="#83a598",
    error="#fb4934",
    warning="#fabd2f",
    success="#b8bb26",
    info="#83a598",
    created="#b8bb26",
    modified="#fabd2f",
    deleted="#fb4934",
    editor_text="#ebdbb2",
    line_number="#7c6f64",
    line_number_active="#e5d5ad",
    active_line="#3a3735bf",
    selection="#83a5983d",
    syntax={
        "primary": "#ebdbb2",
        "comment": "#a89984",
        "keyword": "#fb4934",
        "function": "#b8bb26",
        "type": "#fabd2f",
        "string": "#b8bb26",
        "number": "#d3869b",
        "boolean": "#d3869b",
        "constant": "#d3869b",
        "property": "#83a598",
        "attribute": "#8ec07c",
        "operator": "#8ec07c",
        "variable": "#ebdbb2",
        "variable.special": "#83a598",
        "punctuation": "#d5c4a1",
        "punctuation.bracket": "#a89984",
        "tag": "#8ec07c",
        "title": "#b8bb26",
    },
)


@dataclass(frozen=True)
class AutoTheme:
    """Follows the operating system's appearance: ``light`` in light mode, ``dark`` in dark mode."""

    light: Theme
    dark: Theme

    def pick(self, dark: bool) -> Theme:
        """Returns the dark theme when ``dark`` is true, else the light one."""
        return self.dark if dark else self.light


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------


def _rgba(color: str):
    h = color.lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
    return r, g, b, a


def _hex(r, g, b, a=1.0) -> str:
    clamp = lambda v: max(0, min(255, int(round(v))))  # noqa: E731
    out = f"#{clamp(r):02x}{clamp(g):02x}{clamp(b):02x}"
    return out if a >= 1.0 else out + f"{clamp(a * 255):02x}"


@lru_cache(maxsize=4096)  # views mix the same few colors on every render
def alpha(color: str, value: float) -> str:
    """``color`` with its opacity multiplied by ``value``."""
    r, g, b, a = _rgba(color)
    return _hex(r, g, b, a * value)


@lru_cache(maxsize=4096)  # views mix the same few colors on every render
def mix(a: str, b: str, amount: float = 0.5) -> str:
    """Blends two colors; ``amount=0`` is ``a`` and ``amount=1`` is ``b``."""
    ra, ga, ba, aa = _rgba(a)
    rb, gb, bb, ab = _rgba(b)
    t = amount
    return _hex(ra + (rb - ra) * t, ga + (gb - ga) * t, ba + (bb - ba) * t, aa + (ab - aa) * t)


def luminance(color: str) -> float:
    """Relative luminance (0 = black, 1 = white) as defined by WCAG."""
    def channel(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b, _ = _rgba(color)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio between two colors (1 to 21)."""
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@lru_cache(maxsize=4096)  # views mix the same few colors on every render
def readable_on(background: str, light: str = "#fafafa", dark: str = "#1c2025") -> str:
    """Whichever of ``light``/``dark`` text reads better on ``background``."""
    return light if contrast(background, light) >= contrast(background, dark) else dark


def lighten(color: str, amount: float = 0.1) -> str:
    """Mixes ``color`` with white by ``amount`` (0 to 1)."""
    return mix(color, "#ffffff", amount)


def darken(color: str, amount: float = 0.1) -> str:
    """Mixes ``color`` with black by ``amount`` (0 to 1)."""
    return mix(color, "#000000", amount)


# ---------------------------------------------------------------------------
# Zed theme files
# ---------------------------------------------------------------------------

_ZED_KEYS = {
    "background": "background",
    "surface": "surface.background",
    "elevated": "elevated_surface.background",
    "editor": "editor.background",
    "title_bar": "title_bar.background",
    "status_bar": "status_bar.background",
    "tab_bar": "tab_bar.background",
    "tab_active": "tab.active_background",
    "tab_inactive": "tab.inactive_background",
    "panel": "panel.background",
    "terminal": "terminal.background",
    "border": "border",
    "border_variant": "border.variant",
    "border_focused": "border.focused",
    "border_selected": "border.selected",
    "element": "element.background",
    "element_hover": "element.hover",
    "element_active": "element.active",
    "element_selected": "element.selected",
    "ghost_hover": "ghost_element.hover",
    "ghost_active": "ghost_element.active",
    "ghost_selected": "ghost_element.selected",
    "text": "text",
    "text_muted": "text.muted",
    "text_placeholder": "text.placeholder",
    "text_disabled": "text.disabled",
    "text_accent": "text.accent",
    "icon": "icon",
    "icon_muted": "icon.muted",
    "error": "error",
    "warning": "warning",
    "success": "success",
    "info": "info",
    "hint": "hint",
    "created": "created",
    "modified": "modified",
    "deleted": "deleted",
    "conflict": "conflict",
    "ignored": "ignored",
    "editor_text": "editor.foreground",
    "line_number": "editor.line_number",
    "line_number_active": "editor.active_line_number",
    "active_line": "editor.active_line.background",
    "scrollbar": "scrollbar.thumb.background",
    "scrollbar_hover": "scrollbar.thumb.hover_background",
    "search_match": "search.match_background",
}

_ANSI = ("black", "red", "green", "yellow", "blue", "magenta", "cyan", "white", "bright_black")


def _read_json(source: Union[str, Path, Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(source, dict):
        return source
    return json.loads(Path(source).read_text(encoding="utf-8"))


def _short(color: Optional[str]) -> Optional[str]:
    """``#rrggbbff`` -> ``#rrggbb`` (Zed writes alpha even when opaque)."""
    if isinstance(color, str) and len(color) == 9 and color.lower().endswith("ff"):
        return color[:7]
    return color


def _from_zed_style(entry: Dict[str, Any]) -> Theme:
    style = entry.get("style", {})
    appearance = entry.get("appearance", "dark")
    base = ONE_LIGHT if appearance == "light" else ONE_DARK
    tokens: Dict[str, Any] = {"name": entry.get("name", "Zed theme"), "appearance": appearance}
    for token, key in _ZED_KEYS.items():
        value = _short(style.get(key))
        if value:
            tokens[token] = value
    tokens.setdefault("title_bar", tokens.get("background", base.title_bar))
    tokens.setdefault("status_bar", tokens.get("background", base.status_bar))
    players = [p for p in style.get("players", []) if isinstance(p, dict)]
    if players:
        tokens["players"] = tuple(_short(p.get("cursor")) for p in players if p.get("cursor"))
        if players[0].get("selection"):
            tokens["selection"] = players[0]["selection"]
    accent = tokens.get("text_accent") or (tokens.get("players") or (base.accent,))[0]
    tokens["accent"] = accent
    tokens["on_accent"] = readable_on(accent)
    tokens["shadow"] = "#0000004d" if appearance == "dark" else "#00000026"
    syntax: Dict[str, SyntaxStyle] = {}
    for scope, value in (style.get("syntax") or {}).items():
        if not isinstance(value, dict) or not value.get("color"):
            continue
        color = _short(value["color"])
        flags = []
        if value.get("font_style") == "italic":
            flags.append("italic")
        if (value.get("font_weight") or 0) >= 700:
            flags.append("bold")
        syntax[scope] = (color, " ".join(flags)) if flags else color
    if syntax:
        syntax.setdefault("primary", tokens.get("editor_text", base.editor_text))
        tokens["syntax"] = syntax
    ansi = {name: _short(style[f"terminal.ansi.{name}"]) for name in _ANSI if style.get(f"terminal.ansi.{name}")}
    if style.get("terminal.dim_foreground"):
        ansi["dim"] = _short(style["terminal.dim_foreground"])
    if ansi:
        tokens["ansi"] = ansi
    return base.derive(**tokens)


# ---------------------------------------------------------------------------
# Built-in themes and the registry
# ---------------------------------------------------------------------------

_BUNDLED = Path(__file__).with_name("zed_themes")
_registry: Dict[str, Theme] = {}


def _load_bundled(file: str) -> List[Theme]:
    try:
        family = _read_json(_BUNDLED / file)
    except OSError:  # pragma: no cover - broken install
        return []
    return [_from_zed_style(entry) for entry in family.get("themes", [])]


class themes:  # noqa: N801 - namespace
    """Built-in themes (Zed's One, Ayu and Gruvbox families, and Pyzed's own) and the theme registry."""

    ONE_DARK = ONE_DARK
    ONE_LIGHT = ONE_LIGHT
    GRUVBOX_DARK = GRUVBOX_DARK

    @staticmethod
    def all() -> List[Theme]:
        """Every registered theme, in registration order."""
        return list(_registry.values())

    @staticmethod
    def names() -> List[str]:
        """The names of every registered theme, in registration order."""
        return list(_registry)

    @staticmethod
    def get(name: str) -> Theme:
        """Looks a theme up by name (case-insensitive)."""
        if name in _registry:
            return _registry[name]
        for key, value in _registry.items():
            if key.lower() == name.lower():
                return value
        raise KeyError(f"unknown theme {name!r}; available: {', '.join(_registry)}")

    @staticmethod
    def register(theme: Theme) -> Theme:
        """Adds (or replaces) a theme so it can be found by name."""
        _registry[theme.name] = theme
        return theme

    @staticmethod
    def load_zed(source: Union[str, Path, Dict[str, Any]]) -> List[Theme]:
        """Loads and registers every theme in a Zed theme family file."""
        family = _read_json(source)
        return [themes.register(_from_zed_style(entry)) for entry in family.get("themes", [family])]

    @staticmethod
    def auto(light: Union[Theme, str] = "One Light", dark: Union[Theme, str] = "One Dark") -> AutoTheme:
        """A theme that follows the OS light/dark setting."""
        return AutoTheme(
            light if isinstance(light, Theme) else themes.get(light),
            dark if isinstance(dark, Theme) else themes.get(dark),
        )


for _theme in (ONE_DARK, ONE_LIGHT):
    themes.register(_theme)
for _theme in _load_bundled("ayu.json") + _load_bundled("gruvbox.json"):
    themes.register(_theme)
    setattr(themes, _theme.name.upper().replace(" ", "_"), _theme)
GRUVBOX_DARK = themes.GRUVBOX_DARK = _registry.get("Gruvbox Dark", GRUVBOX_DARK)
from .theme_palettes import PYZED_THEMES as _PYZED_THEMES  # noqa: E402 - needs the helpers above

for _theme in _PYZED_THEMES:  # Pyzed's own: Midnight, Graphite, Forest, Rosé, Dawn and Glacier
    themes.register(_theme)
    setattr(themes, _theme.name.upper().replace(" ", "_").replace("É", "E"), _theme)
del _theme


_current: Theme = ONE_DARK
_stack: List[Theme] = []


def current() -> Theme:
    """The theme components use when none is passed explicitly."""
    return _current


def use(theme: Theme) -> None:
    """Sets the current theme (``App`` does this for you before every ``view()``)."""
    global _current
    _current = theme


def resolve(value: Union[Theme, AutoTheme, str, None], *, dark: bool = True) -> Theme:
    """Turns an ``App.theme`` value (theme, name, ``AutoTheme`` or ``None``) into a ``Theme``."""
    if value is None:
        return ONE_DARK if dark else ONE_LIGHT
    if isinstance(value, Theme):
        return value
    if isinstance(value, AutoTheme):
        return value.pick(dark)
    if isinstance(value, str):
        if value == "auto":
            return ONE_DARK if dark else ONE_LIGHT
        return themes.get(value)
    raise TypeError(f"expected a Theme, AutoTheme or theme name, got {type(value).__name__}")
