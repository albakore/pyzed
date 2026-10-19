---
title: Commands and tasks
description: Focusing fields, closing the app, editing the editor, background work and messages from threads.
sidebar:
  order: 4
---

A [`Command`](/pyzed/reference/command/) is an effect the runtime carries out for you. Return it
from `update`, `on_start`, `on_key` or any callback.

```python
from pyzed import Command
```

| Command | Effect |
| --- | --- |
| `Command.focus(id)` | Focuses the field with that `id`. |
| `Command.exit()` | Closes the application. |
| `Command.set_editor_text(id, text)` | Replaces an editor's text. |
| `Command.set_editor_cursor(id, line, col)` | Moves an editor's cursor (1-based). |
| `Command.scroll_to_end(id)` | Scrolls a `scrollable` to the end. |
| `Command.scroll_to(id, x, y)` | Scrolls a `scrollable` to a position in pixels. |
| `Command.copy(text)` | Copies to the clipboard. |
| `Command.paste(then)` | Reads the clipboard and calls `then(text)`. |
| `Command.paste_image(then)` | Reads an image from the clipboard and calls `then(png)` with its PNG bytes (`None` if there is none). |
| `Command.pick_files(then, ...)` | Opens the system's file dialog and calls `then(paths)`; `filters=[("Images", ["png", "jpg"])]`, `multiple=False`, `folder=True`. |
| `Command.message(msg)` | Sends `msg` to `update` on the next cycle. |
| `Command.perform(fn, then)` | Runs `fn()` in the background (a thread, or the asyncio loop if it is `async def`) and passes the result to `then`. |
| `Command.batch([...])` | Several at once (returning a list works too). |
| `Command.open_window(w)`, `close_window`, `drag_window`… | Control windows. See [multiple windows](/pyzed/guides/windows/#window-commands). |

## Focusing a field

```python
def open_search(self):
    self.searching = True
    return Command.focus("search")

def view(self):
    return ui.input(self.query, self.set_query, id="search") if self.searching else ...
```

## Background work

`Command.perform` runs a slow function in the background so the interface doesn't freeze and,
when it finishes, calls `then(result)` on the UI thread. If the function is `async def`, it runs
on Pyzed's asyncio loop; if it returns a generator, `then` is called with each value. For async
code you can also return the coroutine directly: see
[async and subscriptions](/pyzed/guides/async/).

```python
import json
import urllib.request


class Repos(pz.App):
    def __init__(self):
        self.repos, self.loading = [], False

    def on_start(self):
        return self.load()

    def load(self):
        self.loading = True
        return Command.perform(self.download, self.received)

    @staticmethod
    def download():
        with urllib.request.urlopen("https://api.github.com/users/albakore/repos") as r:
            return json.load(r)

    def received(self, repos):
        self.repos, self.loading = repos, False

    def view(self):
        if self.loading:
            return pz.center(ui.muted("Loading…"))
        return pz.column([ui.list_item(r["name"], icon="book") for r in self.repos], padding=8)
```

If `fn` raises an exception, it is printed and `then` is not called. Catch it inside `fn` and
return an error value if you want to show it.

## Messages from other threads

`pz.post(message)` sends a message to the app from **any thread**. Use it for progress,
long-running processes, sockets or timers:

```python
import subprocess
import threading


class Build(pz.App):
    def __init__(self):
        self.lines = []

    def update(self, message):
        kind, value = message
        if kind == "line":
            self.lines.append(value)
            return Command.scroll_to_end("log")

    def build(self):
        def worker():
            proc = subprocess.Popen(["cargo", "build"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                pz.post(("line", line.rstrip()))
        threading.Thread(target=worker, daemon=True).start()

    def view(self):
        return pz.column([
            ui.button("Build", self.build, variant="solid"),
            ui.terminal(self.lines, id="log"),
        ], spacing=8, padding=12)
```

`pz.post` raises `RuntimeError` if no app is running. The GIL is released while the event loop
runs, so your threads make progress normally.

## Closing the app

```python
def on_key(self, combo):
    if combo == "ctrl-q":
        return Command.exit()
```
