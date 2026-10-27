"""A small store back office that shows the newer components working together.

    python examples/store_admin.py

Filters with a range slider, a tag box and a rating; the products split into pages; an order
followed with a stepper and a timeline, its details in a description list; and the numbers of
the week in a line chart, a gauge and progress rings. "Reload" shows skeletons for a moment.
"""

import random

import pyzed as pz
from pyzed import ui

PRODUCTS = [
    {"name": name, "price": price, "stars": stars, "tags": tags}
    for name, price, stars, tags in [
        ("Desk lamp", 39, 4, ["home", "light"]), ("Mechanical keyboard", 129, 5, ["desk", "tech"]),
        ("Notebook", 9, 3, ["paper"]), ("Monitor arm", 89, 4, ["desk"]), ("Headphones", 199, 5, ["tech", "audio"]),
        ("Plant pot", 19, 3, ["home"]), ("USB hub", 29, 4, ["tech"]), ("Desk mat", 25, 4, ["desk"]),
        ("Speaker", 149, 4, ["audio", "tech"]), ("Pen set", 15, 5, ["paper"]), ("Webcam", 79, 3, ["tech"]),
        ("Cable box", 22, 3, ["desk", "home"]), ("Bookend", 18, 4, ["home", "paper"]), ("Mic arm", 59, 4, ["audio"]),
    ]
]
PER_PAGE = 5
STEPS = ["Placed", "Paid", "Packed", "Shipped", "Delivered"]


class StoreAdmin(pz.App):
    title = "Store admin"
    size = (1120, 740)

    def __init__(self):
        self.price = (0, 200)
        self.tags = []
        self.min_stars = 0
        self.page = 1
        self.step = 3
        self.loading = 0

    # -- state ---------------------------------------------------------------
    def filtered(self):
        return [p for p in PRODUCTS
                if self.price[0] <= p["price"] <= self.price[1] and p["stars"] >= self.min_stars
                and all(tag in p["tags"] for tag in self.tags)]

    def set_filter(self, **values):
        for name, value in values.items():
            setattr(self, name, value)
        self.page = 1

    def reload(self):
        self.loading = 12  # frames of skeleton

    def subscriptions(self):
        return [pz.every(1 / 20, self.tick)] if self.loading else []

    def tick(self):
        self.loading -= 1

    # -- view ----------------------------------------------------------------
    def filters(self):
        return ui.card(pz.column([
            ui.label("Filters", weight="semibold"),
            self.labeled("Price", ui.range_slider(self.price, lambda v: self.set_filter(price=v), min=0, max=200,
                                                  step=5, show_value="{:.0f} €")),
            self.labeled("Tags", ui.tag_input(self.tags, lambda tags: self.set_filter(tags=tags),
                                              placeholder="Add a tag…",
                                              suggestions=sorted({t for p in PRODUCTS for t in p["tags"]}))),
            self.labeled("At least", ui.rating(self.min_stars, lambda n: self.set_filter(min_stars=n))),
        ], spacing=16), width=320)

    def labeled(self, title, control):
        return pz.column([ui.label(title, size="sm", color="text_muted"), control], spacing=6, width="fill")

    def products(self):
        found = self.filtered()
        pages = max((len(found) + PER_PAGE - 1) // PER_PAGE, 1)
        shown = found[(self.page - 1) * PER_PAGE:self.page * PER_PAGE]
        if self.loading:
            rows = [pz.row([ui.skeleton(height=28, circle=True), ui.skeleton(height=12)], spacing=10, align="center")
                    for _ in range(PER_PAGE)]
        elif not shown:
            rows = [ui.empty_state("No products", "Loosen the filters.", icon="search", size="sm", height=200)]
        else:
            rows = [pz.row([ui.avatar(p["name"]), pz.column([ui.label(p["name"]), ui.rating(p["stars"], size=12)]),
                            pz.hspace(), *[ui.chip(t) for t in p["tags"]], ui.label(f"{p['price']} €", mono=True)],
                           spacing=10, align="center") for p in shown]
        return ui.card(pz.column([
            pz.row([ui.label(f"Products ({len(found)})", weight="semibold"), pz.hspace(),
                    ui.button("Reload", self.reload, icon="refresh-cw", size="sm")], align="center"),
            pz.column(rows, spacing=12, height=220),
            pz.container(ui.pagination(self.page, pages, lambda n: setattr(self, "page", n)), width="fill",
                         align_x="center"),
        ], spacing=12), width="fill")

    def order(self):
        times = ["Mon 09:12", "Mon 09:13", "Tue 11:40", "Wed 08:05", "Thu 16:20"]
        icons = ["shopping-cart", "credit-card", "package", "truck", "package-check"]
        return ui.card(pz.column([
            pz.row([ui.label("Order #1042", weight="semibold"), pz.hspace(),
                    ui.badge(STEPS[min(self.step, 4)], tint="success" if self.step >= 4 else "accent")],
                   align="center"),
            ui.stepper(STEPS, self.step, lambda i: setattr(self, "step", i)),
            pz.row([
                pz.container(ui.timeline([ui.TimelineItem(STEPS[i], time=times[i], icon=icons[i],
                                                          tint="success" if i < self.step else "accent")
                                          for i in range(min(self.step + 1, 5))], dense=False), width="fill"),
                pz.container(ui.description_list({"Customer": "Ada Lovelace", "Items": "2", "Total": "168 €",
                                                  "Tracking": "PZ-7781-ES",
                                                  "Paid": ui.badge("Card", tint="success")},
                                                 label_width=80, mono_values=False), width="fill"),
            ], spacing=20),
            pz.row([ui.button("Back", lambda: setattr(self, "step", max(self.step - 1, 0)), size="sm"),
                    ui.button("Next step", lambda: setattr(self, "step", min(self.step + 1, 5)), size="sm",
                              variant="solid")], spacing=8),
        ], spacing=14), width="fill")

    def numbers(self):
        random.seed(4)
        visits = [random.randint(80, 140) + i * 12 for i in range(7)]
        sales = [v // 6 + random.randint(-4, 4) for v in visits]
        return ui.card(pz.row([
            ui.line_chart({"Visits": visits, "Sales": sales}, labels=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                          width=330, height=170, fill=True),
            pz.column([ui.gauge(72, unit="%", label="Stock used", size=130, thresholds=[(80, "warning"), (95, "error")]),
                       pz.row([ui.progress_ring(0.64, size=52, thickness=5, show_value=True),
                               ui.progress_ring(0.9, size=52, thickness=5, tint="success", label="9/10")],
                              spacing=16)], spacing=12, align="center"),
        ], spacing=16, align="center"), width="fill")

    def view(self):
        t = self.resolved_theme()
        return pz.container(pz.scrollable(pz.column([
            ui.heading("Store admin", level=2),
            pz.row([self.filters(), self.products()], spacing=16),
            pz.row([self.order(), self.numbers()], spacing=16),
        ], spacing=16, padding=24)), width="fill", height="fill", bg=t.background)


if __name__ == "__main__":
    pz.run(StoreAdmin)
