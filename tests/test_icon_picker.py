"""Tests for icon search and the icon picker (the library component and the designer's icon dialog)."""

import pyzed as pz
from pyzed import _core, icons, ui
from pyzed.designer.app import Designer


def test_icons_are_found_by_name_and_tag():
    assert icons.search("user")[0] == "user"
    assert "user" in icons.search("person")  # by tag
    assert icons.search("arrow up")[0] == "arrow-up"
    assert icons.search("ARROW-UP")[0] == "arrow-up"
    assert icons.search("zzzz-not-an-icon") == []
    assert icons.search("") == icons.names()
    assert "person" in icons.tags("user") and icons.tags("not-an-icon") == []


def test_icons_are_grouped_in_categories():
    arrows = icons.category("arrows")
    assert "arrow-up" in arrows and "chevron-down" in arrows and "user" not in arrows
    assert "user" in icons.category("people")
    for key in icons.CATEGORIES:
        assert icons.category(key), key
        assert pz.t(f"pyzed.icons.categories.{key}") != f"pyzed.icons.categories.{key}"
    assert all(name in arrows for name in icons.search("up", arrows))


def test_the_picker_filters_and_emits_the_picked_icon():
    got = []
    picker = ui.IconPicker.create(value="house", clearable=True, on_change=lambda e: got.append(e.value))
    picker.set_query("arrow up")
    assert picker.matches()[0] == "arrow-up"
    assert isinstance(picker.render(), pz.Widget)
    picker.pick("arrow-up")
    assert got == ["arrow-up"] and picker.value == "arrow-up"
    picker.set_query("")
    picker.set_group("people")
    assert "user" in picker.matches() and "arrow-up" not in picker.matches()
    picker.set_group("not-a-category")
    assert picker.group == ""
    picker.set_query("zzzz-not-an-icon")
    assert picker.matches() == [] and isinstance(picker.render(), pz.Widget)  # "No icon matches"
    picker.pick("")
    assert got[-1] == ""


def test_the_picker_scrolls_to_the_picked_icon_and_focuses_its_search():
    assert ui.IconPicker.create(value="").on_mount() is None
    assert isinstance(ui.IconPicker.create(value="zap").on_mount(), _core.Command)
    assert isinstance(ui.IconPicker.create(value="", autofocus=True).on_mount(), _core.Command)


def test_the_picker_renders_and_reports_no_matches(tmp_path):
    class Empty(pz.App):
        def view(self):
            return ui.icon_picker_dialog("user", lambda name: None, on_close=lambda: None)

    pz.screenshot(Empty(), tmp_path / "picker.png", size=(420, 460))
    assert (tmp_path / "picker.png").stat().st_size > 0
    grid = ui.icon_grid(["user", "house", "star"], lambda name: None, selected="star", columns=2)
    assert grid is not None


def test_the_designer_picks_icons_from_the_dialog():
    app = Designer(language_servers=False)
    app.doc.add("button", 10, 10)
    app.doc.select("button1")
    app.view()  # the Properties panel shows the icon editor
    picked = []
    app.open_icon_picker("house", picked.append)
    assert app.dialog == "icon_picker"
    assert app.dialog_view(app.theme_obj) is not None
    app.pick_icon("star")
    assert picked == ["star"] and app.dialog is None and app.icon_pick is None
    app.pick_icon("x")  # nothing waiting: ignored
    assert picked == ["star"]


def test_the_button_icon_property_opens_the_dialog():
    from pyzed.designer import components, panels

    app = Designer(language_servers=False)
    app.doc.add("button", 10, 10)
    app.doc.select("button1")
    prop = next(p for p in components.get("button").props if p.kind == "icon")
    editor = panels.editor_for(app, prop, "house", lambda v: app.doc.set_prop("button1", prop.name, v),
                               "button1.icon", app.theme_obj)
    assert isinstance(editor, pz.Widget)
    app.open_icon_picker("house", lambda v: app.doc.set_prop("button1", prop.name, v))
    app.pick_icon("rocket")
    assert app.doc.form["button1"].props[prop.name] == "rocket"
