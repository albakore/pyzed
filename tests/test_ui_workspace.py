"""The editor chrome in ``pyzed.ui.workspace``: title bar, panels, status bar and the workspace layout."""

import importlib

import pytest

import pyzed as pz
from pyzed import ui
from ui_tree import Node, install

ws = importlib.import_module("pyzed.ui.workspace")  # pyzed.ui.workspace is also a function

DARK, LIGHT = pz.themes.ONE_DARK, pz.themes.ONE_LIGHT


@pytest.fixture
def tree(monkeypatch):
    return install(monkeypatch)


def test_title_bar_puts_start_left_and_end_right(tree):
    bar = ws.title_bar(["start"], ["end"], height=40, theme=DARK)
    body = bar.find("container")
    assert body.props["height"] == 39 and body.props["bg"] == DARK.title_bar  # the 1px border is the rest
    items = body.args[0].args[0]
    assert items[0] == "start" and items[-1] == "end"
    assert [n.props.get("width") for n in items[1:-1]] == ["fill"]
    assert bar.find("rule").props["color"] == DARK.border


def test_title_bar_centers_the_middle_item(tree):
    items = ws.title_bar(["a"], ["b"], center="title").find("row").args[0]
    assert items[2] == "title"
    assert items[1].kind == items[3].kind == "space"


def test_title_button_mutes_and_shows_a_chevron(tree):
    plain = ws.title_button("pyzed", "msg", theme=DARK)
    assert plain.args[1] == "msg"
    text = plain.find("text", lambda n: n.args[0] == "pyzed")
    assert text.props["color"] == DARK.text and text.props["weight"] == "medium"

    muted = ws.title_button("main", icon="git-branch", muted=True, chevron=True, theme=DARK)
    text = muted.find("text", lambda n: n.args[0] == "main")
    assert text.props["color"] == DARK.text_muted and text.props["weight"] is None
    assert len(muted.find_all("text", lambda n: n.props.get("font") == "icons")) == 2  # branch icon + chevron


def test_status_bar_and_items(tree):
    bar = ws.status_bar(["left"], ["right"], height=30, theme=LIGHT)
    body = bar.find("container")
    assert body.props["height"] == 29 and body.props["bg"] == LIGHT.status_bar
    assert body.args[0].args[0][0] == "left" and body.args[0].args[0][-1] == "right"

    item = ws.status_item("Ln 4, Col 2", "goto", theme=DARK)
    assert item.kind == "button" and item.args[1] == "goto"
    assert item.props["bg"] == "transparent"
    assert item.texts() == ["Ln 4, Col 2"]

    selected = ws.status_item(icon="git-branch", selected=True, color="error", theme=DARK)
    assert selected.props["bg"] == DARK.ghost_selected
    assert selected.find("text").props["color"] == DARK.icon  # selected icons are not muted
    assert ws.status_item("x", color="error", theme=DARK).find("text").props["color"] == DARK.error


def test_status_item_tooltip_shows_the_keys(tree):
    item = ws.status_item(icon="terminal", tooltip="Toggle terminal", keys="ctrl-`", theme=DARK)
    assert item.kind == "tooltip" and item.props["position"] == "top"
    assert "Toggle terminal" in item.texts()


def test_panel_header(tree):
    header = ws.panel_header("Project", ["action"], icon="folder", theme=DARK)
    row = header.find("row")
    assert row.args[0][-1] == "action"
    assert "Project" in header.texts()
    assert header.props["height"] == 32


@pytest.mark.parametrize("side, edge, size_key", [("left", "right", "width"), ("right", "left", "width"),
                                                   ("bottom", "top", "height")])
def test_numeric_panels_resize_from_their_inner_edge(tree, side, edge, size_key):
    calls = []
    widget = ws.panel("content", side=side, on_resize=calls.append, min_size=90, theme=DARK, **{size_key: 250})
    assert widget.kind == "resizable"
    assert widget.props["edge"] == edge == ws.INNER_EDGES[side]
    assert widget.props["size"] == 250 and widget.props["min_size"] == 90
    assert widget.props["color"] == DARK.border and widget.props["hover_color"] == DARK.accent
    widget.props["on_resize"](300)
    assert calls == [300]
    assert widget.find("container").props["bg"] == DARK.panel


@pytest.mark.parametrize("side, layout, edge_first", [("left", "row", False), ("right", "row", True),
                                                      ("bottom", "column", True)])
def test_fixed_panels_draw_a_border_on_the_inner_side(tree, side, layout, edge_first):
    widget = ws.panel("content", side=side, width=200, resizable=False, theme=DARK)
    assert widget.kind == layout
    parts = widget.args[0]
    edge = parts[0] if edge_first else parts[1]
    assert edge.kind == "rule" and edge.props["vertical"] is (side != "bottom")


def test_panels_with_relative_sizes_are_not_resizable(tree):
    assert ws.panel("content", side="left", width="fill").kind == "row"


def test_workspace_hides_missing_docks(tree):
    layout = ws.workspace("editor", theme=DARK)
    assert layout.find_all("resizable") == []
    assert layout.props["bg"] == DARK.background and layout.props["color"] == DARK.text
    center = layout.find("container", lambda n: n.args and n.args[0] == "editor")
    assert center.props["bg"] == DARK.editor


def test_workspace_places_docks_and_reports_resizes(tree):
    calls = []
    layout = ws.workspace(
        "editor",
        title_bar="title",
        status_bar="status",
        left="tree",
        right="assistant",
        bottom="terminal",
        left_width=200,
        right_width=300,
        bottom_height=150,
        on_resize=lambda side, size: calls.append((side, size)),
        theme=DARK,
    )
    column = layout.args[0]
    assert column.args[0][0] == "title" and column.args[0][-1] == "status"
    docks = {n.props["edge"]: n for n in layout.find_all("resizable")}
    assert {edge: n.props["size"] for edge, n in docks.items()} == {"right": 200, "left": 300, "top": 150}
    assert docks["top"].props["min_size"] == 80
    for edge, size in (("right", 210), ("left", 310), ("top", 160)):
        docks[edge].props["on_resize"](size)
    assert calls == [("left", 210), ("right", 310), ("bottom", 160)]


def test_workspace_without_on_resize(tree):
    layout = ws.workspace("editor", left="tree")
    assert layout.find("resizable").props["on_resize"] is None


def test_workspace_is_exported_from_ui():
    assert ui.workspace is ws.workspace and ui.status_bar is ws.status_bar


def test_workspace_renders(tmp_path):
    class Demo(pz.App):
        size = (480, 300)

        def view(self):
            return ui.workspace(
                ui.label("center"),
                title_bar=ui.title_bar([ui.title_button("pyzed", chevron=True)]),
                left=ui.panel_header("Project"),
                bottom=ui.label("terminal"),
                status_bar=ui.status_bar([ui.status_item("main", icon="git-branch")]),
            )

    out = tmp_path / "workspace.png"
    Demo().screenshot(out, scale=1)
    assert out.stat().st_size > 0


def test_node_helpers():
    node = Node("row", ([Node("text", ("a",), {}), Node("button", (Node("text", ("b",), {}), "msg"), {})],), {})
    assert node.texts() == ["a", "b"]
    assert node.button_with("b").args[1] == "msg"
