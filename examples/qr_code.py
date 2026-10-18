"""Type something and get its QR code, after Iced's ``qr_code`` demo."""

import pyzed as pz
from pyzed import ui


class QR(pz.App):
    title = "QR code"
    size = (420, 520)

    def __init__(self):
        self.data = "https://github.com/albakore/pyzed"
        self.dark = True

    def view(self):
        t = self.resolved_theme()
        fg, bg = (t.text, t.surface) if self.dark else ("#000000", "#ffffff")
        return pz.container(
            pz.column([
                ui.heading("QR code", level=2),
                ui.input(self.data, lambda v: setattr(self, "data", v), placeholder="Text or URL"),
                ui.checkbox(self.dark, lambda v: setattr(self, "dark", v), label="Use theme colors"),
                pz.container(pz.qr_code(self.data, cell_size=7, color=fg, bg=bg) if self.data else ui.muted("Empty"),
                             padding=16, bg=bg, radius=t.radius),
            ], spacing=14, align="center"),
            padding=24, width="fill", height="fill", align_x="center", bg=t.background,
        )


if __name__ == "__main__":
    pz.run(QR)
