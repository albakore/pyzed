---
title: Code
description: "A code editor with syntax highlighting and git markers, and a terminal view: Zed-style components for Python desktop apps built with Pyzed."
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

### Multiple cursors and Zed's keys

![Three cursors and the search results for prices](../../../assets/components/editor-multicursor.png)

The editor uses Zed's default keys (Linux and Windows; <kbd>Cmd</kbd> instead of <kbd>Ctrl</kbd> on macOS):

| Keys | Action |
| --- | --- |
| <kbd>Alt</kbd>+click | Add a cursor (or remove the one under the click) |
| <kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>↑</kbd> / <kbd>↓</kbd> | Add a cursor above / below |
| <kbd>Ctrl</kbd>+<kbd>D</kbd> | Select the word under the cursor, then add the next match as a cursor |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>L</kbd> | Select every match |
| <kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>I</kbd> | One cursor on each line of the selection |
| <kbd>Ctrl</kbd>+<kbd>U</kbd> | Undo the last cursor change |
| <kbd>Esc</kbd> | Back to one cursor, then drop the selection |
| <kbd>Ctrl</kbd>+<kbd>Z</kbd>, <kbd>Ctrl</kbd>+<kbd>Y</kbd> or <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd> | Undo and redo (consecutive typing is one step) |
| <kbd>Alt</kbd>+<kbd>↑</kbd> / <kbd>↓</kbd> | Move the lines up / down |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>↑</kbd> / <kbd>↓</kbd> | Duplicate the lines |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>K</kbd> | Delete the lines |
| <kbd>Ctrl</kbd>+<kbd>L</kbd> | Select the line (again: the next one too) |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>J</kbd> | Join lines |
| <kbd>Ctrl</kbd>+<kbd>Enter</kbd> / <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Enter</kbd> | New line below / above, indented |
| <kbd>Ctrl</kbd>+<kbd>]</kbd> / <kbd>Ctrl</kbd>+<kbd>[</kbd>, <kbd>Shift</kbd>+<kbd>Tab</kbd> | Indent / outdent (<kbd>Tab</kbd> indents a selection of several lines) |
| <kbd>Ctrl</kbd>+<kbd>/</kbd> | Toggle line comments (`#`, `//` or `--`, from `language`) |
| <kbd>Ctrl</kbd>+<kbd>M</kbd> | Jump to the matching (or enclosing) bracket |
| <kbd>Ctrl</kbd>+<kbd>Backspace</kbd> / <kbd>Ctrl</kbd>+<kbd>Delete</kbd> | Delete the word before / after |
| <kbd>Home</kbd> | First non-blank character, then the start of the line |
| <kbd>Ctrl</kbd>+<kbd>↑</kbd> / <kbd>↓</kbd> | Scroll one line without moving the cursor |
| <kbd>Ctrl</kbd>+<kbd>C</kbd> / <kbd>Ctrl</kbd>+<kbd>X</kbd> | Without a selection, copy / cut the whole line; with several cursors, every cursor's text |
| <kbd>Ctrl</kbd>+<kbd>K</kbd> <kbd>Ctrl</kbd>+<kbd>0</kbd> / <kbd>Ctrl</kbd>+<kbd>J</kbd> / <kbd>Ctrl</kbd>+<kbd>L</kbd> | Fold everything / unfold everything / toggle the fold at the cursor |

Typing, deleting and moving apply to every cursor. Pasting text with one line per cursor gives each
cursor its line, as in Zed. The bracket next to the cursor and its match are outlined
(`match_brackets`), and selecting text highlights its other occurrences (`selection_highlight`).

Every action has a name (Zed's, in snake case). `on_action(name)` is called after each one runs,
`Command.editor_action(id, name)` runs one from code (a menu, a command palette) and
`Command.editor_actions()` lists them:

```python
ui.editor("main.py", code, path="main.py", on_action=self.ran,
          highlights=self.found)       # [(line, column, end_line, end_column)], 1-based

def comment(self):
    return pz.Command.editor_action("main.py", "toggle_comments")

def select_matches(self):
    # One cursor per range; the first one is the primary cursor.
    return pz.Command.select_editor_ranges("main.py", self.found)

def replace_all(self):
    # One undo step; on_change gets the new text.
    return pz.Command.replace_editor_ranges("main.py", [(r, "total") for r in self.found])
```

Names include `undo`, `redo`, `add_selection_above`, `add_selection_below`, `select_next`,
`select_previous`, `select_all_matches`, `split_selection_into_lines`, `undo_selection`, `cancel`,
`move_line_up`, `move_line_down`, `duplicate_line_up`, `duplicate_line_down`, `delete_line`,
`newline_above`, `newline_below`, `indent`, `outdent`, `select_line`, `join_lines`, `toggle_comments`,
`move_to_enclosing_bracket`, `convert_to_upper_case`, `convert_to_lower_case` and
`sort_lines_case_sensitive`.

### Input methods

Chinese, Japanese, Korean and other languages typed through an input method (IME) work in the editor.
While you compose, the IME's text is drawn in a box at the cursor and the caret is hidden; the committed text goes in at every cursor, and consecutive commits are undone
in one step, like typing. The IME follows the cursor as you move it.

![Composing 你好 with a pinyin input method](../../../assets/components/editor-ime.png)

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
