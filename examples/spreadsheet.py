"""A spreadsheet like Google Sheets or Excel: formulas, formats, filters, dropdowns and several sheets.

    python examples/spreadsheet.py

``pz.Workbook`` holds the cells and does the work (formulas, sorting, undo, Excel files);
``ui.Spreadsheet`` shows it with a toolbar, menus and sheet tabs. Open and save ``.xlsx``,
``.ods`` and ``.csv`` files from the title bar (``.ods`` is only read).
"""

import pyzed as pz
from pyzed import ui


def sample() -> pz.Workbook:
    book = pz.Workbook(sheets=["Sales", "Team"])
    book.write(
        [
            ["Date", "Region", "Product", "Units", "Price", "Total", "Paid"],
            ["2026-01-05", "North", "Apples", 120, 0.5, "=D2*E2", True],
            ["2026-01-09", "South", "Pears", 80, 0.75, "=D3*E3", True],
            ["2026-01-14", "East", "Plums", 45, 1.2, "=D4*E4", False],
            ["2026-02-02", "North", "Grapes", 200, 2.25, "=D5*E5", True],
            ["2026-02-11", "West", "Apples", 65, 0.5, "=D6*E6", False],
            ["2026-02-20", "South", "Cherries", 30, 4.1, "=D7*E7", True],
            ["2026-03-03", "East", "Pears", 150, 0.75, "=D8*E8", True],
            ["2026-03-17", "West", "Grapes", 90, 2.25, "=D9*E9", False],
        ],
        at="A1",
    )
    book["A11"] = "Total"
    book["D11"] = "=SUM(D2:D9)"
    book["F11"] = "=SUM(F2:F9)"
    book["A12"] = "Paid"
    book["F12"] = '=SUMIF(G2:G9, TRUE, F2:F9)'
    book["A13"] = "Top sale"
    book["F13"] = "=INDEX(B2:B9, MATCH(MAX(F2:F9), F2:F9, 0))"
    book.format("A1:G1", bold=True, fill="#e8f0fe", borders="bottom")
    book.format("E2:F12", number_format="$#,##0.00")
    book.format("A11:G13", bold=True)
    book.format("A11:G11", borders="top")
    book.validate("B2:B9", options=["North", "South", "East", "West"])
    book.validate("G2:G9", checkbox=True)
    book.conditional_format("D2:D9", "data_bar", fill="#a8dab5")
    book.conditional_format("F2:F9", ">", 150, fill="#fce8b2")
    book.note("F13", "The region of the largest sale.")
    book.column_width("A", 110)
    book.column_width("C", 110)
    book.freeze(rows=1)
    book.filter("A1:G9")

    book.active = "Team"
    book.write(
        [
            ["Name", "Role", "Started", "Days", "Rating"],
            ["Ada", "Engineer", "2021-04-01", "=DATEDIF(C2, TODAY(), \"d\")", 5],
            ["Grace", "Manager", "2019-09-15", "=DATEDIF(C3, TODAY(), \"d\")", 4],
            ["Linus", "Engineer", "2023-01-10", "=DATEDIF(C4, TODAY(), \"d\")", 3],
        ],
        at="A1",
    )
    book.format("A1:E1", bold=True, fill="#e6f4ea")
    book.conditional_format("E2:E4", "color_scale", colors=["#f4c7c3", "#ffffff", "#b7e1cd"])
    book.active = "Sales"
    book.select("A1")
    return book


class SpreadsheetApp(pz.App):
    title = "Spreadsheet"
    size = (1100, 680)

    def __init__(self):
        self.book = sample()
        self.path = None

    def open(self):
        def opened(paths):
            if paths:
                self.book = pz.Workbook.open(paths[0])
                self.path = paths[0]

        return pz.Command.pick_files(opened, multiple=False,
                                     filters=[("Spreadsheets", ["xlsx", "xls", "ods", "csv", "tsv"])])

    def save(self):
        def chosen(paths):
            if paths:
                self.book.save(paths[0])
                self.path = paths[0]

        return pz.Command.save_file(chosen, file_name="book.xlsx",
                                    filters=[("Excel", ["xlsx"]), ("CSV", ["csv"])])

    def view(self):
        t = self.resolved_theme()
        bar = ui.toolbar(
            [ui.label(self.path or "Untitled spreadsheet", weight="semibold")],
            [ui.button("Open…", self.open, icon="folder-open", size="sm"),
             ui.button("Save as…", self.save, icon="save", size="sm")],
            height=40,
        )
        return pz.column([bar, ui.Spreadsheet(book=self.book)], width="fill", height="fill").style(background=t.editor)


if __name__ == "__main__":
    pz.run(SpreadsheetApp)
