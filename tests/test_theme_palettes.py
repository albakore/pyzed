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


def test_brand_themes_are_the_default_and_readable():
    dark, light = pz.themes.PYZED_DARK, pz.themes.PYZED_LIGHT
    assert pz.themes.names()[:2] == ["Pyzed Dark", "Pyzed Light"]
    assert pz.App.theme is dark and pz.theme.resolve(None, dark=False) is light
    assert pz.theme.resolve("auto", dark=True) is dark and pz.themes.auto().pick(False) is light
    assert (dark.editor, dark.panel, dark.text_accent, dark.accent) == ("#14161b", "#191c22", "#8b83ff", "#5b50f0")
    assert (light.background, light.accent, light.led) == ("#f6f7f9", "#4f46e5", "#f5a524")
    for theme in (dark, light):
        assert contrast(theme.text, theme.editor) >= 7, theme.name
        assert contrast(theme.text_muted, theme.panel) >= 4.5, theme.name
        assert contrast(theme.on_accent, theme.accent) >= 4.5, theme.name
        assert contrast(theme.display_text, theme.display) >= 7, theme.name


def test_instrument_colors_follow_the_other_colors_unless_set():
    gruvbox = pz.themes.get("Gruvbox Dark")
    assert gruvbox.led == gruvbox.warning and gruvbox.canvas == gruvbox.background
    warm = pz.themes.ONE_DARK.derive(warning="#ff8800")
    assert warm.led == "#ff8800"  # followed the new warning color
    lit = pz.themes.ONE_DARK.derive(led="#00ff00").derive(warning="#ff8800")
    assert lit.led == "#00ff00"  # set by hand: kept
    assert pz.Theme.from_dict(pz.themes.PYZED_DARK.to_dict()) == pz.themes.PYZED_DARK
