"""Tests for Pyzed's own themes, made from palettes."""

import pyzed as pz
from pyzed import theme_palettes
from pyzed.theme import contrast


def test_pyzed_themes_are_registered_and_readable():
    names = [t.name for t in theme_palettes.PYZED_THEMES]
    assert names == ["Pyzed Midnight", "Pyzed Graphite", "Pyzed Forest", "Pyzed Rosé", "Pyzed Dawn", "Pyzed Glacier"]
    for theme in theme_palettes.PYZED_THEMES:
        assert pz.themes.get(theme.name) is theme
        assert contrast(theme.text, theme.editor) >= 7, theme.name
        assert contrast(theme.text_muted, theme.panel) >= 4.5, theme.name
        assert contrast(theme.on_accent, theme.accent) >= 4.5, theme.name
        assert theme.is_dark == (theme.name not in ("Pyzed Dawn", "Pyzed Glacier"))
    assert pz.themes.PYZED_ROSE.name == "Pyzed Rosé" and pz.themes.PYZED_MIDNIGHT.is_dark


def test_a_palette_makes_a_complete_theme():
    dusk = theme_palettes.from_palette("Dusk", "dark", editor="#1b1d24", chrome="#23262f", text="#d8dbe2",
                                       accent="#7aa2f7", red="#f7768e", orange="#ff9e64", yellow="#e0af68",
                                       green="#9ece6a", cyan="#7dcfff", purple="#bb9af7")
    assert dusk.syntax["keyword"] == "#bb9af7" and dusk.syntax["string"] == "#9ece6a"
    assert dusk.error == "#f7768e" and dusk.tab_active == dusk.editor and dusk.ansi["blue"] == "#7aa2f7"
    assert dusk.border != dusk.panel and dusk.element_hover != dusk.panel
