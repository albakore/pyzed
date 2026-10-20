"""Tests for custom window frames: ui.window_frame, the platform styles and Window.frame."""

import pytest

import pyzed as pz
from pyzed import _core, ui
from pyzed.ui import frame


def test_resolve_frame_values(monkeypatch):
    monkeypatch.setattr(frame, "system_platform", lambda: "gnome")
    assert frame.resolve(None) is None and frame.resolve(False) is None and frame.resolve("system") is None
    assert frame.resolve("custom") == "gnome" and frame.resolve(True) == "gnome"
    assert frame.resolve("windows") == "windows"
    # on macOS the system keeps drawing its own buttons over the custom bar
    monkeypatch.setattr(frame, "system_platform", lambda: "macos")
    assert frame.resolve("custom") == "overlay" and frame.resolve("macos") == "macos"
    with pytest.raises(ValueError):
        frame.resolve("beos")


@pytest.mark.parametrize("platform, env, expected", [
    ("darwin", {}, "macos"),
    ("win32", {}, "windows"),
    ("linux", {"XDG_CURRENT_DESKTOP": "KDE"}, "kde"),
    ("linux", {"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}, "ubuntu"),
    ("linux", {"XDG_CURRENT_DESKTOP": "GNOME"}, "gnome"),
    ("linux", {"WSL_DISTRO_NAME": "Ubuntu", "XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}, "windows"),
])
def test_system_platform(monkeypatch, platform, env, expected):
    for name in ("XDG_CURRENT_DESKTOP", "DESKTOP_SESSION", "WSL_DISTRO_NAME", "WSL_INTEROP"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(frame.sys, "platform", platform)
    monkeypatch.setattr("pyzed._platform.sys.platform", platform)
    monkeypatch.setattr("pyzed._platform.is_wsl", lambda release=None: "WSL_DISTRO_NAME" in env)
    assert ui.system_platform() == expected


@pytest.mark.parametrize("style", frame.PLATFORMS)
def test_every_style_draws(style):
    assert isinstance(ui.window_controls(style), _core.Widget)
    assert isinstance(ui.window_controls(style, on_close=lambda: None, maximized=True, focused=False), _core.Widget)
    assert isinstance(ui.window_title_bar("Notes", style=style, start=[ui.label("x")], end=[ui.label("y")]),
                      _core.Widget)
    with pytest.raises(ValueError):
        ui.window_controls("beos")


def test_start_and_end_offsets_follow_the_buttons():
    assert frame.start_x("macos") == frame.controls_width("macos") + 10 and frame.end_x("macos") == 8
    assert frame.start_x("windows") == 8 and frame.end_x("windows") == 138 + 10


def test_commands():
    for direction in ("n", "s", "e", "w", "ne", "nw", "se", "sw"):
        assert isinstance(pz.Command.drag_resize_window(direction), pz.Command)
    with pytest.raises(ValueError):
        pz.Command.drag_resize_window("up")
    assert isinstance(pz.Command.maximize_window(False), pz.Command)
    assert isinstance(pz.Command.show_window_menu(), pz.Command)
    assert repr(pz.window_edges(pz.text("x"), enabled=False)) == "<Widget window_edges>"
    with pytest.raises(ValueError):
        pz.window_edges(pz.text("x"), border=-1)


class Framed(pz.App):
    frame = "windows"
    title = "Notes"

    def __init__(self):
        self.opened = 0
        self.closing_allowed = True

    def open_file(self):
        self.opened += 1

    def frame_menus(self):
        return [ui.Menu("File", [ui.MenuItem("Open", self.open_file), ui.SEPARATOR, "Recent"])]

    def on_close(self):
        return None if self.closing_allowed else False

    def view(self):
        return pz.text("body")


def test_window_frame_settings_and_automatic_frame():
    app = Framed()
    assert app.__pyzed_frame__() == "windows"
    assert pz.App.__pyzed_frame__(pz.App()) is None
    framed = []
    real = frame.window_frame
    frame.window_frame = lambda content, **kw: framed.append(kw) or real(content, **kw)
    try:
        assert isinstance(app.__pyzed_view__(), _core.Widget)
    finally:
        frame.window_frame = real
    assert [m.label for m in framed[0]["menus"]] == ["File"]
    # a view that draws its own frame is not framed twice
    drawn = []

    class Own(Framed):
        def view(self):
            drawn.append(True)
            return ui.window_frame(pz.text("body"), end=[ui.label("x")])

    own = Own()
    with frame.drawing(own) as mark:
        own.view()
    assert mark.drawn and mark.style == "windows" and drawn


def test_menus_open_follow_the_pointer_and_close():
    app = Framed()
    state = frame._menu_state(app)
    with frame.drawing(app):
        ui.window_frame(pz.text("body"), menus=app.frame_menus())
    assert state.open is None and not state.expanded
    # collapsed, the menus hide behind one ☰ button; open, every menu's name shows
    assert len(frame._menu_bar(app.frame_menus() * 3, state, True, 32, pz.themes.ONE_DARK)) == 1
    state.open, state.expanded, state.x = 0, True, 8.0
    assert len(frame._menu_bar(app.frame_menus() * 3, state, True, 32, pz.themes.ONE_DARK)) == 3
    with frame.drawing(app):
        widget = ui.window_frame(pz.text("body"), menus=app.frame_menus())
    assert isinstance(widget, _core.Widget) and state.x == 8.0


def test_close_button_asks_on_close():
    app = Framed()
    app.closing_allowed = False
    assert frame._close_window(app) is None
    app.closing_allowed = True
    assert isinstance(frame._close_window(app), pz.Command)


def test_window_state_defaults():
    window = pz.Window()
    assert window.window_maximized is False and window.window_focused is True
    assert isinstance(window.minimize(), pz.Command) and isinstance(window.toggle_maximize(), pz.Command)


def test_designer_frame_preferences_and_preview():
    from pyzed.designer import preferences
    from pyzed.designer.app import Designer
    from pyzed.designer import surface

    d = Designer(language_servers=False)
    assert d.frame == "custom" and d.preview_frame is None
    assert surface.frame_style(d) == ui.system_platform()
    d.set_preview("frame", "windows")
    assert d.preview_frame == "windows" and preferences.load().preview_frame == "windows"
    assert surface.frame_style(d) == "windows"
    d.open_preview_picker("frame")
    assert d.dialog == "preview_frame" and d.dialog_view(d.theme_obj) is not None
    d.set_preview("frame", None)
    assert d.preview_frame is None and preferences.load().preview_frame == ""
    # back to the system's frame on the next start
    d.set_window_frame(False)
    assert preferences.load().window_frame is False
    assert Designer(language_servers=False).frame is None
    for style in ("macos", "windows", "gnome", "overlay"):
        d.frame = style if style != "overlay" else "custom"
        d.app_menu = "file"
        d.view()
        d.app_menu = "help"
        d.view()


def test_designer_title_center_and_palette_places():
    from pyzed.designer import dialogs
    from pyzed.designer.app import Designer

    d = Designer(language_servers=False)
    # Run, Stop and the search field sit in the middle of the bar, with both frames
    start, end = d.title_items(d.theme_obj)
    assert len(end) == 3 and isinstance(d.title_center(d.theme_obj), _core.Widget)
    assert isinstance(d.title_bar(d.theme_obj), _core.Widget)
    d.open_palette()
    assert d.dialog == "palette" and d.dialog_view(d.theme_obj) is not None
    places = {item.label: item for item in dialogs.places(d, d.theme_obj)}
    assert "Panel: Properties" in places and "Editor settings: Cursor" in places
    places["Editor settings: Cursor"].on_press()
    assert d.dialog == "editor_settings" and d.assist.settings_section == "cursor"
    d.open_palette()
    places["Panel: Events"].on_press()
    assert d.dialog is None
