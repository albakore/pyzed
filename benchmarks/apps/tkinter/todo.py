"""Reference app: add tasks (button or Enter), tick them off, delete them, see how many are left."""

import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.title("To-do")
root.geometry("420x480")
tasks = []  # [title, BooleanVar]
left = ttk.Label(root, font=("TkDefaultFont", 14))
left.pack(anchor="w", padx=16, pady=(16, 8))
entry_row = ttk.Frame(root)
entry_row.pack(fill="x", padx=16)
draft = tk.StringVar()
entry = ttk.Entry(entry_row, textvariable=draft)
entry.pack(side="left", fill="x", expand=True)
canvas = tk.Canvas(root, highlightthickness=0)
bar = ttk.Scrollbar(root, command=canvas.yview)
canvas.configure(yscrollcommand=bar.set)
bar.pack(side="right", fill="y", pady=12)
canvas.pack(fill="both", expand=True, padx=16, pady=12)
inner = ttk.Frame(canvas)
canvas.create_window((0, 0), window=inner, anchor="nw")
inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))


def refresh():
    for child in inner.winfo_children():
        child.destroy()
    for task in tasks:
        row = ttk.Frame(inner)
        ttk.Checkbutton(row, text=task[0], variable=task[1], command=refresh).pack(side="left")
        ttk.Button(row, text="Delete", command=lambda t=task: (tasks.remove(t), refresh())).pack(side="right")
        row.pack(fill="x", pady=2)
    left.configure(text=f"{sum(not done.get() for _, done in tasks)} left")


def add(_event=None):
    if draft.get().strip():
        tasks.append([draft.get().strip(), tk.BooleanVar(value=False)])
        draft.set("")
        refresh()


ttk.Button(entry_row, text="Add", command=add).pack(side="left", padx=(8, 0))
entry.bind("<Return>", add)
refresh()
root.mainloop()
