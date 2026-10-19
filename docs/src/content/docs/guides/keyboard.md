---
title: Keyboard and shortcuts
description: "Keyboard shortcuts in Pyzed apps: Zed-style key bindings with on_key, and how to show the shortcuts in menus, buttons and the rest of the UI."
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

<kbd>Tab</kbd> and <kbd>Shift</kbd>+<kbd>Tab</kbd> also move the focus between fields when no
widget used them; see [Accessibility](/pyzed/guides/accessibility/#moving-between-fields-with-tab).
:::

## Held keys and key releases

`on_key` fires once per press. For keys that act *while* they are
held, define `on_key_up(self, key)`, which receives each release by name (`"left"`, `"space"`,
`"a"`, without modifiers), or ask at any moment which keys are down:

- `pz.pressed()` returns the keys held right now as a `frozenset` of names.
- `pz.is_pressed("left", "a")` is `True` while any of them is held.

```python
class Game(pz.App):
    def on_key_up(self, key):
        if key == "space":
            self.charging = False

    def tick(self, dt):
        if pz.is_pressed("left", "a"):
            self.x -= 200 * dt
```

Key presses and releases only become messages when the app or one of its windows defines
`on_key` or `on_key_up`, so an app without them does not redraw on every key. `pz.pressed()`
works either way. The [games section](/pyzed/games/#input) shows them in a frame loop, along
with `pyzed.game` helpers such as `axis` and `vector`.

## Showing shortcuts

- `ui.kbd("ctrl-shift-p")` draws the keys. On macOS it uses symbols (⌃⇧P), elsewhere words.
- `ui.button(..., keys="ctrl-s")`, `ui.MenuItem(..., keys=...)`, `ui.PaletteItem(..., keys=...)`
  and `ui.tooltip(..., keys=...)` show the shortcut next to the action.
- Force the style with `pyzed.ui.base.KEY_STYLE = "symbols"` or `"words"`.
