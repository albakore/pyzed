"""Reference app: a counter with -, + and Reset."""

import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.title("Counter")
root.geometry("320x200")
count = tk.IntVar(value=0)
frame = ttk.Frame(root)
frame.place(relx=0.5, rely=0.5, anchor="center")
ttk.Label(frame, textvariable=count, font=("TkDefaultFont", 24)).pack(pady=8)
buttons = ttk.Frame(frame)
buttons.pack()
ttk.Button(buttons, text="-", command=lambda: count.set(count.get() - 1)).pack(side="left", padx=4)
ttk.Button(buttons, text="+", command=lambda: count.set(count.get() + 1)).pack(side="left", padx=4)
ttk.Button(buttons, text="Reset", command=lambda: count.set(0)).pack(side="left", padx=4)
root.mainloop()
