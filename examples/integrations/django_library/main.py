"""A library catalog on Django's ORM: async queries on Pyzed's loop, and model validation shown on each field.

    uv run main.py                     # the desktop app
    uv run manage.py createsuperuser   # then `uv run manage.py runserver` for the same data in /admin/

The database (library.sqlite3) is created and migrated next to this file on the first run.
Walkthrough: https://albakore.github.io/pyzed/integrations/django/
"""

from __future__ import annotations

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "library_site.settings")
django.setup()  # before importing models

from asgiref.sync import sync_to_async  # noqa: E402
from django.core.exceptions import ValidationError  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.db.models import Count, Q  # noqa: E402

import pyzed as pz  # noqa: E402
from pyzed import ui  # noqa: E402

from catalog.models import Author, Book  # noqa: E402

BOOKS = [
    ("Ursula K. Le Guin", "United States", [("The Left Hand of Darkness", 1969, "9780441478125"),
                                             ("The Dispossessed", 1974, "9780061054884"),
                                             ("A Wizard of Earthsea", 1968, "9780547773742")]),
    ("Jorge Luis Borges", "Argentina", [("Ficciones", 1944, "9780802130303"), ("El Aleph", 1949, "9788499089508")]),
    ("Isaac Asimov", "United States", [("Foundation", 1951, "9780553293357"), ("I, Robot", 1950, "9780553382563")]),
    ("Octavia E. Butler", "United States", [("Kindred", 1979, "9780807083697"),
                                             ("Parable of the Sower", 1993, "9781538732182")]),
    ("Stanisław Lem", "Poland", [("Solaris", 1961, "9780156027601")]),
    ("Julio Cortázar", "Argentina", [("Rayuela", 1963, "9788437604572")]),
]


def prepare_database() -> None:
    """Applies the migrations and adds a few books the first time (plain synchronous Django)."""
    call_command("migrate", verbosity=0)
    if Author.objects.exists():
        return
    for name, country, books in BOOKS:
        author = Author.objects.create(name=name, country=country)
        Book.objects.bulk_create(Book(author=author, title=t, year=y, isbn=i) for t, y, i in books)


class Library(pz.App):
    title = "Library · Django"
    size = (1100, 680)

    def __init__(self):
        self.authors: list[Author] = []
        self.books: list[Book] = []
        self.author_id: int | None = None   # None shows every book
        self.query = ""
        self.editing = None                 # a Book, "new" or None
        self.draft: dict = {}
        self.errors: dict[str, str] = {}

    # -- Django's async ORM: the coroutines run on Pyzed's loop, the queries on Django's thread ---
    async def fetch(self, author_id, query):
        authors = [a async for a in Author.objects.annotate(count=Count("books"))]
        books = Book.objects.select_related("author")
        if author_id:
            books = books.filter(author_id=author_id)
        if query:
            books = books.filter(Q(title__icontains=query) | Q(author__name__icontains=query) | Q(isbn__startswith=query))
        return ("loaded", query, authors, [b async for b in books])

    async def set_available(self, book_id: int, available: bool):
        await Book.objects.filter(pk=book_id).aupdate(available=available)
        return ("changed",)

    async def store(self, book_id, draft: dict):
        book = await Book.objects.aget(pk=book_id) if book_id else Book()
        book.title, book.isbn, book.year = draft["title"], draft["isbn"], draft["year"]
        book.author = draft["author"]
        try:
            await sync_to_async(book.full_clean)()  # field validators, unique checks and Book.clean()
        except ValidationError as error:
            return ("invalid", error)
        await book.asave()
        return ("saved",)

    async def remove(self, book_id: int):
        await Book.objects.filter(pk=book_id).adelete()
        return ("saved",)

    # -- actions -------------------------------------------------------------------------
    def reload(self):
        return self.fetch(self.author_id, self.query)

    def on_start(self):
        return self.reload()

    def pick_author(self, author_id):
        self.author_id = author_id
        return self.reload()

    def search(self, text: str):
        self.query = text
        return self.reload()

    def open(self, book):
        self.editing, self.errors = book, {}
        if book == "new":
            author = next((a for a in self.authors if a.pk == self.author_id), self.authors[0] if self.authors else None)
            self.draft = {"title": "", "author": author, "year": "", "isbn": ""}
        else:
            self.draft = {"title": book.title, "author": book.author, "year": str(book.year), "isbn": book.isbn}

    def edit(self, key: str):
        return lambda value: self.draft.__setitem__(key, value)

    def save(self):
        return self.store(None if self.editing == "new" else self.editing.pk, dict(self.draft))

    def update(self, message):
        kind, *rest = message
        if kind == "loaded":
            query, authors, books = rest
            if query == self.query:
                self.authors, self.books = authors, books
        elif kind == "invalid":
            self.errors = pz.validation_errors(rest[0])
        elif kind == "saved":
            self.editing = None
            return self.reload()
        elif kind == "changed":
            return self.reload()

    def on_key(self, combo):
        if combo == "escape":
            self.editing = None
        elif combo == "ctrl-n" and self.authors:
            self.open("new")

    # -- view ----------------------------------------------------------------------------
    def sidebar(self, t):
        total = sum(a.count for a in self.authors)
        items = [ui.list_item("All books", lambda: self.pick_author(None), icon="library",
                              end=ui.count_badge(total, tint="text_muted"), selected=self.author_id is None, inset=True)]
        items += [ui.list_item(a.name, lambda a=a: self.pick_author(a.pk), icon="user",
                               end=ui.muted(str(a.count), size="sm"), selected=a.pk == self.author_id, inset=True)
                  for a in self.authors]
        return pz.container(pz.column([ui.muted("AUTHORS", size="xs", weight="semibold"), *items], spacing=2),
                            padding=8, width=250, height="fill", bg=t.panel)

    def dialog(self):
        if self.editing is None:
            return None
        e = self.errors.get
        general = e("")
        form = pz.column([
            ui.callout(general, tint="error") if general else None,
            ui.field("Title", ui.input(self.draft["title"], self.edit("title"), width=260), error=e("title")),
            ui.field("Author", ui.select(self.authors, self.draft["author"], self.edit("author"), width=260),
                     error=e("author")),
            ui.field("Year", ui.input(self.draft["year"], self.edit("year"), placeholder="1969", width=260),
                     error=e("year")),
            ui.field("ISBN", ui.input(self.draft["isbn"], self.edit("isbn"), placeholder="13 digits", mono=True,
                                      width=260), error=e("isbn")),
        ], spacing=12)
        new = self.editing == "new"
        close = lambda: setattr(self, "editing", None)  # noqa: E731
        footer = [ui.button("Cancel", close, variant="ghost"), ui.button("Save", self.save, icon="check", variant="solid")]
        if not new:
            footer.insert(0, ui.button("Delete", lambda: self.remove(self.editing.pk), icon="trash-2",
                                       variant="ghost", tint="error"))
        return ui.modal(form, title="New book" if new else "Edit book", on_close=close, width=560, footer=footer)

    def view(self):
        t = self.resolved_theme()
        columns = [
            ui.Column("Title", "title", width="fill:3"),
            ui.Column("Author", lambda b: b.author.name, width="fill:2"),
            ui.Column("Year", "year", width=70, align="end"),
            ui.Column("ISBN", "isbn", width=160, render=lambda isbn: ui.label(isbn, mono=True, color="text_muted")),
            ui.Column("Available", lambda b: b, width=100, align="center", sortable=False,
                      render=lambda b: ui.switch(b.available, lambda on, pk=b.pk: self.set_available(pk, on))),
        ]
        main = pz.column([
            pz.row([ui.search_input(self.query, self.search, placeholder="Title, author or ISBN…", width=340),
                    pz.hspace(),
                    ui.button("New book", lambda: self.open("new"), icon="book-plus", variant="solid", keys="ctrl-n")],
                   align="center"),
            ui.table(columns, self.books, on_row_press=self.open, row_height=36, height="fill"),
            ui.muted("Same data in the Django admin: uv run manage.py runserver, then open /admin/", size="sm"),
        ], spacing=12, padding=16)
        page = pz.row([self.sidebar(t), pz.container(main, width="fill", height="fill", bg=t.editor)])
        return ui.layer(page, self.dialog(), on_dismiss=lambda: setattr(self, "editing", None), backdrop="#00000066")


if __name__ == "__main__":
    prepare_database()
    pz.run(Library)
