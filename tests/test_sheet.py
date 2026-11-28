"""pz.Workbook (the spreadsheet engine), pz.sheet (the grid) and ui.Spreadsheet."""

import datetime as dt
import sys

import pytest

import pyzed as pz
from pyzed import _core, ui


#: The modifier of the grid's shortcuts: Cmd on macOS, Ctrl elsewhere.
CMD = "cmd" if sys.platform == "darwin" else "ctrl"


def book_with(rows, at="A1"):
    b = pz.Workbook()
    b.write(rows, at=at)
    return b


# --- Values and formulas ----------------------------------------------------------------


def test_values_and_formulas_recalculate():
    b = pz.Workbook()
    b["A1"] = 2
    b["A2"] = 3
    b["A3"] = "=A1*A2+1"
    assert b["A3"] == 7
    b["A1"] = 10
    assert b["A3"] == 31
    assert b.formula("A3") == "=A1*A2+1"
    assert b.text("A3") == "31"


def test_typed_text_is_parsed_like_a_spreadsheet():
    b = pz.Workbook()
    b["A1"] = "42"
    b["A2"] = "12.5%"
    b["A3"] = "TRUE"
    b["A4"] = "$1,200.50"
    b["A5"] = "2026-03-04"
    assert b["A1"] == 42
    assert b["A2"] == pytest.approx(0.125)
    assert b["A3"] is True
    assert b["A4"] == pytest.approx(1200.5)
    assert b["A5"] == dt.date(2026, 3, 4)
    assert b.text("A2") == "12.50%"
    assert b.text("A5") == "2026-03-04"


@pytest.mark.parametrize(
    "formula, expected",
    [
        ("=SUM(A1:A4)", 10),
        ("=AVERAGE(A1:A4)", 2.5),
        ("=COUNTIF(A1:A4, \">2\")", 2),
        ("=SUMIFS(A1:A4, B1:B4, \"x\")", 4),
        ("=IF(A1>0, \"pos\", \"neg\")", "pos"),
        ("=VLOOKUP(3, A1:B4, 2, FALSE)", "x"),
        ("=XLOOKUP(\"y\", B1:B4, A1:A4)", 2),
        ("=INDEX(A1:A4, MATCH(4, A1:A4, 0))", 4),
        ("=TEXTJOIN(\"-\", TRUE, B1:B4)", "x-y-x-y"),
        ("=UPPER(LEFT(\"hello\", 2)) & \"!\"", "HE!"),
        ("=ROUND(PI(), 2)", 3.14),
        ("=IFERROR(1/0, \"oops\")", "oops"),
        ("=DATEDIF(DATE(2020,1,1), DATE(2021,3,1), \"m\")", 14),
        ("=SUMPRODUCT(A1:A4, A1:A4)", 30),
        ("=MAX(A:A)", 4),
    ],
)
def test_functions(formula, expected):
    b = book_with([[1, "x"], [2, "y"], [3, "x"], [4, "y"]])
    b["D1"] = formula
    assert b["D1"] == (pytest.approx(expected) if isinstance(expected, float) else expected)


def test_errors_and_cycles():
    b = pz.Workbook()
    b["A1"] = "=1/0"
    b["A2"] = "=A3"
    b["A3"] = "=A2"
    b["A4"] = "=NOPE(1)"
    assert b.text("A1") == "#DIV/0!"
    assert b.text("A2") == "#CYCLE!"
    assert b.text("A4") == "#NAME?"


def test_dynamic_arrays_spill():
    b = pz.Workbook()
    b["A1"] = "=SEQUENCE(3)"
    assert [b["A1"], b["A2"], b["A3"]] == [1, 2, 3]
    b["A2"] = "block"
    assert b.text("A1") == "#SPILL!"


def test_cross_sheet_references_and_rename():
    b = pz.Workbook(sheets=["Data", "Report"])
    b["Data!A1"] = 5
    b["Report!A1"] = "=Data!A1*2"
    assert b["Report!A1"] == 10
    b.rename_sheet("Data", "Raw data")
    assert b.formula("Report!A1") == "='Raw data'!A1*2"
    assert b["Report!A1"] == 10


# --- Structure -----------------------------------------------------------------------------


def test_insert_and_delete_rows_move_references():
    b = book_with([[1], [2], [3]])
    b["B1"] = "=SUM(A1:A3)"
    b.insert_rows(2)
    assert b.formula("B1") == "=SUM(A1:A4)"
    b["A2"] = 10
    assert b["B1"] == 16
    b.delete_rows(1)
    assert b.formula("A1") is None or b["A1"] == 10
    b2 = book_with([[1, "=A1"]])
    b2.delete_cols("A")
    assert b2.text("A1") == "#REF!"


def test_undo_and_redo():
    b = pz.Workbook()
    b["A1"] = 1
    b["A1"] = 2
    b.format("A1", bold=True)
    assert b.undo() and b.style("A1") == {}
    assert b.undo() and b["A1"] == 1
    assert b.redo() and b["A1"] == 2
    b.batch(lambda: (b.set("B1", 1), b.set("B2", 2)))
    b.undo()
    assert b["B1"] is None and b["B2"] is None


def test_merge_freeze_sizes():
    b = pz.Workbook()
    b["A1"] = "Title"
    b.merge("A1:C1")
    assert b.merges() == ["A1:C1"]
    b.freeze(rows=1, cols=2)
    assert b.frozen == (1, 2)
    b.column_width("B", 140)
    assert b.column_width("B") == 140


def test_sort_and_filter():
    b = book_with([["Name", "Units"], ["b", 3], ["a", 1], ["c", 2]])
    b.sort("A1:B4", "B", header=True)
    assert b.values("A2:A4") == [["a"], ["c"], ["b"]]
    b.filter("A1:B4")
    b.filter_column("B", condition=">1")
    assert b.filtered_rows == [2]
    b.filter_column("B", condition=None, hide=["3"])
    assert 4 in b.filtered_rows


def test_fill_series_and_copy_paste():
    b = book_with([[1], [2]])
    b.fill("A1:A2", "A1:A5")
    assert [b[f"A{i}"] for i in range(1, 6)] == [1, 2, 3, 4, 5]
    b["B1"] = "Mon"
    b.fill("B1", "B1:B3")
    assert b["B3"] == "Wed"
    b["C1"] = "=A1*2"
    text = b.copy("C1")
    b.paste(text, "C2")
    assert b.formula("C2") == "=A2*2"
    b.paste("x\ty\n1\t2", "E1")
    assert b.values("E1:F2") == [["x", "y"], [1, 2]]


def test_find_and_replace():
    b = book_with([["apple", "pear"], ["Apple pie", "plum"]])
    assert b.find("apple") == ["A1", "A2"]
    assert b.find("apple", match_case=True) == ["A1"]
    assert b.find("apple", whole_cell=True) == ["A1"]
    assert b.replace("p", "P", match_case=True) >= 3
    assert b["B2"] == "Plum"


def test_validation_and_conditional_formats():
    b = pz.Workbook()
    b.validate("A1:A5", options=["Yes", "No"])
    assert b.options("A1") == ["Yes", "No"]
    b["A1"] = "Maybe"
    assert not b.is_valid("A1")
    b.conditional_format("B1:B3", ">", 5, fill="#ff0000")
    b.conditional_format("C1:C3", "bar")
    assert len(b.conditional_formats()) == 2


def test_stats_of_a_range():
    b = book_with([[1, 2, "x"], [3, None, 4]])
    s = b.stats("A1:C2")
    assert s["sum"] == 10 and s["count"] == 5 and s["numbers"] == 4 and s["max"] == 4


# --- Files ------------------------------------------------------------------------------------


def test_csv_round_trip():
    b = pz.Workbook.from_csv('a,b\n1,"x, y"\n')
    assert b.values() == [["a", "b"], [1, "x, y"]]
    assert b.to_csv().splitlines()[1] == '1,"x, y"'


def test_xlsx_round_trip(tmp_path):
    b = book_with([["Item", "Price"], ["Tea", 2.5], ["Cake", 4]])
    b["B4"] = "=SUM(B2:B3)"
    b.format("B2:B4", number_format="$#,##0.00", bold=True)
    b.merge("A6:B6")
    b.freeze(rows=1)
    path = tmp_path / "book.xlsx"
    b.save(path)
    c = pz.Workbook.open(path)
    assert c["B4"] == 6.5
    assert c.formula("B4") == "=SUM(B2:B3)"
    assert c.text("B2") == "$2.50"
    assert c.merges() == ["A6:B6"]


def test_xlsx_keeps_layout_and_validation(tmp_path):
    b = book_with([["Region", "Units", "Done"], ["North", 3, True], ["South", 4, False]])
    b.column_width("A", 140)
    b.row_height(1, 32)
    b.hide_cols(["D"])
    b.freeze(rows=1, cols=1)
    b.filter("A1:C3")
    b.gridlines = False
    b.tab_color(0, "#34a853")
    b.validate("A2:A3", options=["North", "South"])
    b.validate("B2:B3", number=(0, 10), integer=True)
    b.validate("C2:C3", checkbox=True)
    path = tmp_path / "layout.xlsx"
    b.save(path)
    c = pz.Workbook.open(path)
    assert c.column_width("A") == 140
    assert c.row_height(1) == 32
    assert c.frozen == (1, 1)
    assert c.filter_range == "A1:C3"
    assert c.gridlines is False
    assert c.tab_color(0) == "#34a853"
    assert c.options("A2") == ["North", "South"]
    c["B2"] = 50
    assert not c.is_valid("B2")


def test_typed_formulas_are_normalized():
    b = pz.Workbook()
    b["B1"], b["B2"] = 2, 3
    b["A1"] = "=sum(b1:b2)"
    b["A2"] = "=-b1"
    b["A3"] = "=if(true, 1, 0)"
    assert b.formula("A1") == "=SUM(B1:B2)" and b["A1"] == 5
    assert b["A2"] == -2
    assert b.formula("A3") == "=IF(TRUE, 1, 0)" and b["A3"] == 1


def test_sorting_a_cell_sorts_its_block_and_keeps_the_header():
    import types

    from pyzed.ui.sheet import Spreadsheet

    b = book_with([["Name", "Units"], ["Pears", 4], ["Apples", 9], ["Plums", 1], [None, None], ["Total", "=SUM(B2:B4)"]])
    b.format("A1:B1", bold=True)
    s = types.SimpleNamespace(wb=b)
    assert Spreadsheet._region(s, "B3") == "A1:B4"
    assert Spreadsheet._region(s, "A6") == "A6:B6"
    assert Spreadsheet._has_header(s, "A1:B4")
    assert not Spreadsheet._has_header(s, "A2:B4")


def test_from_rows_with_dicts():
    b = pz.Workbook.from_rows([{"name": "Ada", "age": 36}, {"name": "Alan", "age": 41}])
    assert b.records() == [{"name": "Ada", "age": 36}, {"name": "Alan", "age": 41}]


# --- The grid ---------------------------------------------------------------------------------


def drive(app, steps, size=(640, 360)):
    frames = []

    def script():
        for step in steps:
            result = yield step
            if step[0] == "snap":
                frames.append(result)

    _core.record(app, script(), size=size, scale=1)
    return frames


class Grid(pz.App):
    def __init__(self, book):
        self.book = book
        self.events = []

    def view(self):
        return pz.sheet(self.book, on_change=lambda e: self.events.append(e["action"]),
                        on_select=lambda e: self.events.append("select"))


def test_typing_into_the_grid_writes_cells():
    book = pz.Workbook()
    book["A1"] = 4
    app = Grid(book)
    # Formula bar 32 px, headers 24 px: B1 is under (40 + 100 + 50, 32 + 24 + 12).
    drive(app, [("move", 190, 68), ("down", "left"), ("up", "left"),
                ("type", "=a1*2"), ("key", "Enter", ""),
                ("type", "hello"), ("key", "Tab", ""), ("type", "x"), ("key", "Escape", "")])
    assert book.formula("B1") == "=A1*2" and book["B1"] == 8
    assert book["B2"] == "hello"
    assert book["C2"] is None
    assert "edit" in app.events and "select" in app.events


def test_keyboard_shortcuts_of_the_grid():
    book = book_with([[1], [2], [3]])
    app = Grid(book)
    drive(app, [("move", 90, 68), ("down", "left"), ("up", "left"),
                ("key", "ArrowDown", "shift"), ("key", "ArrowDown", "shift"), ("key", "b", CMD),
                ("key", "Delete", ""), ("key", "z", CMD)])
    assert book.style("A1").get("bold") is True
    assert book["A3"] == 3
    assert book.selection == "A1:A3"


def test_formula_suggestions_and_reference_picking():
    book = book_with([[1], [2], [3]])
    app = Grid(book)
    drive(app, [("move", 90, 140), ("down", "left"), ("up", "left"),  # A4
                ("type", "=su"), ("key", "Tab", ""),  # accepts SUM(
                ("key", "ArrowUp", ""), ("key", "ArrowUp", "shift"), ("key", "ArrowUp", "shift"),
                ("key", "Enter", "")])
    assert book.formula("A4") == "=SUM(A1:A3)"
    assert book["A4"] == 6


def test_the_grid_draws(tmp_path):
    book = book_with([["Name", "Units"], ["Apples", 3], ["Pears", 4]])
    book.format("A1:B1", bold=True, fill="#e8f0fe")
    frames = drive(Grid(book), [("snap",)])
    assert len(frames) == 1 and len(frames[0]) == 640 * 360 * 4


def test_spreadsheet_component_renders():
    class App(pz.App):
        def __init__(self):
            self.book = book_with([["a", 1], ["b", 2]])

        def view(self):
            return ui.Spreadsheet(book=self.book)

    app = App()
    frames = drive(app, [("snap",)], size=(900, 500))
    assert frames
    assert ui.sheet_colors()["accent"]


class Sheets(pz.App):
    def __init__(self):
        self.book = book_with([["apple"], ["pear"], ["apple pie"]])

    def view(self):
        return ui.Spreadsheet(book=self.book)


def test_double_click_on_a_tab_renames_the_sheet():
    app = Sheets()
    # The tabs are under the grid, 19 px from the bottom; "Sheet1" is the first one after "+".
    drive(app, [("move", 70, 481), ("down", "left"), ("up", "left"), ("down", "left"), ("up", "left"),
                ("type", "Fruit"), ("key", "Enter", "")], size=(900, 500))
    assert app.book.sheets == ["Fruit"]


def test_ctrl_f_types_into_the_find_field():
    app = Sheets()
    drive(app, [("move", 90, 150), ("down", "left"), ("up", "left"),
                ("key", "f", CMD), ("type", "pear"), ("key", "Enter", "")], size=(900, 500))
    assert app.book["A1"] == "apple"  # nothing was typed into a cell
    assert app.book.active_cell == "A2"


def test_events_carry_the_grid_size():
    book = book_with([[1]])
    seen = []

    class App(pz.App):
        def view(self):
            return pz.sheet(book, on_select=seen.append)

    drive(App(), [("move", 190, 68), ("down", "left"), ("up", "left")])
    assert seen and seen[-1]["view_width"] == 640 and seen[-1]["view_height"] == 360


def test_book_can_be_a_path_or_empty_text(tmp_path):
    path = tmp_path / "prices.xlsx"
    book_with([["Tea", 2.5]]).save(path)
    for given in ("", str(path), str(tmp_path / "missing.xlsx")):
        class App(pz.App):
            def view(self, given=given):
                return ui.Spreadsheet(book=given)

        assert drive(App(), [("snap",)], size=(600, 300))
