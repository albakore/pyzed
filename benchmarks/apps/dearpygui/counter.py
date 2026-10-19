"""Reference app: a counter with -, + and Reset."""

import dearpygui.dearpygui as dpg

dpg.create_context()
count = 0


def change(step):
    global count
    count = 0 if step is None else count + step
    dpg.set_value("count", str(count))


with dpg.window(tag="main"):
    dpg.add_text("0", tag="count")
    with dpg.group(horizontal=True):
        dpg.add_button(label="-", callback=lambda: change(-1))
        dpg.add_button(label="+", callback=lambda: change(1))
        dpg.add_button(label="Reset", callback=lambda: change(None))
dpg.create_viewport(title="Counter", width=320, height=200)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("main", True)
dpg.start_dearpygui()
dpg.destroy_context()
