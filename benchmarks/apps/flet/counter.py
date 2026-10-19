"""Reference app: a counter with -, + and Reset."""

import flet as ft


def main(page: ft.Page):
    page.title = "Counter"
    page.window.width, page.window.height = 320, 200
    count = ft.Text("0", size=24)

    def change(step):
        count.value = "0" if step is None else str(int(count.value) + step)
        page.update()

    page.add(ft.Column([
        count,
        ft.Row([
            ft.IconButton(ft.Icons.REMOVE, on_click=lambda e: change(-1)),
            ft.IconButton(ft.Icons.ADD, on_click=lambda e: change(1)),
            ft.TextButton("Reset", on_click=lambda e: change(None)),
        ], alignment=ft.MainAxisAlignment.CENTER),
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER))


ft.run(main)
