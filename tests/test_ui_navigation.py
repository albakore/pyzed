"""Tabs, breadcrumbs and toolbars in ``pyzed.ui.navigation``."""

import pytest

import pyzed as pz
from pyzed import ui
from pyzed.icons import for_file
from pyzed.ui import navigation as nav
from ui_tree import install

DARK = pz.themes.ONE_DARK


@pytest.fixture
def tree(monkeypatch):
    return install(monkeypatch)


def test_tab_for_file_uses_the_name_and_file_icon():
    tab = nav.Tab.for_file("src/app/main.rs", dirty=True)
    icon, color = for_file("main.rs")
    assert (tab.id, tab.label, tab.icon, tab.icon_color, tab.dirty) == ("src/app/main.rs", "main.rs", icon, color, True)
    assert nav.Tab.for_file("README.md", icon="book").icon == "book"


def _label(widget, text):
    return widget.find("text", lambda n: n.args[0] == text)


def test_active_tab_joins_the_content_below(tree):
    tab = nav.tab(nav.Tab("a", "a.py"), active=True, on_select="select", on_close="close", theme=DARK)
    body = tab.find("button")
    assert body.args[1] == "select"
    assert body.props["bg"] == DARK.tab_active
    assert _label(tab, "a.py").props["color"] == DARK.text
    lines = [n for n in tab.find_all("rule") if not n.props.get("vertical")]
    assert lines[0].props["color"] == DARK.tab_active  # no border under the active tab
    assert tab.find_all("hover") == []  # the close button is always visible


def test_inactive_tab_shows_close_on_hover(tree):
    tab = nav.tab(nav.Tab("a", "a.py", preview=True), active=False, on_close="close", theme=DARK)
    assert tab.find("button").props["bg"] == DARK.tab_inactive
    label = _label(tab, "a.py")
    assert label.props["color"] == DARK.text_muted and label.props["italic"] is True
    hover = tab.find("hover")
    assert hover.args[1].kind == "button" and hover.args[1].args[1] == "close"
    lines = [n for n in tab.find_all("rule") if not n.props.get("vertical")]
    assert lines[0].props["color"] == DARK.border


def test_dirty_tab_shows_a_dot(tree):
    clean = nav.tab(nav.Tab("a", "a.py"), active=False, theme=DARK)
    dirty = nav.tab(nav.Tab("a", "a.py", dirty=True), active=False, theme=DARK)
    assert len(dirty.find_all("container")) > len(clean.find_all("container"))
    assert clean.find("hover").args[1].kind == "space"  # no close button without on_close


@pytest.mark.parametrize("status, token", [("modified", "modified"), ("created", "created"), ("deleted", "deleted")])
def test_tab_label_follows_the_git_status(tree, status, token):
    tab = nav.tab(nav.Tab("a", "a.py", status=status), active=True, theme=DARK)
    assert _label(tab, "a.py").props["color"] == getattr(DARK, token)


def test_tab_bar_wires_select_and_close_by_id(tree):
    selected, closed = [], []
    tabs = [nav.Tab("one", "one.py"), nav.Tab("two", "two.py")]
    bar = nav.tab_bar(tabs, "two", on_select=selected.append, on_close=closed.append, start=["back"], end=["split"],
                      height=30, theme=DARK)
    assert bar.props["bg"] == DARK.tab_bar and bar.props["height"] == 30
    assert bar.args[0].props["clip"] is True
    bar.button_with("one.py").args[1]()
    bar.button_with("two.py").args[1]()
    assert selected == ["one", "two"]
    for button in bar.find_all("button", lambda n: n.args[1] is not None and n.args[0].kind == "container"
                               and n.args[0].props.get("center")):
        button.args[1]()
    assert sorted(closed) == ["one", "two"]
    texts = bar.texts()
    assert texts.index("one.py") < texts.index("two.py")
    assert bar.find("row", lambda n: n.args[0] == ["back"]) and bar.find("row", lambda n: n.args[0] == ["split"])


def test_tab_bar_without_callbacks_or_start(tree):
    bar = nav.tab_bar([nav.Tab("one", "one.py")], None)
    assert bar.button_with("one.py").args[1] is None
    assert bar.args[0].args[0][0].kind == "row"  # the first item is the tab, no start group


def test_breadcrumbs(tree):
    crumbs = nav.breadcrumbs(["src", ("file-code", "main.rs"), "fn main"], theme=DARK)
    assert {"src", "main.rs", "fn main"} <= set(crumbs.texts())
    separators = crumbs.find_all("text", lambda n: n.args[0] == "›")
    assert len(separators) == 2 and separators[0].props["color"] == DARK.text_placeholder
    assert _label(crumbs, "fn main").props["color"] == DARK.text  # the last part stands out
    assert _label(crumbs, "src").props["color"] == DARK.text_muted
    assert crumbs.find_all("button") == []


def test_breadcrumbs_report_the_pressed_index(tree):
    pressed = []
    crumbs = nav.breadcrumbs(["a", "b", "c"], separator="/", on_press=pressed.append)
    for text in ("c", "a"):
        crumbs.button_with(text).args[1]()
    assert pressed == [2, 0]
    assert len(crumbs.find_all("text", lambda n: n.args[0] == "/")) == 2


def test_toolbar(tree):
    bar = nav.toolbar(["crumbs"], ["action"], height=28, theme=DARK)
    items = bar.args[0].args[0]
    assert items[0] == "crumbs" and items[-1] == "action" and items[1].kind == "space"
    assert bar.props["bg"] == DARK.editor and bar.props["height"] == 28


def test_navigation_is_exported_from_ui():
    assert ui.Tab is nav.Tab and ui.tab_bar is nav.tab_bar and ui.breadcrumbs is nav.breadcrumbs
