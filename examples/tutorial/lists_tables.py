"""Lists and tables with data: search, sort, select a row and show its details.

    python examples/tutorial/lists_tables.py

- The data is a plain Python list of dicts; ``view()`` filters it with the search text.
- ``ui.table`` draws it with sortable columns (``sort_by``/``descending``/``on_sort``),
  clickable rows (``on_row_press``) and a highlighted ``selected`` row.
- ``ui.Column(..., render=...)`` turns a cell into any widget (here, a colored badge).
- A segmented control switches between the table and a simple list of ``ui.list_item`` rows.

Walkthrough: https://albakore.github.io/pyzed/tutorials/intermediate/lists-tables/
"""

import pyzed as pz
from pyzed import ui

BOOKS = [
    {"title": "Dune", "author": "Frank Herbert", "year": 1965, "status": "Read"},
    {"title": "Neuromancer", "author": "William Gibson", "year": 1984, "status": "Reading"},
    {"title": "The Left Hand of Darkness", "author": "Ursula K. Le Guin", "year": 1969, "status": "Read"},
    {"title": "Foundation", "author": "Isaac Asimov", "year": 1951, "status": "Wishlist"},
    {"title": "Hyperion", "author": "Dan Simmons", "year": 1989, "status": "Reading"},
    {"title": "Snow Crash", "author": "Neal Stephenson", "year": 1992, "status": "Wishlist"},
    {"title": "Solaris", "author": "Stanisław Lem", "year": 1961, "status": "Read"},
]
TINTS = {"Read": "success", "Reading": "accent", "Wishlist": "warning"}


class Library(pz.App):
    title = "My books"
    size = (860, 540)

    def __init__(self):
        self.query = ""
        self.sort_by, self.descending = "Year", False
        self.selected = None  # the book (a dict) shown in the details panel
        self.mode = "Table"

    def visible(self):
        q = self.query.lower()
        return [b for b in BOOKS if q in b["title"].lower() or q in b["author"].lower()]

    def sort(self, column):
        # Clicking the same header again flips the order.
        self.descending = not self.descending if column == self.sort_by else False
        self.sort_by = column

    def table(self, books):
        columns = [
            ui.Column("Title", "title", width=("fill", 3)),
            ui.Column("Author", "author", width=("fill", 2)),
            ui.Column("Year", "year", width=70),
            ui.Column("Status", "status", width=100, render=lambda s: ui.badge(s, tint=TINTS[s])),
        ]
        return ui.table(columns, books, sort_by=self.sort_by, descending=self.descending, on_sort=self.sort,
                        on_row_press=lambda book: setattr(self, "selected", book), selected=self.selected,
                        striped=True, row_height=34, height="fill")

    def simple_list(self, books):
        return pz.scrollable(pz.column([
            ui.list_item(book["title"], lambda book=book: setattr(self, "selected", book), icon="book",
                         selected=book is self.selected, end=ui.muted(str(book["year"])), height=32)
            for book in books
        ], spacing=2), height="fill")

    def details(self):
        book = self.selected
        if book is None:
            return ui.empty_state("Pick a book", "Click a row to see its details.", icon="book-open")
        return pz.column([
            ui.heading(book["title"], level=3),
            ui.label(f"by {book['author']}, {book['year']}", color="text_muted"),
            ui.segmented(list(TINTS), book["status"], lambda s: book.__setitem__("status", s)),
        ], spacing=10)

    def view(self):
        t = self.resolved_theme()
        books = self.visible()
        left = pz.column([
            pz.row([
                pz.container(ui.search_input(self.query, lambda v: setattr(self, "query", v),
                                             placeholder="Search title or author…"), width="fill"),
                ui.segmented(["Table", "List"], self.mode, lambda m: setattr(self, "mode", m)),
            ], spacing=8, align="center"),
            ui.muted(f"{len(books)} of {len(BOOKS)} books", size="sm"),
            self.table(books) if self.mode == "Table" else self.simple_list(books),
        ], spacing=10, width="fill", height="fill")
        right = pz.container(self.details(), width=260, height="fill", padding=16, bg=t.surface, radius=t.radius)
        return pz.container(pz.row([left, right], spacing=16), padding=20, width="fill", height="fill",
                            bg=t.background)


if __name__ == "__main__":
    pz.run(Library)
