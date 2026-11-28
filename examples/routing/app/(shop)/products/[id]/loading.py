import pyzed as pz
from pyzed import ui


def loading():
    return pz.column([ui.skeleton(240, 28), ui.skeleton(lines=3), ui.skeleton(120, 32)], spacing=16)
