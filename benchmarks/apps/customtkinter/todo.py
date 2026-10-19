"""Reference app: add tasks (button or Enter), tick them off, delete them, see how many are left."""

import customtkinter as ctk

root = ctk.CTk()
root.title("To-do")
root.geometry("420x480")
tasks = []  # [title, BooleanVar]
left = ctk.CTkLabel(root, font=ctk.CTkFont(size=16, weight="bold"))
left.pack(anchor="w", padx=16, pady=(16, 8))
entry_row = ctk.CTkFrame(root, fg_color="transparent")
entry_row.pack(fill="x", padx=16)
entry = ctk.CTkEntry(entry_row)
entry.pack(side="left", fill="x", expand=True)
inner = ctk.CTkScrollableFrame(root)
inner.pack(fill="both", expand=True, padx=16, pady=12)


def refresh():
    for child in inner.winfo_children():
        child.destroy()
    for task in tasks:
        row = ctk.CTkFrame(inner, fg_color="transparent")
        ctk.CTkCheckBox(row, text=task[0], variable=task[1], command=refresh).pack(side="left")
        ctk.CTkButton(row, text="Delete", width=60, command=lambda t=task: (tasks.remove(t), refresh())).pack(
            side="right")
        row.pack(fill="x", pady=2)
    left.configure(text=f"{sum(not done.get() for _, done in tasks)} left")


def add(_event=None):
    if entry.get().strip():
        tasks.append([entry.get().strip(), ctk.BooleanVar(value=False)])
        entry.delete(0, "end")
        refresh()


ctk.CTkButton(entry_row, text="Add", width=60, command=add).pack(side="left", padx=(8, 0))
entry.bind("<Return>", add)
refresh()
root.mainloop()
