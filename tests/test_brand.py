"""Pyzed's brand in the library: the logo widgets, the instrument-panel pieces and the brand files."""

import json
from pathlib import Path

import pyzed as pz
from pyzed import _core, brand, ui

ROOT = Path(__file__).resolve().parent.parent


def test_logo_files_ship_with_the_package_and_match_the_brand_folder():
    for path in (brand.ICON, brand.MARK, brand.MARK_DARK, brand.WORDMARK, brand.WORDMARK_DARK):
        assert Path(path).is_file()
    for name in ("pyzed-mark.svg", "pyzed-wordmark-dark.svg"):
        assert (ROOT / "python" / "pyzed" / "brand" / name).read_text() == (ROOT / "assets" / "brand" / name).read_text()
    tokens = json.loads((ROOT / "assets" / "brand" / "tokens.json").read_text())
    dark = pz.themes.PYZED_DARK
    assert tokens["dark"]["surface"].lower() == dark.editor and tokens["dark"]["accent"].lower() == dark.text_accent
    assert tokens["light"]["accent"].lower() == pz.themes.PYZED_LIGHT.accent
    for icon in ("icon.ico", "icon.icns", "icon.png"):
        assert (ROOT / "assets" / icon).stat().st_size > 1000


def test_logo_widgets_build_in_both_appearances():
    assert isinstance(brand.mark(20), _core.Widget)
    assert isinstance(brand.mark(16, color="#ffffff", theme=pz.themes.PYZED_LIGHT), _core.Widget)
    assert isinstance(brand.wordmark(28, theme=pz.themes.ONE_LIGHT), _core.Widget)


def test_instrument_pieces_build_and_toggle():
    seen = []
    assert isinstance(ui.led(True), _core.Widget) and isinstance(ui.led(False, color="success"), _core.Widget)
    assert isinstance(ui.led_toggle("Snap", True, seen.append, tooltip="Snap to grid"), _core.Widget)
    assert isinstance(ui.lcd("60 FPS", None, "wgpu"), _core.Widget)
    assert isinstance(ui.status_item("ruff", led="success"), _core.Widget)
    rack = ui.theme_rack(pz.themes.all()[:5], "Pyzed Dark", seen.append, theme=pz.themes.PYZED_DARK)
    assert isinstance(rack, _core.Widget)


def test_designer_shows_the_brand(tmp_path):
    from pyzed.designer.app import Designer

    d = Designer(language_servers=False)
    t = d.theme_obj
    assert d.icon == brand.ICON and d.app_id == "dev.pyzed.design" and t.name == "Pyzed Dark"
    assert isinstance(d.title_display(t), _core.Widget) and isinstance(d.toolbar(t), _core.Widget)
    from pyzed.designer import new

    form = new.create("form1").form
    assert form.theme == "Pyzed Dark"
