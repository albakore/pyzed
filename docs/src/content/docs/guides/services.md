---
title: Services
description: "Timers, shortcuts, file watchers, processes, background workers, web requests, the clipboard, settings, file dialogs, notifications and tray icons for Python desktop apps with Pyzed, with events delivered on the UI thread."
sidebar:
  order: 5.5
---

**Services** are the parts of an app that raise events but draw nothing: `pz.Timer`, `pz.Shortcut`,
`pz.FileWatcher`, `pz.Process`, `pz.Worker`, `pz.HttpRequest`, `pz.Clipboard`, `pz.Settings`, `pz.FileDialog`,
`pz.Notification` and `pz.TrayIcon`. They are the same objects as the [non-visual components](/pyzed/editor/non-visual-components/)
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
| `pz.TrayIcon(icon=None, tooltip="", menu=())` | `click`, `double_click` (Windows), `menu` (the item), `failed` | `show()` returns whether it could; `hide()`. Changes to `icon`, `tooltip` and `menu` show at once. |
| `pz.SystemInfo(interval=0, disk_path=None)` | `update` (a dict) | `os`, `os_version`, `hostname`, `user`, `cpu_count`, `language`, `memory_total`, `memory_available`, `disk_free`; `folder("downloads")`, `env(name)`. |
| `pz.Launcher(target="")` | `opened`, `failed` (the target) | `open(target)` with the system's program (files, folders, links, `mailto:`), `reveal(path)`, `email(to, subject, body)`. |
| `pz.NetworkMonitor(host="1.1.1.1", port=53, interval=5000)` | `change` (bool), `online`, `offline` | Tries a connection every `interval` ms in the background; `online` holds the last answer. |
| `pz.PowerMonitor(interval=30000, low_level=20)` | `change` (`(percent, plugged)`), `low`, `plugged`, `unplugged` | `percent` is `None` on computers without a battery (`has_battery`). |

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

### The operating system

The services of `pyzed.system` (also at the top level: `pz.SystemInfo`, `pz.Launcher`...) read the computer and
open things with the programs the user already has:

```python
info = pz.SystemInfo()
f"{info.os} {info.os_version}, {info.cpu_count} cores"   # "Windows 11, 8 cores"
info.folder("downloads")                                 # the user's Downloads folder
info.disk_free // 2**30                                  # free GB

launcher = pz.Launcher(on_failed=lambda target: print("Could not open", target))
launcher.open("https://example.com")                     # the default browser
launcher.open("report.pdf")                              # the PDF viewer
launcher.reveal("report.pdf")                            # its folder, with the file selected

network = pz.NetworkMonitor(on_offline=lambda: print("Offline"), on_online=lambda: print("Back"))
network.start()
```

For files, `ui.file_input` is a path field with a button that opens the system's dialog, and `ui.DropZone` takes
files dragged from the desktop. A window also gets every dropped file in `on_file_drop(path)` (`on_file_hover` and
`on_file_leave` while they are dragged over it). See the [System](/pyzed/library/drop-zone/) pages of the library.

### An icon in the tray

`pz.TrayIcon` puts an icon in the notification area on Windows, the menu bar on macOS and the panel on Linux, with
a tooltip and a menu. The menu is a list, or text with one item per line: `-` is a separator, `[x]` and `[ ]` make
check items that flip when clicked, and indented lines make a submenu.

```python
self.tray = pz.TrayIcon("icon.png", "Backups", menu="""
Open
[x] Pause
Speed
  Slow
  Fast
-
Quit
""", on_click=self.open, on_menu=self.menu)
self.tray.show()

def menu(self, item):
    if item == "Pause":
        self.paused = self.tray.checked("Pause")
    elif item == "Quit":
        return pz.Command.exit()
```

`pz.TrayItem(text, id=None, enabled=True, checked=None, items=[])` gives an item an `id` (what `on_menu` receives)
or disables it. Without an `icon` it shows a blue dot.

On Linux the icon is a StatusNotifierItem, without GTK: KDE, Cinnamon, XFCE, MATE, LXQt and most panels show it,
and GNOME does with the AppIndicator extension. `pz.TrayIcon.supported()` says whether the desktop shows tray
icons; where it does not, `show()` returns `False` and `failed` says why.

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
