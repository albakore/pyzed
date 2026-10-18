"""Themes: color tokens modeled after Zed's theme schema.

Every component reads its colors from the *current* theme, so switching
``App.theme`` restyles the whole UI. Create your own with ``Theme.derive``::

    my_theme = themes.ONE_DARK.derive(name="Ocean", accent="#4fb3ff")
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from typing import Dict, Tuple, Union

SyntaxStyle = Union[str, Tuple[str, str]]


@dataclass(frozen=True)
class Theme:
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
        return self.appearance == "dark"

    def derive(self, **changes) -> "Theme":
        """Returns a copy with some tokens replaced. ``syntax`` / ``ansi`` dicts are merged."""
        if "syntax" in changes:
            changes["syntax"] = {**self.syntax, **changes["syntax"]}
        if "ansi" in changes:
            changes["ansi"] = {**self.ansi, **changes["ansi"]}
        return replace(self, **changes)

    def tokens(self) -> Dict[str, object]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

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


class themes:  # noqa: N801 - namespace
    ONE_DARK = ONE_DARK
    ONE_LIGHT = ONE_LIGHT
    GRUVBOX_DARK = GRUVBOX_DARK

    @staticmethod
    def all():
        return [ONE_DARK, ONE_LIGHT, GRUVBOX_DARK]


_current: Theme = ONE_DARK


def current() -> Theme:
    """The theme components use when none is passed explicitly."""
    return _current


def use(theme: Theme) -> None:
    """Sets the current theme (``App`` does this for you before every ``view()``)."""
    global _current
    _current = theme


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


def alpha(color: str, value: float) -> str:
    """``color`` with its opacity multiplied by ``value``."""
    r, g, b, a = _rgba(color)
    return _hex(r, g, b, a * value)


def mix(a: str, b: str, amount: float = 0.5) -> str:
    """Blends two colors; ``amount=0`` is ``a`` and ``amount=1`` is ``b``."""
    ra, ga, ba, aa = _rgba(a)
    rb, gb, bb, ab = _rgba(b)
    t = amount
    return _hex(ra + (rb - ra) * t, ga + (gb - ga) * t, ba + (bb - ba) * t, aa + (ab - aa) * t)
