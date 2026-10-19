"""Reference app: a counter with -, + and Reset."""

import customtkinter as ctk

root = ctk.CTk()
root.title("Counter")
root.geometry("320x200")
count = ctk.IntVar(value=0)
frame = ctk.CTkFrame(root, fg_color="transparent")
frame.place(relx=0.5, rely=0.5, anchor="center")
ctk.CTkLabel(frame, textvariable=count, font=ctk.CTkFont(size=24)).pack(pady=8)
buttons = ctk.CTkFrame(frame, fg_color="transparent")
buttons.pack()
ctk.CTkButton(buttons, text="-", width=40, command=lambda: count.set(count.get() - 1)).pack(side="left", padx=4)
ctk.CTkButton(buttons, text="+", width=40, command=lambda: count.set(count.get() + 1)).pack(side="left", padx=4)
ctk.CTkButton(buttons, text="Reset", width=60, command=lambda: count.set(0)).pack(side="left", padx=4)
root.mainloop()
