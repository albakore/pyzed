"""Web-style layout: boxes, a stylesheet with states, media queries and nested components.

    python examples/web_layout.py

- ``pz.box`` works like a ``div``: block, flex, grid or stack, with ``gap`` and every style.
- ``pz.stylesheet`` holds the CSS-like rules; ``:hover`` and ``transition`` animate the cards.
- ``@media`` rules and ``pz.media`` adapt the page when the window is narrow.
- ``Card`` takes its content as children and reads the chosen plan from the context.
"""

import pyzed as pz
from pyzed import ui

pz.stylesheet({
    ".page": {"background": "background", "padding": 32, "width": "fill", "height": "fill"},
    ".hero": {"size": 28, "weight": "bold"},
    ".muted": {"color": "text_muted"},
    "@media (max_width: 720)": {".page": {"padding": 16}, ".hero": {"size": 22}},
})

PLANS = [("Free", "$0", "For trying things out."), ("Pro", "$8", "For people who ship every week."),
         ("Team", "$20", "Shared projects and roles.")]


class Card(pz.Component):
    """A plan card: its content comes in as children."""

    name: str = ""
    children: list = ()
    events = {"pick": "The card was clicked."}
    stylesheet = {
        "&": {"background": "panel", "border": (1, "border"), "radius": 10, "padding": 16, "transition": 120},
        "&:hover": {"border_color": "accent", "translate": (0, -2)},
        "&.chosen": {"border": (2, "accent")},
    }

    def render(self):
        chosen = self.context("plan") == self.name
        return pz.box(*self.children, ui.label("✓ Selected").classes("muted") if chosen else None, gap=6).on(
            click=lambda: self.emit("pick", self.name), cursor="pointer")


class WebLayout(pz.App):
    title = "Web layout"
    size = (900, 560)

    def __init__(self):
        self.plan = "Pro"

    def card(self, name, price, text):
        return Card(
            pz.text(name).style(weight="semibold"),
            pz.text(price).style(size=22, weight="bold"),
            pz.text(text).classes("muted"),
            ui.badge("Popular").style(position="absolute", top=0, right=0) if name == "Pro" else None,
            name=name, class_="chosen" if name == self.plan else None,
            on_pick=lambda e: setattr(self, "plan", e.value),
        )

    def view(self):
        narrow = pz.media("max_width: 720")
        with pz.provide(plan=self.plan):
            cards = [self.card(*plan) for plan in PLANS]
        return pz.box(
            pz.text("Pick a plan").classes("hero"),
            pz.text("Boxes, a stylesheet and media queries, like a web page.").classes("muted"),
            pz.box(cards, display="grid", columns=1 if narrow else 3, gap=16),
            pz.box(ui.button("Cancel", lambda: None), ui.button(f"Continue with {self.plan}", lambda: None),
                   display="flex", justify="end", gap=8),
            gap=20, class_="page", overflow="scroll",
        )


if __name__ == "__main__":
    pz.run(WebLayout)
