---
title: Services
description: "Timers, shortcuts, file watchers, processes, background workers, web requests, the clipboard, settings, file dialogs and notifications for Python desktop apps with Pyzed, with events delivered on the UI thread."
sidebar:
  order: 5.5
---

**Services** are the parts of an app that raise events but draw nothing: `pz.Timer`, `pz.Shortcut`,
`pz.FileWatcher`, `pz.Process`, `pz.Worker`, `pz.HttpRequest`, `pz.Clipboard`, `pz.Settings`, `pz.FileDialog` and
`pz.Notification`. They are the same objects as the [non-visual components](/pyzed/editor/non-visual-components/)
of Pyzed Design, and they work in a `pz.App`, in a form, or in a script with no window at all.

```python
from pathlib import Path

import pyzed as pz
from pyzed import ui


class Inbox(pz.App):
    def __init__(self):
        self.files = sorted(p.name for p in Path("inbox").glob("*"))
        self.watcher = pz.FileWatcher("inbox", on_change=self.refresh)
        self.watcher.start()

    def refresh(self, changed):            # runs on the UI thread
        self.files = sorted(p.name for p in Path("inbox").glob("*"))

    def view(self):
        return pz.column([ui.list_item(name, icon="file-text") for name in self.files], padding=16)


pz.run(Inbox)
```

![A File watcher listing the files created and deleted in a folder](/pyzed/media/services/watcher.webp)

## Handlers and threads

Give handlers as `on_<event>=` keywords, or later with `service.on("event", handler)` (`None` removes one). A
handler with a parameter receives the event's value; one without parameters is just called. Each class lists its
events in `Service.events`.

Watchers, processes, workers and web requests do their work in **background threads**, but their events reach the
handlers on **the app's thread** (through `pz.post`), so a handler can change the app's state and return commands
like any callback. With no app running, in a script or a test, the handler is called right away in the thread that
raised the event.

`service.enabled = False` mutes every event; `stop()` ends what the service is doing.

## The services

| Class | Raises | What to know |
| --- | --- | --- |
| `pz.Timer(interval=1000, repeat=True)` | `tick` (the count) | Milliseconds, like Visual Basic and Qt. Return `timer.subscriptions()` from `App.subscriptions`. `start()`, `stop()`, `running`. |
| `pz.Shortcut("mod-s")` | `activate` (the combo) | Call `shortcut.handle(combo)` from `on_key`. `"Ctrl+S"`, `"ctrl-s, cmd-s"` and `mod-` (Cmd on macOS, Ctrl elsewhere) all work. |
| `pz.FileWatcher(path, pattern="*", recursive=False, interval=500)` | `created`, `modified`, `deleted` (a path), `change` (the list) | Compares file times and sizes every `interval` ms, so it works the same everywhere, network drives included. |
| `pz.Process(command, directory=None, env=None, shell=False)` | `started`, `output`, `error_output` (a line), `finished` (exit code), `failed` | `start()`, `write(text)`, `kill()`, `wait()`, `running`, `exit_code`. A string command is split like a shell would. |
| `pz.Worker(work)` | `progress`, `done` (the result), `failed` (the exception) | `run(value)` calls `work(value)` in a thread; it can `report(progress)` and check `cancelled`. |
| `pz.HttpRequest(url, method="GET", headers=None, body=None, timeout=30)` | `response` (an `HttpResponse`), `failed` | `send()`; `send(json={...})` sends JSON with POST. Error statuses are responses too: check `response.ok`. |
| `pz.Clipboard(watch=False, interval=500)` | `change`, `paste` (the text) | `copy(text)` and `paste()` return commands. With `watch`, return `subscriptions()` from your app. |
| `pz.Settings(name, folder=None, defaults=None)` | `change` (`(key, value)`) | A dict saved as JSON at once (`autosave`), per user, in Pyzed's settings folder. |
| `pz.FileDialog(mode="open", filters=..., directory=None, file_name="")` | `chosen` (path or list), `cancelled` | `show()` returns the command that opens it; modes `open`, `open_many`, `save`, `folder`. |
| `pz.Notification(title, text)` | `shown`, `failed` | `show(text=None)` returns whether it could be shown. |

### A timer and a shortcut

```python
import time

import pyzed as pz


class Clock(pz.App):
    def __init__(self):
        self.now = ""
        self.clock = pz.Timer(1000, on_tick=self.tick)
        self.quit = pz.Shortcut("mod-q", on_activate=lambda: pz.Command.exit())

    def tick(self):
        self.now = time.strftime("%H:%M:%S")

    def subscriptions(self):
        return self.clock.subscriptions()

    def on_key(self, combo):
        return self.quit.handle(combo)

    def view(self):
        return pz.text(self.now, size=48)
```

### A command and its output

```python
self.log = []
self.build = pz.Process("cargo build --release", directory="engine",
                        on_output=self.log.append, on_error_output=self.log.append,
                        on_finished=lambda code: self.done(code == 0))
self.build.start()
```

### Work in the background

```python
def resize_all(paths):
    for i, path in enumerate(paths):
        if worker.cancelled:
            return None
        shrink(path)
        worker.report((i + 1) * 100 // len(paths))
    return len(paths)

worker = pz.Worker(resize_all, on_progress=self.set_progress, on_done=self.finished)
worker.run(photos)
```

### A web API

```python
api = pz.HttpRequest("https://api.github.com/repos/albakore/pyzed", on_response=self.show_stars)
api.send()

def show_stars(self, response):
    if response.ok:
        self.stars = response.json()["stargazers_count"]
```

### Settings and dialogs

```python
prefs = pz.Settings("my-app", defaults={"theme": "One Dark"})
prefs["theme"] = "One Light"          # saved at once
prefs.get("theme")                    # "One Light", next time too

dialog = pz.FileDialog("open", filters="Images: png, jpg", on_chosen=self.load_image)

def open_clicked(self):
    return dialog.show()              # a command: return it
```

## Without a window

Nothing here needs a running app. Scripts and tests can wait for the result:

```python
import pyzed as pz

process = pz.Process(["git", "status", "--short"], on_output=print)
process.start()
process.wait()                        # blocks until it ends; returns the exit code

request = pz.HttpRequest("https://example.com")
request.send()
print(request.wait(10).status)        # 200
```

`Process.wait()`, `Worker.wait()` and `HttpRequest.wait()` block until the work ends (with an optional
`timeout`) and return the exit code, the result or the response.
