"""Reference app: add tasks (button or Enter), tick them off, delete them, see how many are left."""

import flet as ft


def main(page: ft.Page):
    page.title = "To-do"
    page.window.width, page.window.height = 420, 480
    tasks = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
    left = ft.Text("0 left", size=18, weight=ft.FontWeight.BOLD)

    def refresh(_=None):
        left.value = f"{sum(not row.controls[0].value for row in tasks.controls)} left"
        page.update()

    def remove(row):
        tasks.controls.remove(row)
        refresh()

    def add(_):
        if entry.value.strip():
            row = ft.Row([ft.Checkbox(label=entry.value.strip(), on_change=refresh, expand=True)])
            row.controls.append(ft.IconButton(ft.Icons.DELETE, on_click=lambda e: remove(row)))
            tasks.controls.append(row)
            entry.value = ""
            refresh()

    entry = ft.TextField(expand=True, on_submit=add)
    page.add(left, ft.Row([entry, ft.Button("Add", on_click=add)]), tasks)


ft.run(main)
