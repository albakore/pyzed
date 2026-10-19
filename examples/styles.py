"""Styles: CSS-like properties on any widget, named styles, gradients, masks and a global style.

    python examples/styles.py

- ``widget.style(...)`` sets borders, radius, background, shadow, padding and typography.
- ``pz.define_style`` names a style; ``App.style`` styles the whole window.
- Backgrounds take colors with alpha, ``pz.Gradient`` and ``pz.Paint`` with a ``pz.Mask``.
"""

import pyzed as pz
from pyzed import ui

pz.define_style("card", background="elevated", border=(1, "border"), radius=10, padding=16,
                shadow=("#00000055", (0, 6), 18))
pz.define_style("pill", radius=999, padding=(4, 12), size=12, weight="semibold")

SUNSET = pz.Gradient(["#f97316", "#db2777", "#7c3aed"], angle=120)


class StylesDemo(pz.App):
    title = "Styles"
    size = (860, 520)
    # The global style: every text in the window uses it unless a closer style says otherwise.
    style = pz.Style(font="sans", size=14, color="text")

    def __init__(self):
        self.round = True

    def view(self):
        buttons = pz.row([
            ui.button("Default", lambda: None),
            ui.button("Square, red border", lambda: None).style(radius=0, border=(2, "#ef4444")),
            ui.button("Mono + bold", lambda: None).style(font="mono", weight="bold", color="accent"),
            ui.button("Gradient", lambda: None).style(background=SUNSET, color="#ffffff", radius=8),
        ], spacing=10)
        pills = pz.row([
            pz.text("pill").style("pill", background="accent", color="#ffffff"),
            pz.text("success").style("pill", background=pz.Paint("success", opacity=0.2), color="success"),
            pz.text("warning").style("pill", background=pz.Paint("warning", opacity=0.2), color="warning"),
        ], spacing=8)
        faded = pz.container(None, width="fill", height=90).style(
            background=pz.Paint(SUNSET, mask=pz.Mask([1, 0.15])), radius=10)
        card = pz.column([
            pz.text("A card").style(size=18, weight="semibold"),
            pz.text("Every text inside a style inherits its typography.").style(color="text_muted"),
            pills,
        ], spacing=10).style("card", width="fill")
        return pz.column([
            pz.text("widget.style(...)").style(size=22, weight="bold"),
            buttons,
            card,
            pz.text("pz.Paint(gradient, mask=pz.Mask([1, 0.15]))").style(font="mono", size=12, color="text_muted"),
            faded,
        ], spacing=16).style(padding=24, background="background", width="fill", height="fill")


if __name__ == "__main__":
    pz.run(StylesDemo)
