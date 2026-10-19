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


def _png_column(path, x):
    """The RGB colors down column ``x`` of an 8-bit RGB/RGBA PNG (no Pillow in CI)."""
    import struct
    import zlib

    data = path.read_bytes()
    pos, idat, width, channels = 8, b"", 0, 4
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width = struct.unpack(">I", chunk[:4])[0]
            channels = {2: 3, 6: 4}[chunk[9]]
        elif kind == b"IDAT":
            idat += chunk
        pos += 12 + length
    raw, stride = zlib.decompress(idat), width * channels
    prev, column = bytearray(stride), []
    for row in range(len(raw) // (stride + 1)):
        kind, line = raw[row * (stride + 1)], bytearray(raw[row * (stride + 1) + 1:(row + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - channels] if i >= channels else 0
            b, c = prev[i], prev[i - channels] if i >= channels else 0
            if kind == 1:
                line[i] = (line[i] + a) & 255
            elif kind == 2:
                line[i] = (line[i] + b) & 255
            elif kind == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        column.append(tuple(line[x * channels:x * channels + 3]))
        prev = line
    return column


@pytest.mark.parametrize("options", [{"columns": 2}, {"max_width": 200}])
def test_uniform_grid_height_is_each_rows_height(tmp_path, options):
    class Demo(pz.App):
        def view(self):
            cells = [pz.container(None, bg="#ff0000", width="fill", height="fill") for _ in range(4)]
            return pz.container(pz.grid(cells, height=40, **options), bg="#000000", width="fill", height="fill")

    out = tmp_path / "grid.png"
    pz.screenshot(Demo, out, size=(400, 200), scale=1)
    reds = [y for y, (r, g, b) in enumerate(_png_column(out, 10)) if r > 200 and g < 50]
    assert (reds[0], reds[-1]) == (0, 79)  # two rows of 40 px, not 200 px split in two
