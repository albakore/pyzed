"""States, sizes and events of the form controls in ``pyzed.ui.inputs`` and ``pyzed.ui.controls``."""

from types import SimpleNamespace

import pytest

import pyzed as pz
from pyzed import ui
from ui_tree import install

T = pz.themes.ONE_DARK


@pytest.fixture
def tree(monkeypatch):
    return install(monkeypatch)


def test_input_states(tree):
    got = []
    disabled = ui.input("a", got.append, on_submit=got.append, disabled=True, theme=T)
    assert disabled.props["on_input"] is None and disabled.props["on_submit"] is None
    assert disabled.props["color"] == T.text_disabled
    readonly = ui.input("a", got.append, readonly=True, theme=T)
    assert readonly.props["on_input"]("changed") is None and got == []  # selectable, not editable
    invalid = ui.input("a", got.append, invalid=True, theme=T)
    assert invalid.props["border_color"] == T.error and invalid.props["focus_border_color"] == T.error
    limited = ui.input("ab", got.append, max_length=3, theme=T)
    limited.props["on_input"]("abcd")
    limited.props["on_input"]("abc")
    assert got == ["abc"]


def test_input_clear_button(tree):
    cleared = []
    field = ui.input("text", print, on_clear=lambda: cleared.append(True), theme=T)
    assert field.kind == "stack"
    field.find("button").args[1]()
    assert cleared == [True]
    assert ui.input("", print, on_clear=print, theme=T).kind == "text_input"  # nothing to clear


def test_switch_and_checkbox(tree):
    assert ui.switch(True, print, disabled=True, theme=T).props["on_toggle"] is None
    assert ui.switch(True, print, size="lg", theme=T).props["size"] == 20
    small = ui.checkbox(False, print, size="sm", theme=T)
    assert small.props["size"] == 14 and small.props["text_size"] == 12.5
    assert ui.checkbox(True, print, disabled=True, theme=T).props["on_toggle"] is None
    got = []
    mixed = ui.checkbox(None, got.append, label="Some", theme=T)
    assert mixed.kind == "events" and "Some" in mixed.texts()
    mixed.props["click"]()
    assert got == [True]


def test_slider_options(tree):
    released = []
    bar = ui.slider(0.5, print, on_release=lambda: released.append(1), theme=T)
    assert bar.props["on_release"] is not None and bar.props["width"] == "fill"
    vertical = ui.slider(3, print, min=0, max=10, step=1, vertical=True, show_value=True, height=100, theme=T)
    assert vertical.kind == "column" and vertical.texts() == ["3"]
    assert vertical.find("slider").props["vertical"] is True
    assert ui.slider(0.25, print, show_value="{:.0%}", theme=T).texts() == ["25%"]
    off = ui.slider(0.5, print, on_release=print, disabled=True, theme=T)
    assert off.props["on_change"] is None and off.props["on_release"] is None


def test_segmented_values_icons_and_disabled(tree):
    got = []
    seg = ui.segmented([("a", "Bold", "bold"), ("b", "Italic"), "c"], "a", got.append, disabled={"c"},
                       width="fill", theme=T)
    buttons = seg.find_all("button")
    assert [b.props["width"] for b in buttons] == ["fill"] * 3
    buttons[1].args[1]()
    assert got == ["b"]
    assert buttons[2].args[1] is None  # disabled
    assert seg.texts()[1:] == ["Bold", "Italic", "c"]  # after the bold icon


def test_select_states(tree):
    opened = []
    select = ui.select(["x", "y"], "x", print, on_open=lambda: opened.append(1), invalid=True, theme=T)
    assert select.props["on_open"] is not None and select.props["border_color"] == T.error
    off = ui.select(["x"], None, print, on_open=print, disabled=True, theme=T)
    assert off.args[2] is None and off.props["on_open"] is None


def test_radio_group_disabled_and_descriptions(tree):
    got = []
    group = ui.radio_group(["a", "b"], "a", got.append, disabled={"b"}, descriptions={"a": "First"}, theme=T)
    radios = group.find_all("radio")
    assert radios[0].args[2] is not None and radios[1].args[2] is None
    assert "First" in group.texts()


def key(name):
    return SimpleNamespace(key=name)


def test_number_field_keys_and_states(tree):
    got = []
    field = ui.number_field(5, got.append, min=0, max=20, step=1, prefix="$", theme=T)
    assert field.kind == "events" and "$" in field.texts()
    on_key = field.props["key_down"]
    on_key(key("up"))
    on_key(key("shift-down"))
    on_key(key("home"))
    on_key(key("end"))
    on_key(key("a"))
    assert got == [6, 0, 0, 20]  # shift steps ten, clamped to min
    shown = ui.number_field(1.5, print, decimals=2, theme=T).find("text_input")
    assert shown.args[0] == "1.50"
    off = ui.number_field(1, got.append, disabled=True, invalid=True, theme=T)
    assert off.kind == "container" and off.props["border_color"] == T.error
    assert off.find("text_input").props["on_input"] is None
    assert all(b.args[1] is None for b in off.find_all("button"))


def test_toggle_group_multiple_tooltips_and_disabled(tree):
    got = []
    group = ui.toggle_group([("l", "align-left", "Left"), ("r", "align-right")], {"l"}, got.append,
                            multiple=True, disabled={"r"}, theme=T)
    buttons = group.find_all("button")
    assert buttons[0].props["bg"] == T.element_selected and buttons[1].args[1] is None
    buttons[0].args[1]()
    assert got == ["l"]
    assert "Left" in group.texts()  # the tooltip


def test_chip_and_split_button(tree):
    chip = ui.chip("x", on_press=print, on_remove=print, disabled=True, theme=T)
    assert chip.kind == "container"  # not pressable
    assert chip.find("button").args[1] is None  # the x is shown but does nothing
    tinted = ui.chip("err", on_press=print, selected=True, tint="error", theme=T)
    assert tinted.props["bg"] == pz.theme.alpha(T.error, 0.18)
    split = ui.split_button("Run", print, print, disabled=True, tooltip="Run it", theme=T)
    assert all(b.args[1] is None for b in split.find_all("button")) and "Run it" in split.texts()


def test_field_required_and_vertical(tree):
    field = ui.field("Name", ui.input("", print, theme=T), required=True, vertical=True, error="Required", theme=T)
    assert field.kind == "column" and field.texts() == ["Name", "*", "Required"]


def test_controls_render_for_real():
    widgets = [
        ui.input("a", print, on_clear=print, invalid=True), ui.checkbox(None, print, label="Mixed"),
        ui.slider(1, print, vertical=True, show_value=True), ui.number_field(1, print, prefix="$"),
        ui.select(["x"], "x", print, on_open=print, on_close=print),
    ]
    assert all(isinstance(w, pz.Widget) for w in widgets)
