"""Interface and code fonts, and the interface size, in the designer's settings."""

from pyzed import _core
from pyzed.designer import commands, dialogs, preferences, settings
from pyzed.designer.app import Designer


def test_font_families_list_the_bundled_fonts():
    families = _core.font_families()
    assert "IBM Plex Sans" in families and "IBM Plex Mono" in families
    assert families == sorted(set(families), key=str.lower)
    assert "lucide" not in dialogs.font_families()


def test_fonts_and_interface_size_apply_and_are_saved():
    d = Designer(language_servers=False)
    assert d.scale == 1.0
    d.set_ui_font("DejaVu Sans")
    d.set_ui_scale(1.2)
    d.assist.set("font_family", "DejaVu Sans Mono")
    assert preferences.load().ui_font == "DejaVu Sans"
    assert preferences.load().ui_scale == 1.2
    assert settings.load().font_family == "DejaVu Sans Mono"
    d.dialog = "settings"
    d.view()
    # a new designer starts with them
    again = Designer(language_servers=False)
    assert again.scale == 1.2 and again.prefs.ui_font == "DejaVu Sans"
    again.set_ui_font("")
    again.assist.set("font_family", "")


def test_zooming_the_interface_stays_in_range():
    d = Designer(language_servers=False)
    d.zoom_ui(1)
    assert d.scale == 1.05
    for _ in range(30):
        d.zoom_ui(1)
    assert d.scale == preferences.UI_SCALE[1]
    d.zoom_ui(0)
    assert d.scale == 1.0
    d.set_ui_scale(0.1)
    assert d.scale == preferences.UI_SCALE[0]
    assert preferences.DesignerSettings.from_dict({"ui_scale": 9}).ui_scale == preferences.UI_SCALE[1]
    ids = {a.id for a in commands.ACTIONS}
    assert {"zoom_in_ui", "zoom_out_ui", "reset_ui_zoom"} <= ids


def test_panel_windows_follow_the_interface_size():
    from pyzed.designer.windows import DocWindow, Pane

    d = Designer(language_servers=False)
    d.set_ui_scale(1.25)
    assert DocWindow(d, Pane(place="window:1")).scale == 1.25
