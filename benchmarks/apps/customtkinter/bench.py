"""Bench app: ROWS rows in a CTkScrollableFrame (see ../benchkit.py).

Under Xvfb this app dies with an X error (BadAlloc or BadValue from CreatePixmap) once the
scrollable frame holds more than about 100 rows, so only the 10-row scenario has results.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchkit import FOOTER, H, ROWS, TICK, W, A, Driver, color, hexc, label  # noqa: E402

import customtkinter as ctk  # noqa: E402

root = ctk.CTk()
root.title("bench")
root.geometry(f"{W}x{H}+0+0")
root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)
scroll = ctk.CTkScrollableFrame(root)
scroll.grid(row=0, column=0, sticky="nsew")
labels = []
for i in range(ROWS):
    row = ctk.CTkFrame(scroll, fg_color="transparent")
    text = ctk.CTkLabel(row, text=label(i, 0), anchor="w", width=300)
    text.pack(side="left")
    ctk.CTkButton(row, text="Open", width=80).pack(side="left")
    row.pack(fill="x")
    labels.append(text)
# The footer is created last, so Tk draws it after the rows (the grid keeps it at the bottom).
footer = ctk.CTkFrame(root, height=FOOTER, fg_color=hexc(A), corner_radius=0)
footer.grid(row=1, column=0, sticky="ew")
driver = Driver()


def tick():
    k = driver.next()
    if k:
        for i, text in enumerate(labels):
            text.configure(text=label(i, k))
        footer.configure(fg_color=hexc(color(k)))
    root.after(int(TICK * 1000), tick)


root.after(int(TICK * 1000), tick)
root.mainloop()
