"""A playful pastel theme: cream background, candy colors and very round corners.

    python examples/theming/pastel.py

- ``Theme.generate`` for a light theme, then ``derive`` with a pastel info color and avatar colors.
- ``pz.define_style`` names a reusable "bubble" style for the card around everything.
"""

import pyzed as pz
from pyzed import ui
from preview import preview

PASTEL = pz.Theme.generate(
    "Pastel", background="#fffaf3", text="#4a3f55", accent="#f472b6", radius=16,
    success="#34d399", warning="#f59e0b", error="#fb7185",
).derive(info="#60a5fa", players=("#f472b6", "#a78bfa", "#60a5fa", "#34d399", "#fbbf24"))
pz.themes.register(PASTEL)

pz.define_style("bubble", background="surface", radius=24, padding=20, border=(2, "#f9a8d4"),
                shadow=("#f472b633", (0, 8), 24))


class PastelApp(pz.App):
    title = "Pastel"
    size = (720, 670)
    theme = "Pastel"

    def view(self):
        friends = pz.row([ui.avatar(name, index=i, size=30) for i, name in enumerate(["AL", "BO", "CY", "DI", "EV"])],
                         spacing=6)
        return pz.container(pz.column([
            pz.container(preview("Hello!", "Soft colors and round corners."), width="fill").style("bubble"),
            friends,
        ], spacing=16), padding=24, width="fill", height="fill")


if __name__ == "__main__":
    pz.run(PastelApp)
