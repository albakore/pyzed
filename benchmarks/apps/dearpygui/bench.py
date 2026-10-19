"""Bench app: ROWS rows in a child window (see ../benchkit.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchkit import FOOTER, H, ROWS, TICK, W, A, Driver, color, hexc, label  # noqa: E402

import time  # noqa: E402

import dearpygui.dearpygui as dpg  # noqa: E402

dpg.create_context()
themes = {}
for c in (A, color(1)):
    with dpg.theme() as theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, c)
            dpg.add_theme_style(dpg.mvStyleVar_ChildBorderSize, 0)
    themes[c] = theme
with dpg.window(tag="main"):
    with dpg.child_window(height=-FOOTER - 8):
        for i in range(ROWS):
            with dpg.group(horizontal=True):
                dpg.add_text(label(i, 0), tag=f"row{i}")
                dpg.add_button(label="Open")
    dpg.add_child_window(height=FOOTER, tag="footer")
dpg.bind_item_theme("footer", themes[A])
dpg.create_viewport(title="bench", width=W, height=H, x_pos=0, y_pos=0)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("main", True)
driver = Driver()
last = time.monotonic()
while dpg.is_dearpygui_running():
    if time.monotonic() - last >= TICK:
        last = time.monotonic()
        k = driver.next()
        if k:
            for i in range(ROWS):
                dpg.set_value(f"row{i}", label(i, k))
            dpg.bind_item_theme("footer", themes[color(k)])
    dpg.render_dearpygui_frame()
dpg.destroy_context()
