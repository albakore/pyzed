---
title: Code
description: The code editor with syntax highlighting and git markers, and the terminal view.
sidebar:
  order: 7
---

## Editor

![Code editor](../../../assets/components/editor.png)

```python
ui.editor(
    "counter.py",                      # buffer id
    code,                              # initial text
    path="counter.py",                 # infers the language
    markers={6: "modified", 7: "created", 10: "created"},
    on_change=self.changed,            # receives the full text
    on_cursor=self.cursor,             # receives (line, column), 1-based
)
```

- **Uncontrolled.** The text, cursor, selection and undo history live in Rust, tied to the `id`.
  `text` is only used the first time that `id` appears. To replace the content, return
  `Command.set_editor_text(id, text)`.
- **One buffer per file.** Use the path as `id`: when switching tabs, each file keeps its cursor
  and history.
- **Highlighting.** Over 100 languages (syntect / two-face grammars) using the theme's syntax
  colors. The language is inferred from `path` or passed with `language="rs"`.
- **Git markers.** `markers` assigns `"created"`, `"modified"` or `"deleted"` to each line.
- **Cursor.** `Command.set_editor_cursor(id, line, column)` moves the cursor, even before the
  first draw.

```python
def save(self):
    Path(self.active).write_text(self.texts[self.active])
    self.dirty.discard(self.active)

def changed(self, text):
    self.texts[self.active] = text
    self.dirty.add(self.active)
```

- **Long lines.** With `wrap=False` (default) the editor scrolls horizontally and the line
  numbers stay pinned on the left. With `wrap=True` lines wrap and the number appears on the
  first row of each line, as in Zed.
- **Active line.** The cursor line is highlighted and scrolling follows the cursor (also with
  <kbd>PgUp</kbd>/<kbd>PgDn</kbd>).

## Terminal

![Terminal](../../../assets/components/terminal.png)

```python
output = "$ pytest -q\n\x1b[32m24 passed\x1b[0m in 1.21s\n$ "
ui.terminal(output, id="term")
```

It is a **read-only** view that understands ANSI colors and stays scrolled to the bottom.
Feed it the output of a process you run yourself (for example with `subprocess` in a thread and
`pz.post`). It also accepts a list of lines made of `(text, color)` segments, where the color is
an ANSI name (`"green"`, `"red"`, `"dim"`…) or a theme token.

`ui.ansi(text)` converts to segments in case you want to draw them your own way.

Full reference: [Code](/pyzed/reference/ui/#code).
