"""Reference app: a counter with -, + and Reset."""

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import NumericProperty

KV = """
AnchorLayout:
    BoxLayout:
        orientation: "vertical"
        size_hint: None, None
        size: 240, 120
        spacing: 8
        Label:
            text: str(app.count)
            font_size: 32
        BoxLayout:
            spacing: 8
            Button:
                text: "-"
                on_press: app.count -= 1
            Button:
                text: "+"
                on_press: app.count += 1
            Button:
                text: "Reset"
                on_press: app.count = 0
"""


class CounterApp(App):
    count = NumericProperty(0)
    title = "Counter"

    def build(self):
        return Builder.load_string(KV)


CounterApp().run()
