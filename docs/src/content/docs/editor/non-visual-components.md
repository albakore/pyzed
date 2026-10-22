---
title: Non-visual components
description: "Timers, keyboard shortcuts, file watchers, processes, background workers, web requests, the clipboard, settings, file dialogs, notifications, system information, the launcher and network and battery monitors in Pyzed Design: components with properties and events that draw nothing."
sidebar:
  order: 6.2
---

Some parts of an app have **properties and events but nothing to show**: a timer that ticks, a folder you watch,
a command running in the background. Visual Basic and Qt Designer kept them in a **tray under the form**, and Pyzed
Design does the same. They are not drawn on the form, neither while you design nor when it runs: they only appear
in the tray and in the **Outline**, where they belong to the form.

![Adding a Timer, a File watcher and a Web request from the toolbox: each one goes to the tray under the form, and a double click opens its tick handler](/pyzed/media/services/tray.webp)

## Adding one

1. Find it in the toolbox, under **Components** or **System** (or type its name in **Search components…**).
2. **Click it**: it goes straight to the tray, selected, with its properties on the right. Dragging it onto the
   form does the same; it never lands inside a container.
3. Set its properties in the **Properties** panel, and **double-click** its chip to write the handler of its main
   event (`tick` for a timer, `output` for a process...). The **Events** panel lists all of them.

| In the tray | Result |
| --- | --- |
| Click a chip | Selects the component. |
| Double-click a chip | Opens the handler of its main event. |
| Right-click a chip | View code, Help, Cut, Copy, Duplicate, Enable or Disable, Delete. |

In the **Outline**, non-visual components are listed after the controls, under **Non-visual**. They have no
position, size, style or animations: only their own properties and **Enabled** (a disabled component raises no
events). Copy, paste, undo and rename work as with any control, and renaming one renames its handlers.

## The components

| Component | What it does | Events |
| --- | --- | --- |
| **Timer** | Runs `tick` every `interval` milliseconds while `running`. Turn off `repeat` to tick once (a delay). | `tick` (the count) |
| **Shortcut** | A keyboard shortcut for the whole window: `keys` such as `ctrl-s`, several separated by commas. `mod-s` is <kbd>Cmd</kbd>+<kbd>S</kbd> on macOS and <kbd>Ctrl</kbd>+<kbd>S</kbd> elsewhere. | `activate` (the combo) |
| **File watcher** | Watches a folder (`path`), the files that match `pattern` (`*.csv`, several separated by `;`), with `recursive` for subfolders. | `change` (the changed paths), `created`, `modified`, `deleted` (one path) |
| **Process** | Runs `command` in `directory` and streams what it prints, line by line. `autostart` starts it when the form opens. | `output`, `error_output` (a line), `finished` (exit code), `started` (process id), `failed` |
| **Background worker** | Runs slow work in a thread so the window stays responsive. | `work` (in the thread), `progress`, `done` (the result), `failed` (the exception) |
| **Web request** | Calls `url` with `method`, `headers` (one `Name: value` per line) and `body`, in the background. | `response` (the answer), `failed` (no answer) |
| **Clipboard** | Copies and pastes text; with `watch` it notices what is copied, in this app or another one. | `change`, `paste` (the text) |
| **Settings** | Values kept between runs (a JSON file per user), and the value of the controls listed in `remember`. | `change` (`(key, value)`) |
| **File dialog** | The system's dialog: `mode` is `open`, `open_many`, `save` or `folder`; `filters` has one `Images: png, jpg` per line. | `chosen` (the path, or a list), `cancelled` |
| **Notification** | A desktop notification with `title` and `text`. | `shown`, `failed` |
| **System info** | The computer: `os`, `os_version`, `machine`, `hostname`, `user`, `home`, `cpu_count`, `language`, memory and free disk (of `disk_path`). With `interval` it checks again periodically. | `update` (a dict with all of it) |
| **Launcher** | Opens `target` with the program the system uses for it: a file, a folder, a web page or a `mailto:` link. | `opened`, `failed` (the target) |
| **Network monitor** | Whether the internet can be reached, checking `host`:`port` every `interval` ms while `running`. | `change` (`True`/`False`), `online`, `offline` |
| **Battery monitor** | The battery's charge and whether it is plugged in, every `interval` ms. | `change` (`(percent, plugged)`), `low` (under `low_level`), `plugged`, `unplugged` |

Each component's page in the built-in reference (<kbd>Shift</kbd>+<kbd>F1</kbd> with it selected) lists every
property and event with its handler name.

## Using them from the handlers

They are attributes of the form like any control. Their properties read and write as attributes, and they have
**methods**:

```python
def run_click(form, event):
    if form.proc.running:
        form.proc.kill()
    else:
        form.proc.start(form.command.text)     # or the command set in the designer


def proc_output(form, event):
    form.output.text += event.value + "\n"     # one line of what the program printed


def proc_finished(form, event):
    form.status.text = "Done." if event.value == 0 else f"It ended with code {event.value}."
```

| Component | Methods and state |
| --- | --- |
| Timer | `start()`, `stop()`, `running`, `count` |
| Shortcut | `matches(combo)` |
| File watcher | `start()`, `stop()`, `running`, `check()` |
| Process | `start(command=None)`, `write(text)`, `kill()`, `running`, `exit_code`, `pid` |
| Background worker | `run(value)`, `cancel()`, `report(progress)`, `busy`, `cancelled`, `result` |
| Web request | `send(url=None, json=None, body=None)`, `busy`, `response` |
| Clipboard | `copy(text)` and `paste()` (commands: return them), `text` |
| Settings | `settings1["key"]`, `settings1["key"] = value`, `get(key, default)`, `set()`, `delete()`, `keys()` |
| File dialog | `show()` (a command: return it), `path`, `paths` |
| Notification | `show(text=None)` |
| System info | `check()`, `env(name)`, `folder("documents")`, `memory_available`, `disk_free`, `is_windows`, `is_mac`, `is_linux` |
| Launcher | `open(target=None)`, `reveal(path)` (shows it in the file manager), `email(to, subject, body)` |
| Network monitor | `check()`, `online`, `start()`, `stop()` |
| Battery monitor | `check()`, `percent`, `plugged`, `has_battery` |

Events that happen in the background (a line of output, a file that changed, a web answer) reach your handlers on
the window's thread, so handlers can change controls freely. The one exception is the worker's `work` event:

```python
def count_click(form, event):
    form.primes.run(200_000)                   # starts work in a thread


def primes_work(form, event):                  # runs in the thread: do not touch controls here
    found = 0
    for n in range(2, event.value):
        if event.sender.cancelled:             # form.primes.cancel() was called
            return None
        if all(n % d for d in range(2, int(n ** 0.5) + 1)):
            found += 1
        if n % 2000 == 0:
            event.sender.report(n * 100 // event.value)
    return found                               # arrives in done


def primes_progress(form, event):
    form.progress.value = event.value


def primes_done(form, event):
    form.status.text = f"{event.value:,} primes"
```

Commands are returned, as in every handler:

```python
def open_click(form, event):
    return form.file_dialog1.show()            # opens the system's dialog


def file_dialog1_chosen(form, event):
    form.editor.text = Path(event.value).read_text()


def copy_click(form, event):
    return form.clipboard1.copy(form.editor.text)


def http1_response(form, event):
    if event.value.ok:
        form.stars.text = str(event.value.json()["stargazers_count"])
```

![The Task runner example running: the process streams its output, the timer moves the clock and the worker fills the progress bar](/pyzed/media/services/runner.webp)

The **Task runner** example (`examples/designer/tasks.pzform`) uses seven of them together: a Timer for the clock,
a Process for the command, a Background worker that counts primes, a File watcher, Settings that remember the
command, a Shortcut (<kbd>Ctrl</kbd>+<kbd>R</kbd>) and a Notification. Open it with
`pyzed design examples/designer/tasks.pzform`.

## Remembering what the user left

Put a **Settings** component on the form and list control names in **Remember**, one per line: when the form
closes their values (the text of a text box, the state of a check box, a slider's value...) are saved, and the next
time it opens they are back. The file is `<form>.<component>.json` in Pyzed's per-user settings folder, or the
name in **File**. Your own values go in the same file:

```python
def form_load(form, event):
    form.volume.value = form.prefs.get("volume", 50)


def volume_change(form, event):
    form.prefs["volume"] = event.value
```

## In code, without the designer

Each component is a class of [`pyzed.services`](/pyzed/guides/services/) (`pz.Timer`, `pz.Process`,
`pz.FileWatcher`...), so the same objects work in a `pz.App` written by hand, or in a script with no window.

:::tip
A busy **Process** or **File watcher** can flood the console with events: `output`, `error_output`, `progress` and
`tick` are never logged, and **Settings → Running** turns event logging off for the rest.
:::
