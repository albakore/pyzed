"""An RPG inventory: a grid of items whose rarity glows, and a glass details panel.

    python examples/showcase/inventory.py

- Rarity is light: rare items ``glow``, epic and legendary ones ``bloom`` (and legendary
  ones pulse with ``animate("glow_pulse")``).
- The details panel is ``glass`` over an ember backdrop, a shader graph made of nodes in
  Pyzed Design (``shaders/embers.pzshad``); stat bars and the selected slot animate with
  ``transition``.
- Click an item to inspect it.
"""

from pathlib import Path

import pyzed as pz

SHADER = Path(__file__).parent / "shaders" / "embers.pzshad"


RARITY = {
    "common": ("#9ca3af", None),
    "rare": ("#60a5fa", "glow"),
    "epic": ("#c084fc", "bloom"),
    "legendary": ("#fb923c", "bloom"),
}
ITEMS = (
    ("sword", "Dawnbreaker", "legendary", "Weapon", {"Attack": 0.92, "Speed": 0.64, "Crit": 0.71}),
    ("shield", "Aegis of Tides", "epic", "Off-hand", {"Armor": 0.81, "Block": 0.66, "Weight": 0.40}),
    ("wand", "Ember Wand", "rare", "Weapon", {"Attack": 0.58, "Speed": 0.80, "Crit": 0.35}),
    ("gem", "Star Shard", "epic", "Material", {"Purity": 0.88, "Power": 0.62, "Value": 0.74}),
    ("flask-conical", "Health Potion", "common", "Consumable", {"Heal": 0.45, "Duration": 0.10, "Value": 0.08}),
    ("scroll", "Scroll of Return", "common", "Consumable", {"Range": 0.30, "Value": 0.12, "Weight": 0.05}),
    ("crown", "Crown of Ash", "legendary", "Helm", {"Armor": 0.55, "Wisdom": 0.95, "Charm": 0.86}),
    ("key", "Old Key", "common", "Quest", {"Value": 0.02, "Weight": 0.04, "Rust": 0.90}),
    ("feather", "Phoenix Plume", "rare", "Material", {"Power": 0.70, "Purity": 0.52, "Value": 0.61}),
    ("bow-arrow", "Windstring", "rare", "Weapon", {"Attack": 0.66, "Speed": 0.87, "Crit": 0.50}),
    ("shirt", "Silk Tunic", "common", "Chest", {"Armor": 0.20, "Speed": 0.60, "Weight": 0.10}),
    ("apple", "Golden Apple", "epic", "Consumable", {"Heal": 0.95, "Duration": 0.60, "Value": 0.70}),
)
#: Each rarity's slot color.
TINT = {"common": "#1f1d24", "rare": "#16233a", "epic": "#2a1a3d", "legendary": "#3a2112"}
COLUMNS, ROWS = 6, 4
SLOT = 76


class Inventory(pz.App):
    title = "Inventory"
    size = (1180, 640)
    theme = pz.themes.ONE_DARK

    def __init__(self):
        self.selected = 0

    def select(self, index):
        self.selected = index

    def slot(self, index):
        if index >= len(ITEMS):
            return pz.container(None, width=SLOT, height=SLOT).style(
                background="#ffffff08", radius=12, border=(1, "#ffffff12"))
        icon, name, rarity, _, _ = ITEMS[index]
        color, light = RARITY[rarity]
        selected = index == self.selected
        # A plain color, not a gradient: the GPU renderer draws halos only around solid boxes.
        style = dict(radius=12, background=TINT[rarity],
                     border=(2 if selected else 1, color if selected else color + "66"))
        if light == "glow":
            style.update(glow=(color + "88", 10))
        elif light == "bloom":
            style.update(bloom=(color, 0.55 if rarity == "epic" else 0.8))
        tile = pz.container(pz.icon(icon, size=32, color="#ffffff"), width=SLOT, height=SLOT,
                            align_x="center", align_y="center").style(**style)
        if rarity == "legendary":
            tile = tile.animate("glow_pulse", repeat="infinite", duration=2000)
        tile = pz.mouse_area(tile, on_press=lambda: self.select(index))
        return tile.animate("grow", on="hover").animate("shrink", on="press")

    def grid(self):
        rows = [pz.row([self.slot(r * COLUMNS + c) for c in range(COLUMNS)], spacing=10) for r in range(ROWS)]
        gold = pz.row([pz.icon("coins", size=16, color="#fbbf24"),
                       pz.text("12,480", size=14, weight="bold", color="#fde68a"),
                       pz.space(width="fill"),
                       pz.text(f"{len(ITEMS)} / {COLUMNS * ROWS}", size=12, color="#ffffff88")],
                      spacing=8, align="center", width=COLUMNS * SLOT + (COLUMNS - 1) * 10)
        return pz.column([
            pz.text("INVENTORY", size=13, weight="bold", color="#fdba74"),
            pz.column(rows, spacing=10),
            gold,
        ], spacing=14).style(glass={"tint": "#140b0b", "strength": 0.35, "blur": 16}, radius=20, padding=20)

    def details(self):
        icon, name, rarity, kind, stats = ITEMS[self.selected]
        color, _ = RARITY[rarity]
        bars = []
        for label, value in stats.items():
            bars.append(pz.column([
                pz.row([pz.text(label, size=12, color="#ffffffbb"), pz.space(width="fill"),
                        pz.text(str(round(value * 100)), size=12, weight="bold", color="#ffffff")], width=240),
                pz.container(pz.container(None, height=8).style(
                    background=pz.Gradient([color + "88", color], angle=90), radius=4).transition(
                    width=240 * value, duration=320, easing="ease_out_cubic"),
                    width=240).style(background="#ffffff14", radius=4),
            ], spacing=4))
        hero = pz.container(pz.icon(icon, size=56, color="#ffffff").style(bloom=(color, 0.9)), width=240,
                            height=150, align_x="center", align_y="center").style(
            background=pz.Gradient([color + "44", "#00000000"], angle=180), radius=16)
        panel = pz.column([
            hero,
            pz.text(name, size=22, weight="bold", color="#ffffff"),
            pz.row([pz.text(rarity.upper(), size=11, weight="bold", color=color),
                    pz.text("·", size=11, color="#ffffff66"),
                    pz.text(kind, size=11, color="#ffffffaa")], spacing=6),
            *bars,
            pz.row([
                pz.text("Equip", size=13, weight="bold", color="#1c1917").style(
                    background=color, radius=8, padding=(8, 18)).animate("lift", on="hover"),
                pz.text("Drop", size=13, color="#ffffffcc").style(
                    background="#ffffff14", radius=8, padding=(8, 18), border=(1, "#ffffff22")),
            ], spacing=10),
        ], spacing=12, width=240)
        return pz.presence(panel.style(glass={"tint": "#1c1012", "strength": 0.3, "blur": 18}, radius=20,
                                       padding=20), key=self.selected, enter="fade_in_right",
                           exit="fade_out", id="details")

    def view(self):
        body = pz.row([self.grid(), self.details()], spacing=24, align="start")
        return pz.stack([
            pz.shader(SHADER, width="fill", height="fill", fallback=pz.Gradient(["#0f0707", "#2a0e05"], angle=180)),
            pz.container(body, width="fill", height="fill", align_x="center", align_y="center"),
        ])


if __name__ == "__main__":
    pz.run(Inventory)
