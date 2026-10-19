"""An inventory app on SQLModel: the form is validated by the same model that defines the table.

    uv run main.py

The database (inventory.db) is created next to this file on the first run.
Walkthrough: https://albakore.github.io/pyzed/integrations/sqlmodel/
"""

from __future__ import annotations

from pydantic import ValidationError

import pyzed as pz
from pyzed import Command, ui

import models
from models import CATEGORIES, Product, ProductIn

LOW_STOCK = 5


class Inventory(pz.App):
    title = "Inventory · SQLModel"
    size = (1100, 680)

    def __init__(self):
        self.products: list[Product] = []
        self.category = "All"
        self.editing = None            # a Product, "new" or None
        self.draft: dict[str, str] = {}
        self.errors: dict[str, str] = {}

    def on_start(self):
        return Command.perform(lambda: (models.setup(), models.products())[1], self.loaded)

    def loaded(self, products: list[Product]):
        self.products = products

    def reload(self):
        return Command.perform(models.products, self.loaded)

    # -- the form ----------------------------------------------------------------------
    def open(self, product):
        self.editing, self.errors = product, {}
        if product == "new":
            self.draft = {"name": "", "sku": "", "category": CATEGORIES[0], "price": "", "stock": "0"}
        else:
            self.draft = {key: str(getattr(product, key)) for key in ("name", "sku", "category", "price", "stock")}

    def edit(self, key: str):
        return lambda value: self.draft.__setitem__(key, value)

    def save(self):
        try:
            data = ProductIn.model_validate(self.draft)  # strings from the inputs are coerced or rejected here
        except ValidationError as error:
            self.errors = pz.validation_errors(error)
            return None
        product_id = None if self.editing == "new" else self.editing.id
        return Command.perform(lambda: models.save(product_id, data), self.saved)

    def saved(self, result):
        if isinstance(result, dict):
            self.errors = result
            return None
        self.editing = None
        return self.reload()

    def restock(self, product: Product, amount: int):
        return Command.perform(lambda: models.restock(product.id, amount), lambda _: self.reload())

    def on_key(self, combo):
        if combo == "escape":
            self.editing = None
        elif combo == "ctrl-n":
            self.open("new")

    # -- view ----------------------------------------------------------------------------
    def stock_cell(self, product: Product):
        if product.stock == 0:
            badge = ui.badge("out of stock", tint="error")
        elif product.stock < LOW_STOCK:
            badge = ui.badge(f"{product.stock} left", tint="warning")
        else:
            badge = ui.label(str(product.stock), mono=True)
        return pz.row([
            ui.icon_button("minus", lambda: self.restock(product, -1), size="sm", tooltip="Sell one"),
            pz.container(badge, width=96, align_x="center"),
            ui.icon_button("plus", lambda: self.restock(product, 1), size="sm", tooltip="Receive one"),
        ], spacing=4, align="center")

    def summary(self, t):
        value = sum(p.price * p.stock for p in self.products)
        by_category = [sum(p.price * p.stock for p in self.products if p.category == c) for c in CATEGORIES]
        palette = [t.accent, t.success, t.warning, t.error, t.players[3]]
        legend = pz.column([pz.row([ui.indicator(color), ui.muted(c, size="sm")], spacing=6, align="center")
                            for c, color in zip(CATEGORIES, palette)], spacing=2)
        return pz.row([
            ui.stat("Stock value", f"${value:,.0f}"),
            ui.stat("Low stock", sum(0 < p.stock < LOW_STOCK for p in self.products)),
            ui.stat("Out of stock", sum(p.stock == 0 for p in self.products)),
            ui.card(pz.row([ui.donut(by_category, colors=palette, size=84, thickness=12), legend],
                           spacing=14, align="center"), padding=10),
        ], spacing=12, align="center")

    def dialog(self):
        if self.editing is None:
            return None
        e = self.errors.get
        fields = pz.column([
            ui.field("Name", ui.input(self.draft["name"], self.edit("name"), width=240), error=e("name")),
            ui.field("SKU", ui.input(self.draft["sku"], self.edit("sku"), placeholder="KEY-0003", mono=True,
                                     width=240), description="Three letters, a dash and four digits", error=e("sku")),
            ui.field("Category", ui.select(CATEGORIES, self.draft["category"], self.edit("category"), width=240)),
            ui.field("Price", ui.input(self.draft["price"], self.edit("price"), placeholder="0.00", width=240),
                     error=e("price")),
            ui.field("Stock", ui.input(self.draft["stock"], self.edit("stock"), width=240), error=e("stock")),
        ], spacing=12)
        close = lambda: setattr(self, "editing", None)  # noqa: E731
        return ui.modal(fields, title="New product" if self.editing == "new" else "Edit product", on_close=close,
                        width=520, footer=[ui.button("Cancel", close, variant="ghost"),
                                           ui.button("Save", self.save, icon="check", variant="solid")])

    def view(self):
        t = self.resolved_theme()
        shown = [p for p in self.products if self.category in ("All", p.category)]
        columns = [
            ui.Column("Product", "name", width="fill:3"),
            ui.Column("SKU", "sku", render=lambda sku: ui.label(sku, mono=True, color="text_muted")),
            ui.Column("Category", "category"),
            ui.Column("Price", "price", align="end", render=lambda price: ui.label(f"${price:,.2f}", mono=True)),
            ui.Column("Stock", lambda p: p, width=180, align="center", render=self.stock_cell, sortable=False),
        ]
        toolbar = pz.row([
            ui.segmented(["All", *CATEGORIES], self.category, lambda c: setattr(self, "category", c)),
            pz.hspace(),
            ui.button("New product", lambda: self.open("new"), icon="package-plus", variant="solid", keys="ctrl-n"),
        ], align="center")
        page = pz.container(
            pz.column([self.summary(t), toolbar,
                       ui.table(columns, shown, on_row_press=self.open, row_height=40, height="fill")], spacing=14),
            padding=16, width="fill", height="fill", bg=t.editor,
        )
        return ui.layer(page, self.dialog(), on_dismiss=lambda: setattr(self, "editing", None),
                        backdrop="#00000066")


if __name__ == "__main__":
    pz.run(Inventory)
