"""Bench app: ROWS rows in a scrollable frame (see ../benchkit.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchkit import FOOTER, H, ROWS, TICK, W, A, Driver, color, hexc, label  # noqa: E402

import tkinter as tk  # noqa: E402

root = tk.Tk()
root.title("bench")
root.geometry(f"{W}x{H}+0+0")
canvas = tk.Canvas(root, highlightthickness=0)
bar = tk.Scrollbar(root, command=canvas.yview)
canvas.configure(yscrollcommand=bar.set)
bar.pack(side="right", fill="y")
canvas.pack(side="left", fill="both", expand=True)
inner = tk.Frame(canvas)
canvas.create_window((0, 0), window=inner, anchor="nw")
inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
labels = []
for i in range(ROWS):
    row = tk.Frame(inner)
    text = tk.Label(row, text=label(i, 0), anchor="w", width=40)
    text.pack(side="left")
    tk.Button(row, text="Open").pack(side="left")
    row.pack(fill="x")
    labels.append(text)
# The footer is created last, so Tk draws it after the rows (it is still packed at the bottom).
footer = tk.Frame(root, height=FOOTER, bg=hexc(A))
footer.pack(side="bottom", fill="x", before=canvas)
driver = Driver()


def tick():
    k = driver.next()
    if k:
        for i, text in enumerate(labels):
            text.configure(text=label(i, k))
        footer.configure(bg=hexc(color(k)))
    root.after(int(TICK * 1000), tick)


root.after(int(TICK * 1000), tick)
root.mainloop()
