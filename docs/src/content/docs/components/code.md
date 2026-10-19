---
title: Code
description: The code editor with syntax highlighting and git markers, and the terminal view.
sidebar:
  order: 7
---

:::tip[Component library]
Every component now has its own page, with a live preview, examples and its full API, in the
[component library](/pyzed/library/). This page is kept as a summary.
:::

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

### Editing like Zed

![Folded blocks, code lens and the minimap](../../../assets/components/editor-features.png)

```python
ui.editor(
    "app.py", code, path="app.py",
    minimap=True,                  # or a width in pixels
    cursor_shape="block",          # "bar" (default), "block", "underline", "hollow"
    on_zoom=self.zoom,             # 1, -1 or 0 from Ctrl+= / Ctrl+- / Ctrl+0 and Ctrl+wheel
    font_size=self.font_size,
)

def zoom(self, step):
    self.font_size = 14 if step == 0 else self.font_size + step
```

- **Auto-closing pairs** (`auto_close=True`, the default). Typing `(`, `[`, `{`, `"`, `'` or `` ` ``
  also inserts its closing pair and leaves the cursor in between. With a selection, the pair wraps
  it. Typing a closer that is already next steps over it, <kbd>Backspace</kbd> inside an empty pair
  deletes both, and <kbd>Enter</kbd> between brackets opens an indented line. Quotes are not paired
  inside words (`don't`), but they are after a string prefix (`f"`, `rb'`).
- **Folding** (`folding=True`, the default). Blocks fold by indentation: hover the gutter to see
  the chevrons, and click one to fold its block. A folded line ends in `⋯` (click it to unfold).
  <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>[</kbd> folds the innermost block around the cursor and
  <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>]</kbd> unfolds it. `Command.fold_line(id, line)` and
  `Command.fold_all(id)` do it from code. Line numbers, `markers`, `annotations`, `on_change`,
  `on_cursor` and `set_editor_cursor` keep using real lines; editing a folded line or moving the
  cursor into a fold unfolds it.
- **Minimap.** `minimap=True` draws the code zoomed out on the right with the visible area
  highlighted; click to jump, drag to scroll, or use the wheel over it.
- **Font zoom.** The editor reports <kbd>Ctrl</kbd>+<kbd>=</kbd>, <kbd>Ctrl</kbd>+<kbd>-</kbd>,
  <kbd>Ctrl</kbd>+<kbd>0</kbd> and <kbd>Ctrl</kbd>+wheel to `on_zoom`; change `font_size` in response.
- **Cursor.** `cursor_shape`, `cursor_blink`, `cursor_width` (of the bar) and `cursor_color` (the
  theme's player color by default), like Zed's `cursor_shape` setting.

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
