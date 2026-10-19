"""A PyPI explorer: concurrent httpx requests streamed into the window, responses validated by Pydantic.

    uv run main.py
    uv run main.py rich textual polars      # start with other packages

Walkthrough: https://albakore.github.io/pyzed/integrations/httpx-pydantic/
"""

from __future__ import annotations

import sys
import webbrowser
from datetime import datetime, timezone

import pyzed as pz
from pyzed import ui

from pypi import Package, fetch_all

DEFAULT = ["pyzed-ui", "fastapi", "django", "sqlalchemy", "sqlmodel", "httpx", "pydantic", "requests"]


def ago(when: datetime) -> str:
    days = (datetime.now(timezone.utc) - when).days
    if days < 1:
        return "today"
    if days < 60:
        return f"{days} days ago"
    return f"{days // 30} months ago" if days < 730 else f"{days // 365} years ago"


class Explorer(pz.App):
    title = "PyPI explorer · httpx + Pydantic"
    size = (1100, 680)

    def __init__(self, names: list[str]):
        self.names = names
        self.packages: dict[str, Package | str | None] = {name: None for name in names}  # None while loading
        self.selected = names[0] if names else None
        self.new_name = ""

    def on_start(self):
        return fetch_all(self.names)  # an async generator: each (name, result) it yields reaches update()

    def update(self, message):
        name, result = message
        self.packages[name] = result

    def add(self, *_):
        name = self.new_name.strip().lower()
        self.new_name = ""
        if not name:
            return None
        self.selected = name
        if name in self.packages and isinstance(self.packages[name], Package):
            return None
        self.packages[name] = None
        return fetch_all([name])

    # -- view ----------------------------------------------------------------------------
    def row(self, name: str):
        package = self.packages[name]
        if package is None:
            end = ui.spinner(size=12)
        elif isinstance(package, str):
            end = pz.icon("circle-alert", size=14, color=self.resolved_theme().error)
        else:
            end = ui.muted(package.info.version, size="sm", mono=True)
        return ui.list_item(name, lambda: setattr(self, "selected", name), icon="package", end=end,
                            selected=name == self.selected, inset=True, height=30)

    def details(self, t):
        package = self.packages.get(self.selected)
        if package is None:
            return pz.center(ui.spinner(size=24))
        if isinstance(package, str):
            return pz.center(ui.empty_state(self.selected, package, icon="circle-alert"))
        info, history = package.info, package.history()
        years = package.per_year()
        links = [ui.button(label, lambda url=url: webbrowser.open(url), icon="external-link", size="sm", variant="ghost")
                 for label, url in list((info.project_urls or {}).items())[:4]]
        versions = ui.virtual_list(history, lambda item: pz.row([
            ui.label(item[0], mono=True, width="fill"), ui.muted(item[1].strftime("%Y-%m-%d"), size="sm")],
            padding=(0, 8), align="center", height=26), item_height=26)
        return pz.column([
            pz.row([ui.heading(info.name, level=2), ui.badge(info.version, tint="success")], spacing=10, align="center"),
            ui.muted(info.summary or "No summary.", size="lg"),
            pz.row(links, spacing=4) if links else None,
            pz.row([
                ui.stat("Releases", len(history)),
                ui.stat("Latest", ago(history[0][1]) if history else "—"),
                ui.stat("Python", info.requires_python or "any"),
                ui.stat("License", (info.license_expression or info.license or "—")[:18]),
            ], spacing=12),
            pz.row([
                ui.card(ui.bar_chart([count for _, count in years], labels=[str(y)[2:] for y, _ in years],
                                     width=340, height=150), title="Releases per year", width=374),
                ui.card(pz.container(versions, height=150), title="Versions", width="fill"),
            ], spacing=12),
        ], spacing=14, padding=20)

    def view(self):
        t = self.resolved_theme()
        loading = sum(p is None for p in self.packages.values())
        sidebar = pz.container(pz.column([
            ui.input(self.new_name, lambda v: setattr(self, "new_name", v), placeholder="Add a package…",
                     icon="plus", on_submit=self.add),
            ui.virtual_list(list(self.packages), self.row, item_height=30),
            ui.muted(f"Loading {loading}…" if loading else f"{len(self.packages)} packages", size="sm"),
        ], spacing=8), padding=8, width=260, height="fill", bg=t.panel)
        return pz.row([sidebar, pz.container(self.details(t), width="fill", height="fill", bg=t.editor)])


if __name__ == "__main__":
    pz.run(Explorer(sys.argv[1:] or DEFAULT))
