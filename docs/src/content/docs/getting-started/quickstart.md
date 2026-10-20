---
title: Quickstart
description: "Your first native Python desktop window with Pyzed in five minutes: install the package, write a small counter app and run it anywhere."
---

## 1. A window

```python title="hello.py"
import pyzed as pz


class Hello(pz.App):
    title = "Hello"
    size = (400, 240)

    def view(self):
        return pz.center(pz.text("Hello, Pyzed", size=24))


pz.run(Hello)
```

```bash
python hello.py
```

An app is a class that inherits from `pz.App`. Its `view()` method returns the widgets that are shown.
`pz.run()` opens the window and blocks until it is closed.

## 2. State and messages

State lives in your object. Interactive widgets take a **message**: any Python
value. When the user clicks the button, Pyzed calls `update(message)` and redraws.

```python title="counter.py"
import pyzed as pz
from pyzed import ui


class Counter(pz.App):
    title = "Counter"
    size = (360, 220)

    def __init__(self):
        self.count = 0

    def update(self, message):
        if message == "increment":
            self.count += 1
        elif message == "decrement":
            self.count -= 1

    def view(self):
        return pz.center(
            pz.column([
                ui.heading(str(self.count)),
                pz.row([
                    ui.button("1", "decrement", icon="minus"),
                    ui.button("1", "increment", icon="plus", variant="solid"),
                    ui.icon_button("rotate-ccw", lambda: setattr(self, "count", 0), tooltip="Reset"),
                ], spacing=8),
            ], spacing=16, align="center"),
            bg=self.resolved_theme().editor,
        )


pz.run(Counter)
```

![The counter](../../../../screenshots/counter.png)

## 3. Callables instead of messages

If the message is a callable (a lambda or a method), Pyzed **calls it directly** and skips
`update`. For small apps this is usually the most convenient:

```python
ui.button("Save", self.save)                  # calls self.save()
ui.button("Delete", lambda: self.delete(id))  # with arguments
```

Controls that produce a value (`on_input`, `on_toggle`, `on_change`…) call the callable
with that value:

```python
ui.input(self.name, lambda text: setattr(self, "name", text), placeholder="Your name")
```

## 4. Components and themes

`pyzed.ui` ships ready-made Zed-style components. They all read the current theme:

```python
class MyApp(pz.App):
    theme = pz.themes.ONE_LIGHT

    def toggle_theme(self):
        self.theme = "One Light" if self.resolved_theme().is_dark else "One Dark"
```

## Next

- [Create a project with `pyzed new`](/pyzed/getting-started/new-project/)
- [Tutorial: to-do list](/pyzed/tutorials/basic/todo-app/)
- [Architecture guide](/pyzed/guides/architecture/)
