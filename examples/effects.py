"""Effects drawn by the renderer: rotation, blur, backdrop blur, glass and bloom, animated.

    python examples/effects.py

- ``style(rotate=-8)`` turns a widget, ``blur=4`` blurs it and ``backdrop_blur=12`` blurs
  what is behind it; ``glass=True`` is a tinted panel with a backdrop blur.
- ``bloom=(color, intensity)`` lights up the area around the bright parts of a widget.
- ``animate("spin")`` and ``transition(rotate=..., blur=..., width=..., font_size=...)``
  animate them; size, padding and font size reflow the layout as they move.
"""

import pyzed as pz
from pyzed import ui

BACKDROP = pz.Gradient(["#ff006e", "#3a86ff", "#06d6a0"], angle=45)


class Effects(pz.App):
    title = "Effects"
    size = (900, 460)

    def __init__(self):
        self.focused = True
        self.wide = False

    def toggle_focus(self):
        self.focused = not self.focused

    def toggle_wide(self):
        self.wide = not self.wide

    def card(self, title, **style):
        return pz.container(pz.text(title, size=18), padding=20, width=150, height=100,
                            align_x="center", align_y="center").style(radius=12, **style)

    def view(self):
        cards = pz.row([
            self.card("Rotate", background="panel", rotate=-10).animate("tilt", on="hover"),
            self.card("Glass", glass=True),
            self.card("Bloom", background="#ffffff", color="#1f2937", bloom=("#ffbe0b", 1.0)),
            self.card("Blur", background="panel").transition(blur=0 if self.focused else 6),
        ], spacing=32, align="center")
        loader = pz.container(pz.icon("loader", size=28), padding=4).animate("spin")
        bar = pz.container(pz.text("Resizable", size=14), padding=10).style(background="panel", radius=8) \
            .transition(width=420 if self.wide else 160, font_size=20 if self.wide else 14, duration=260,
                        easing="ease_out_cubic")
        controls = pz.row([
            ui.button("Blur" if self.focused else "Focus", self.toggle_focus, variant="outline"),
            ui.button("Resize", self.toggle_wide, variant="outline"),
            loader,
            bar,
        ], spacing=16, align="center")
        return pz.container(pz.column([cards, controls], spacing=48, align="center"), width="fill",
                            height="fill", align_x="center", align_y="center").style(background=BACKDROP)


if __name__ == "__main__":
    Effects().run()
