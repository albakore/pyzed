"""Reference app: add tasks (button or Enter), tick them off, delete them, see how many are left."""

import dearpygui.dearpygui as dpg

dpg.create_context()
tasks = []  # [title, done]


def refresh():
    dpg.delete_item("list", children_only=True)
    for task in tasks:
        with dpg.group(horizontal=True, parent="list"):
            dpg.add_checkbox(label=task[0], default_value=task[1],
                             callback=lambda s, value, t=task: (t.__setitem__(1, value), refresh()))
            dpg.add_button(label="Delete", callback=lambda s, a, t=task: (tasks.remove(t), refresh()))
    dpg.set_value("left", f"{sum(not done for _, done in tasks)} left")


def add():
    text = dpg.get_value("entry").strip()
    if text:
        tasks.append([text, False])
        dpg.set_value("entry", "")
        refresh()


with dpg.window(tag="main"):
    dpg.add_text("0 left", tag="left")
    with dpg.group(horizontal=True):
        dpg.add_input_text(tag="entry", width=300, on_enter=True, callback=add)
        dpg.add_button(label="Add", callback=add)
    dpg.add_child_window(tag="list")
dpg.create_viewport(title="To-do", width=420, height=480)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.set_primary_window("main", True)
dpg.start_dearpygui()
dpg.destroy_context()
