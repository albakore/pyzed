"""States and events of buttons, badges, avatars, lists, trees, menus, tabs and breadcrumbs."""

import pytest

import pyzed as pz
from pyzed import ui
from ui_tree import install

T = pz.themes.ONE_DARK


@pytest.fixture
def tree(monkeypatch):
    return install(monkeypatch)


def test_button_loading_and_tooltip(tree):
    loading = ui.button("Save", print, icon="save", loading=True, theme=T)
    assert loading.args[1] is None  # ignores presses
    assert loading.find("canvas")  # the spinner replaces the icon
    tipped = ui.button("Save", print, tooltip="Saves the file", theme=T)
    assert tipped.kind == "tooltip" and "Saves the file" in tipped.texts()


def test_icon_button_tint_keys_loading_indicator(tree):
    tinted = ui.icon_button("trash", print, tint="error", tooltip="Delete", keys="ctrl-d", theme=T)
    assert tinted.kind == "tooltip"
    assert tinted.find("button").props["color"] == T.error
    assert "D" in tinted.texts()  # the key cap
    dot = ui.icon_button("bell", print, indicator="error", theme=T)
    assert any(n.props.get("bg") == T.error for n in dot.find_all("container"))
    assert ui.icon_button("x", print, loading=True, theme=T).args[1] is None


def test_badge_sizes_and_press(tree):
    small = ui.badge("new", size="sm", theme=T)
    assert small.props["padding"] == (0, 5)
    pressed = ui.badge("3", on_press=print, theme=T)
    assert pressed.kind == "events" and pressed.props["click"] is print


def test_avatar_image_status_and_tooltip(tree):
    face = ui.avatar("KK", image="me.png", status="online", tooltip="Kev", size=30, theme=T)
    assert face.kind == "tooltip"
    assert face.find("image").args[0] == "me.png"
    assert any(n.props.get("bg") == T.success for n in face.find_all("container"))


def test_divider_label_and_spacing(tree):
    line = ui.divider(label="or", spacing=8, theme=T)
    assert line.kind == "container" and line.props["padding"] == (8, 0)
    assert line.texts() == ["or"]


def test_list_item_description_double_press_tooltip(tree):
    opened = []
    item = ui.list_item("main.py", print, description="src", on_double_press=lambda: opened.append(1),
                        tooltip="Open main.py", theme=T)
    assert item.kind == "tooltip"
    events = item.find("events")
    events.props["double_click"]()
    assert opened == [1]
    assert events.find("button").props["height"] == 40 and "src" in item.texts()


def test_tree_multi_select_open_and_context(tree):
    got = []
    nodes = ui.TreeNode.from_paths(["src/a.py", "src/b.py"])
    widget = ui.tree(nodes, expanded={"src"}, selected={"src/a.py", "src/b.py"}, focused="src/a.py",
                     on_open=lambda i: got.append(("open", i)), on_context=lambda i: got.append(("menu", i)), theme=T)
    buttons = widget.find_all("button")
    assert [b.props["bg"] for b in buttons[1:]] == [T.ghost_selected] * 2
    assert buttons[1].props["border_color"] == T.border_focused
    widget.find_all("events")[0].props["double_click"]()
    widget.find_all("mouse_area")[0].props["on_right_press"]()
    assert ("open", "src/a.py") in got and ("menu", "src") in got


def test_menu_description_submenu_and_scroll(tree):
    widget = ui.menu([ui.MenuItem("Share", print, submenu=True), ui.MenuItem("Rename", description="F2")],
                     max_height=120, theme=T)
    assert widget.find("scrollable")
    assert "F2" in widget.texts()


def test_tabs_pinned_tooltip_middle_click_context_new(tree):
    got = []
    tabs = [ui.Tab("a", "a.py"), ui.Tab("b", "b.py", icon="file", pinned=True, tooltip="src/b.py")]
    bar = ui.tab_bar(tabs, "a", on_close=lambda i: got.append(("close", i)),
                     on_context=lambda i: got.append(("menu", i)), on_new=lambda: got.append("new"), theme=T)
    events = bar.find_all("events")
    assert "src/b.py" in bar.texts() and bar.texts().index("src/b.py") < bar.texts().index("a.py")  # pinned first
    tab_events = [e for e in events if "right_click" in e.props]
    tab_events[0].props["right_click"]()
    middle = [e for e in events if e.props.get("middle_click")]
    assert len(middle) == 1  # only the closable tab
    middle[0].props["middle_click"]()
    [e for e in events if e.props.get("double_click")][0].props["double_click"]()
    assert got == [("menu", "b"), ("close", "a"), "new"]


def test_breadcrumbs_collapse(tree):
    pressed = []
    crumbs = ui.breadcrumbs(["a", "b", "c", "d", "e"], max_items=3, on_press=pressed.append, on_more=print, theme=T)
    assert [x for x in crumbs.texts() if x != "›"] == ["a", "…", "d", "e"]
    crumbs.button_with("d").args[1]()
    assert pressed == [3]


def test_toolbar_center(tree):
    bar = ui.toolbar([ui.label("left", theme=T)], [], center=ui.label("middle", theme=T), theme=T)
    assert bar.find("stack") and bar.texts() == ["left", "middle"]


def test_render_for_real():
    widgets = [ui.button("x", print, loading=True, tooltip="t"), ui.icon_button("bell", print, indicator="error"),
               ui.avatar("KK", status="away"), ui.divider(label="or"), ui.menu([ui.MenuItem("a")], max_height=50),
               ui.tab_bar([ui.Tab("a", "a", pinned=True)], "a", on_new=print, on_context=print),
               ui.breadcrumbs(["a", "b", "c"], max_items=2), ui.toolbar(center=ui.label("x"))]
    assert all(isinstance(w, pz.Widget) for w in widgets)
