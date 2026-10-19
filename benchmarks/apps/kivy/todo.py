"""Reference app: add tasks (button or Enter), tick them off, delete them, see how many are left."""

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

KV = """
<TaskRow>:
    size_hint_y: None
    height: 40
    CheckBox:
        size_hint_x: None
        width: 40
        active: root.done
        on_active: app.toggle(root.index, self.active)
    Label:
        text: root.title
        color: (.5, .5, .5, 1) if root.done else (1, 1, 1, 1)
        text_size: self.size
        valign: "middle"
    Button:
        text: "Delete"
        size_hint_x: None
        width: 80
        on_press: app.remove(root.index)

BoxLayout:
    orientation: "vertical"
    padding: 16
    spacing: 12
    Label:
        text: f"{app.left} left"
        size_hint_y: None
        height: 32
        font_size: 20
    BoxLayout:
        size_hint_y: None
        height: 40
        spacing: 8
        TextInput:
            id: entry
            multiline: False
            on_text_validate: app.add(self)
        Button:
            text: "Add"
            size_hint_x: None
            width: 80
            on_press: app.add(entry)
    RecycleView:
        data: app.rows
        viewclass: "TaskRow"
        RecycleBoxLayout:
            orientation: "vertical"
            size_hint_y: None
            height: self.minimum_height
            default_size_hint: 1, None
            default_size: None, 40
"""


class TaskRow(BoxLayout):
    index = NumericProperty(0)
    title = StringProperty("")
    done = BooleanProperty(False)


class TodoApp(App):
    title = "To-do"
    rows = ListProperty([])
    left = NumericProperty(0)

    def build(self):
        return Builder.load_string(KV)

    def refresh(self):
        self.rows = [{**row, "index": i} for i, row in enumerate(self.rows)]
        self.left = sum(not row["done"] for row in self.rows)

    def add(self, entry):
        if entry.text.strip():
            self.rows.append({"title": entry.text.strip(), "done": False})
            entry.text = ""
            self.refresh()

    def toggle(self, index, done):
        self.rows[index]["done"] = done
        self.refresh()

    def remove(self, index):
        del self.rows[index]
        self.refresh()


TodoApp().run()
