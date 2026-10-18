---
title: Keyboard and shortcuts
description: Zed-style shortcuts with on_key and how to show them in the UI.
sidebar:
  order: 8
---

Define `on_key(self, combo)` in your app to receive **every** key press, like a global keymap.
`combo` is a Zed-style string:

| Key | `combo` |
| --- | --- |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> | `"ctrl-shift-p"` |
| <kbd>Cmd</kbd>+<kbd>S</kbd> (macOS) / <kbd>Win</kbd>+<kbd>S</kbd> | `"cmd-s"` |
| <kbd>Alt</kbd>+<kbd>Z</kbd> | `"alt-z"` |
| <kbd>Esc</kbd> | `"escape"` |
| Arrows | `"up"`, `"down"`, `"left"`, `"right"` |
| Others | `"enter"`, `"tab"`, `"space"`, `"backspace"`, `"delete"`, `"home"`, `"end"`, `"pageup"`, `"pagedown"`, `"f1"`… |

Modifiers always come in this order: `ctrl-`, `alt-`, `shift-`, `cmd-`. Letters arrive in
lowercase.

```python
KEYMAP = {
    "ctrl-shift-p": "open_palette",
    "ctrl-p": "open_files",
    "ctrl-b": "toggle_left",
    "ctrl-s": "save",
}


class App(pz.App):
    def on_key(self, combo):
        # support Cmd on macOS and Ctrl elsewhere with the same table
        action = KEYMAP.get(combo.replace("cmd-", "ctrl-"))
        if action:
            return getattr(self, action)()
```

`on_key` can return the same things as a callback: `None`, a `Command` or a message for `update`.

:::note
`on_key` also receives keys already handled by a focused field (for example, the letters you
type in an `input`). Only respond to the combos you care about, and check the state when a
shortcut only makes sense in a given context (`if self.palette_open and combo == "escape"`).
:::

## Showing shortcuts

- `ui.kbd("ctrl-shift-p")` draws the keys. On macOS it uses symbols (⌃⇧P), elsewhere words.
- `ui.button(..., keys="ctrl-s")`, `ui.MenuItem(..., keys=...)`, `ui.PaletteItem(..., keys=...)`
  and `ui.tooltip(..., keys=...)` show the shortcut next to the action.
- Force the style with `pyzed.ui.base.KEY_STYLE = "symbols"` or `"words"`.
