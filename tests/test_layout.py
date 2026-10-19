"""Track grids, flex, resizable panels and the dock."""

import pytest

import pyzed as pz
from pyzed import ui


def test_grid_with_int_columns_keeps_the_uniform_grid():
    assert repr(pz.grid(["a", "b"], columns=2)) == "<Widget grid>"
    with pytest.raises(ValueError, match="columns= or max_width="):
        pz.grid(["a"])


def test_track_grid_from_lists_strings_and_cells():
    assert repr(pz.grid(["a", "b"], columns=[120, "1fr", "auto"])) == "<Widget grid [2]>"
    assert repr(pz.grid(["a"], columns="120 2fr auto", rows=[40])) == "<Widget grid [1]>"
    # A cell anywhere switches an int-column grid to tracks too.
    assert repr(pz.grid([pz.cell("a", column=1)], columns=2)) == "<Widget grid [1]>"
    with pytest.raises(ValueError, match="invalid grid track"):
        pz.grid(["a"], columns=["wide"])
    with pytest.raises(ValueError, match="only work with columns=<int>"):
        pz.grid(["a"], columns=["1fr"], max_width=100)


def test_cell_outside_a_grid_is_its_child():
    assert repr(pz.cell(pz.text("hi"), column=0, row=1, column_span=2)) == '<Widget cell <Widget text "hi">>'
    with pytest.raises(ValueError, match="invalid alignment"):
        pz.cell("a", align_x="middle")


def test_resizable_checks_the_edge():
    assert repr(pz.resizable("panel", edge="bottom", size=200, max_size=400)) == "<Widget resizable>"
    with pytest.raises(ValueError, match="invalid edge"):
        pz.resizable("panel", edge="inside")


def test_flex_inserts_spacers_for_justify():
    assert repr(pz.flex(["a", "b", "c"])) == "<Widget row [3]>"
    assert repr(pz.flex(["a", "b", "c"], justify="between")) == "<Widget row [5]>"  # a _ b _ c
    assert repr(pz.flex(["a", "b"], justify="around", gap=4)) == "<Widget row [6]>"  # _ a gap _ b _
    assert repr(pz.flex(["a", "b"], direction="column", justify="end")) == "<Widget column [3]>"
    # Growing items take the free space, so justify adds nothing.
    assert repr(pz.flex([pz.flex_item("a"), "b"], justify="center")) == "<Widget row [2]>"


def test_flex_rejects_bad_options():
    with pytest.raises(ValueError, match="direction"):
        pz.flex([], direction="diagonal")
    with pytest.raises(ValueError, match="justify"):
        pz.flex([], justify="spread")
    with pytest.raises(ValueError, match="only works with direction='row'"):
        pz.flex([], direction="column", wrap=True)
    with pytest.raises(ValueError, match="justify='start'"):
        pz.flex([], wrap=True, justify="center")
    with pytest.raises(ValueError, match="grow"):
        pz.flex_item("a", grow=-1)


def test_layouts_render_off_screen(tmp_path):
    class Demo(pz.App):
        def view(self):
            return pz.column([
                pz.grid([pz.cell("header", column=0, row=0, column_span=2), "a", "b", pz.cell("c", align_x="center")],
                        columns=[100, "1fr"], rows=[30, "auto", "1fr"], spacing=6, height=200),
                pz.flex([pz.flex_item("grow", grow=2), "fixed", pz.flex_item("basis", basis=80)], gap=4),
                pz.flex(["x", "y"], justify="evenly", align="center"),
                pz.row([pz.resizable("left", size=120), pz.space(width="fill"), pz.resizable("right", edge="left")],
                       height=100),
            ])

    out = tmp_path / "layout.png"
    pz.screenshot(Demo, out, size=(500, 400), scale=1)
    assert out.stat().st_size > 0


def test_workspace_docks_are_resizable():
    sizes = []
    layout = ui.workspace("center", left="files", bottom="terminal", on_resize=lambda side, s: sizes.append((side, s)))
    assert "container" in repr(layout)
    assert repr(ui.panel("files", width=200)) == "<Widget resizable>"
    assert repr(ui.panel("files", width=200, resizable=False)).startswith("<Widget row")


def panels():
    return [
        pz.DockPanel("project", "Project", "files", side="left"),
        pz.DockPanel("outline", "Outline", "symbols", side="left"),
        pz.DockPanel("terminal", "Terminal", "shell", side="bottom"),
    ]


def test_dock_moves_panels_and_reports_the_layout():
    seen = []
    dock = pz.Dock.create(center="editor", panels=panels(), on_layout=lambda e: seen.append(e.value))
    assert {s: [p.id for p in ps] for s, ps in dock.groups().items()} == {
        "left": ["project", "outline"], "right": [], "bottom": ["terminal"], "top": []}
    dock.move("outline", "right")
    assert [p.id for p in dock.groups()["right"]] == ["outline"]
    assert seen[-1]["positions"] == {"outline": "right"} and seen[-1]["active"]["right"] == "outline"
    dock.resized("left", 300)
    assert seen[-1]["sizes"]["left"] == 300
    dock.toggle("bottom")
    assert seen[-1]["hidden"] == ["bottom"]
    with pytest.raises(ValueError):
        dock.move("outline", "middle")


def test_dock_drop_works_after_the_drag_ended():
    dock = pz.Dock.create(center="editor", panels=panels())
    dock.start_drag("terminal")
    dock.end_drag()  # the tab's drag_end can arrive before the zone's mouse_up
    dock.drop("top")
    assert dock.side_of(panels()[2]) == "top" and dock.dragging is None
    assert dock.drop("left") is None  # nothing is being dragged any more


def test_dock_restores_a_saved_layout():
    saved = {"positions": {"project": "right"}, "sizes": {"right": 400}, "active": {}, "hidden": []}
    dock = pz.Dock.create(center="editor", panels=panels(), layout=saved)
    assert [p.id for p in dock.groups()["right"]] == ["project"]
    assert dock.sizes["right"] == 400
    assert "stack" in repr(dock.render())


def test_dock_panel_checks_the_side():
    with pytest.raises(ValueError, match="side"):
        pz.DockPanel("x", "X", "content", side="middle")
