---
title: Settings
description: "The preferences of Pyzed Design and its code editor: themes, fonts, keys, where settings are saved and how to translate the visual designer."
sidebar:
  order: 13
---

**Settings** (<kbd>Ctrl</kbd>+<kbd>,</kbd>, the gear at the right of the title bar, or the ☰ menu) holds the
editor's own preferences. Changes apply at once and are saved right away; **Done** closes the dialog.

![The settings dialog](../../../assets/editor/settings.png)

## Appearance

| Setting | What it does |
| --- | --- |
| **Theme** | The editor's theme (One Dark, One Light, Ayu, Gruvbox...). Forms keep their own theme. |
| **Language** | *System default*, English or Español: the language of the menus and panels. |
| **Toolbar** | Shows or hides the toolbar. |
| **Status bar** | Shows or hides the status bar. |
| **Welcome window** | Opens the [welcome window](/pyzed/editor/examples/) at startup (on by default). |
| **Custom window frame** | On by default: Pyzed Design draws its own title bar and window buttons, in the style of your system. Turn it off to use the system's frame (applies the next time it opens). |
| **Form preview frame** | The window frame the canvas shows around the form: this system's, macOS, Windows 11, GNOME, Ubuntu or KDE Plasma. |

## Form canvas

| Setting | What it does |
| --- | --- |
| **Show grid** | The dot grid on the canvas (also <kbd>G</kbd>). |
| **Snap to grid** | Rounds positions and sizes to the grid. |
| **Smart guides** | Aligns to other controls while dragging. |
| **Show hidden controls** | Draws controls whose Visible is off, dimmed. Off leaves them out of the canvas (they stay in the outline). |
| **Grid size for new forms** | The grid step (2 to 64) given to forms and components you create. Each form then keeps its own in Properties. |

## Running

| Setting | What it does |
| --- | --- |
| **Save before running** | <kbd>F5</kbd> saves the document first. |
| **Open the console on Run** | Brings the console to the front when a form starts. |
| **Log events in the console** | Writes every event the running form handles, with its value and handler. |

## Panels

| Setting | What it does |
| --- | --- |
| **Layout → Reset** | Puts every panel back in its default dock and size. |
| **Code editor → Editor settings…** | The [code editor's settings](/pyzed/editor/code-editor/#editor-settings): font, tabs, cursor, completion, language servers. |
| **Key bindings → Keymap editor…** | The [keymap editor](/pyzed/editor/keymap/): change the keys of any action. |
| **AI agents → AI agents settings…** | The [agent's settings](/pyzed/editor/ai-agents/#settings): model providers, keys and browser sign-in, default model, effort and permissions. |

## Telemetry

The designer can keep usage and performance numbers to help improve it, but only if you turn it on: it is
**off by default**. In **Settings → Telemetry**, *Collect usage and performance data* records:

- how many times each command and editor action is used (`command.save`, `editor.select_next`…);
- how long the designer takes to start, to draw a frame and to run each command (count, total, maximum and a
  histogram);
- the number of sessions and their length.

It never records your code, texts, form or file names, or paths. The data is kept in `telemetry.json` in the
Pyzed config folder; **View** opens it and **Delete** empties it (and changes the random installation id).

Nothing leaves your computer unless you also set an **Endpoint**: then the designer posts the data there as JSON
when it closes, and starts counting again. A send that fails is retried the next time. `PYZED_TELEMETRY=0` turns
telemetry off whatever the settings say.

```json
{"schema": 1, "installation": "4f0c…", "app": "pyzed-designer", "version": "0.4.0", "os": "linux",
 "arch": "x86_64", "python": "3.13", "since": "…", "until": "…", "sessions": 3,
 "counters": {"command.save": 12, "editor.select_next": 7},
 "timings": {"render": {"count": 840, "total_ms": 2210.4, "max_ms": 41.2, "buckets": [690, 120, 25, 5, 0, 0, 0, 0]}}}
```

The `buckets` count durations up to 4, 8, 16, 33, 50, 100 and 250 ms, and longer.

## Where they are saved

Everything the editor remembers goes to one file, `designer.json`, in Pyzed's settings folder:

| Platform | Folder |
| --- | --- |
| Windows | `%APPDATA%\pyzed` |
| macOS | `~/Library/Application Support/pyzed` |
| Linux | `$XDG_CONFIG_HOME/pyzed` or `~/.config/pyzed` |

Set `PYZED_CONFIG_DIR` to use another folder (handy for a portable setup or for tests). The file has two
sections: `"designer"` (theme, language, canvas defaults, toolbar and status bar, run options, recent files, and
where each panel is docked, which docks are hidden and their sizes) and `"editor"` (the code editor). The
[AI agent](/pyzed/editor/ai-agents/) keeps its settings in `agents.json` and its threads in `agents/threads/` in
the same folder; API keys are never written there, they go to the system keychain. Invalid
values are ignored and the defaults used, so a hand-edited file can not break the editor.

```json
{
  "designer": { "theme": "One Light", "language": "es", "grid": 8, "snap": true, "console_on_run": true,
                "docks": { "events": "left" }, "sizes": { "right": 360 }, "recent": ["/home/ada/shop/ui/main.pzform"] },
  "editor": { "font_size": 15, "tab_size": 4, "minimap": false, "cursor_shape": "block", "format_on_apply": true }
}
```

## Translating the editor

The editor's interface is translated with [`pz.t`](/pyzed/guides/i18n/). English and Spanish are built in; add a
catalog under the `designer` key to translate it to another language. The **Language** setting offers the built-in
ones; for another language, let the editor follow the system or set `"language"` in the `designer` section of
`designer.json`.

Missing strings fall back to English, so a partial translation already works.
