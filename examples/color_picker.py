"""Color picker: a color with alpha, a linear gradient, or a fill with an opacity mask.

    python examples/color_picker.py

``ui.ColorPicker`` reports a ``"#rrggbbaa"`` string, a ``pz.Gradient`` or a ``pz.Paint``;
all of them work as a ``background`` in ``widget.style``.
"""

import pyzed as pz
from pyzed import ui


class ColorPickerDemo(pz.App):
    title = "Color picker"
    size = (640, 560)

    def __init__(self):
        self.fill = pz.Gradient(["#6366f1", "#ec4899"], angle=135)

    def pick(self, event):
        self.fill = event.value

    def view(self):
        preview = pz.container(None, width="fill", height="fill").style(background=self.fill)
        return pz.row([
            ui.ColorPicker(value=self.fill, on_change=self.pick),
            pz.column([
                pz.stack([ui.checkerboard(320, 360, 12), preview], width=320, height=360).style(border=(1, "border")),
                pz.text(repr(self.fill)).style(font="mono", size=12, color="text_muted"),
            ], spacing=10, width="fill"),
        ], spacing=20).style(padding=24, width="fill", height="fill")


if __name__ == "__main__":
    pz.run(ColorPickerDemo)
