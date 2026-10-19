"""Bench app: ROWS rows in a scrolling Column, not a lazy ListView (see ../benchkit.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchkit import FOOTER, H, ROWS, TICK, W, A, Driver, color, hexc, label  # noqa: E402

import asyncio  # noqa: E402

import flet as ft  # noqa: E402


async def main(page: ft.Page):
    driver = Driver()
    page.title = "bench"
    page.window.width, page.window.height = W, H
    page.window.left, page.window.top = 0, 0
    page.padding = 0
    page.spacing = 0
    labels = [ft.Text(label(i, 0), expand=True) for i in range(ROWS)]
    rows = [ft.Row([text, ft.Button("Open")]) for text in labels]
    footer = ft.Container(height=FOOTER, bgcolor=hexc(A), expand=False)
    page.add(ft.Column([ft.Column(rows, scroll=ft.ScrollMode.AUTO, expand=True), footer], expand=True, spacing=0))
    footer.width = W
    page.update()
    while True:
        await asyncio.sleep(TICK)
        k = driver.next()
        if k:
            for i, text in enumerate(labels):
                text.value = label(i, k)
            footer.bgcolor = hexc(color(k))
            page.update()


ft.run(main)
