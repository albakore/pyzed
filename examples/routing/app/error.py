import pyzed as pz
from pyzed import ui


def error(error, reset):
    return pz.column([
        ui.heading("Something went wrong", level=2),
        ui.label(str(error), color="text_muted"),
        ui.button("Try again", reset, icon="rotate-ccw"),
    ], spacing=12)
