"""Reference app: a counter with -, + and Reset."""

import toga
from toga.style import Pack


class Counter(toga.App):
    def startup(self):
        self.count = 0
        self.label = toga.Label("0", style=Pack(font_size=24, text_align="center"))
        buttons = toga.Box(children=[
            toga.Button("-", on_press=lambda w: self.change(-1)),
            toga.Button("+", on_press=lambda w: self.change(1)),
            toga.Button("Reset", on_press=lambda w: self.change(None)),
        ], style=Pack(direction="row", gap=8))
        box = toga.Box(children=[self.label, buttons], style=Pack(direction="column", align_items="center", gap=8))
        self.main_window = toga.MainWindow(title="Counter", size=(320, 200))
        self.main_window.content = box
        self.main_window.show()

    def change(self, step):
        self.count = 0 if step is None else self.count + step
        self.label.text = str(self.count)


Counter("Counter", "org.pyzed.counter").main_loop()
