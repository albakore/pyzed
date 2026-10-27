---
title: Keymap
description: "Change any keyboard shortcut of Pyzed Design, like Zed's keymap: a keymap editor with search and conflicts, and a keymap.json file with contexts."
sidebar:
  order: 12.5
---

Every key in Pyzed Design comes from one keymap, like Zed's: the menus, the command palette, the canvas, the project
tree, the code panel and the code editor itself. You can change any of them, add more keys to an action, take keys
away and put the defaults back, from a window or by editing a file.

## The keymap editor

Open it with **File → Keymap editor**, <kbd>Ctrl</kbd>+<kbd>K</kbd> <kbd>Ctrl</kbd>+<kbd>S</kbd> (press both in
turn), **Settings → Key bindings** or **Editor settings → Key bindings**.

![The keymap editor searching for "save": Save with its default keys and Save as with keys the user changed](../../../assets/editor/keymap-editor.png)

Each row is an action with one of its keys:

- **Action**: its name and the name it has in `keymap.json` (`workspace::SaveAs`).
- **Keys**: the keys that run it, or a dash when it has none.
- **Context**: where the keys work (see [Contexts](#contexts)).
- **Source**: **Default**, or **User** for the keys you set.

Type in the search field to filter by name, keys or context. **Changed** shows only the actions you changed and
**Conflicts** the keys that run two actions in the same place.

### Change keys

1. Click the pencil of a row (or **+** to give the action one more key).
2. Press the new keys. For a chord, press two in turn, such as <kbd>Ctrl</kbd>+<kbd>K</kbd> then <kbd>Ctrl</kbd>+<kbd>G</kbd>.
3. Choose the context if it should work somewhere else.
4. Press <kbd>Enter</kbd> (or the check mark) to save, or <kbd>Escape</kbd> to cancel.

![Recording Ctrl+K Ctrl+G for Go to line in the code panel](../../../assets/editor/keymap-editor-recording.png)

While you record, the line above the list warns you when those keys already run another action in that context.

:::tip
The trash icon takes the keys away, the arrow puts the action's default keys back, and **Reset all** puts back every
default key.
:::

### Conflicts

When the same keys run two actions in the same context, both rows say so. The last binding wins: yours over the
defaults. The row of the action that runs says **Overrides**, and the other says **Shadowed by**.

![Ctrl+D bound to Grid on the canvas, shadowing Duplicate](../../../assets/editor/keymap-editor-conflicts.png)

## Contexts

A context is the part of the designer that has the keyboard. Keys are looked up from the innermost context to
**Workspace**, so the same keys can do different things in different places: <kbd>Ctrl</kbd>+<kbd>N</kbd> is
**New form** anywhere, but **New file** in the project tree.

| Context | Where | Inside |
| --- | --- | --- |
| `Workspace` | Anywhere in the designer | (outermost) |
| `Canvas` | The form canvas, after you click the form or a control | Workspace |
| `ProjectPanel` | The project tree | Workspace |
| `CodePanel` | The code panel: completions, find, go to line, wrapping | Workspace |
| `Editor` | The text of the code editor | CodePanel |

:::note
A chord can start with any key, like Emacs's <kbd>Ctrl</kbd>+<kbd>X</kbd> <kbd>U</kbd>. Inside the editor, the first
key of a chord only waits for the second one: <kbd>Ctrl</kbd>+<kbd>K</kbd> <kbd>Ctrl</kbd>+<kbd>S</kbd> opens the
keymap editor from the code too.
:::

## Base keymaps

Coming from another editor? Like Zed's `base_keymap`, **Settings → Code editor → Keymap and Vim → Base keymap** puts
that editor's keys over the defaults (which are VS Code's and Zed's), and your own bindings still go on top:

| Base keymap | Some of its keys |
| --- | --- |
| **VS Code** (default) | The defaults: <kbd>Ctrl</kbd>+<kbd>D</kbd> next match, <kbd>Alt</kbd>+<kbd>↑</kbd> move line, <kbd>F12</kbd> definition. |
| **JetBrains** | <kbd>Ctrl</kbd>+<kbd>D</kbd> duplicate, <kbd>Ctrl</kbd>+<kbd>Y</kbd> delete line, <kbd>Ctrl</kbd>+<kbd>W</kbd> expand selection, <kbd>Ctrl</kbd>+<kbd>B</kbd> definition, <kbd>Shift</kbd>+<kbd>F6</kbd> rename, <kbd>Alt</kbd>+<kbd>Enter</kbd> quick fixes, <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>L</kbd> format, <kbd>F2</kbd> next problem. |
| **Sublime Text** | <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>D</kbd> duplicate, <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>↑</kbd> move line, <kbd>Ctrl</kbd>+<kbd>J</kbd> join lines, <kbd>Ctrl</kbd>+<kbd>K</kbd> <kbd>Ctrl</kbd>+<kbd>U</kbd> upper case, <kbd>Ctrl</kbd>+<kbd>B</kbd> run. |
| **Atom** | <kbd>Ctrl</kbd>+<kbd>↑</kbd> move line, <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>D</kbd> duplicate, <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>[</kbd> fold. |
| **TextMate** | <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>↑</kbd> move line, <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>L</kbd> select line, <kbd>Ctrl</kbd>+<kbd>R</kbd> run. |
| **Emacs** | <kbd>Ctrl</kbd>+<kbd>F</kbd>/<kbd>B</kbd>/<kbd>N</kbd>/<kbd>P</kbd> move, <kbd>Ctrl</kbd>+<kbd>A</kbd>/<kbd>E</kbd> line start and end, <kbd>Ctrl</kbd>+<kbd>K</kbd> kill line, <kbd>Ctrl</kbd>+<kbd>W</kbd>/<kbd>Alt</kbd>+<kbd>W</kbd>/<kbd>Ctrl</kbd>+<kbd>Y</kbd> cut, copy, yank, <kbd>Ctrl</kbd>+<kbd>Space</kbd> mark, <kbd>Ctrl</kbd>+<kbd>X</kbd> <kbd>U</kbd> undo, <kbd>Ctrl</kbd>+<kbd>X</kbd> <kbd>Ctrl</kbd>+<kbd>S</kbd> save, <kbd>Alt</kbd>+<kbd>X</kbd> command palette. |

The keymap editor and the shortcut reference show the keys of the base keymap in force, and **Reset** puts back its
keys, not VS Code's.

## Vim mode

**Vim mode** (Settings → Code editor → Keymap and Vim, or *Toggle Vim mode* in the command palette) edits like Vim,
as Zed's `vim_mode` does. The status bar shows the mode (`NORMAL`, `-- INSERT --`, `-- VISUAL --`) and the cursor is
a block outside Insert mode.

- **Motions**: `h` `j` `k` `l`, `w` `b` `e` (and `W` `B` `E`), `0` `^` `$`, `gg` `G`, `{` `}`, `%`, `f` `t` `F` `T`
  with `;` and `,`, and counts (`3w`, `5j`).
- **Operators**: `d` `c` `y` `>` `<`, `gc` (comment), `g~` `gu` `gU` (case), doubled for whole lines (`dd`, `cc`,
  `yy`, `gcc`), with motions and text objects: `iw` `aw`, `i"` `a'`, `i(` `ab`, `i{` `aB`, `i[`, `i<`, `ip`.
- **Commands**: `i` `a` `I` `A` `o` `O`, `v` `V`, `x` `X` `s` `S` `D` `C` `Y`, `p` `P`, `u` and <kbd>Ctrl</kbd>+<kbd>R</kbd>,
  `J`, `~`, `r`, `.` (repeat), `*` `#`, `/` `?` `n` `N` (the find bar), `K` (hover card), `gd` (definition),
  <kbd>Ctrl</kbd>+<kbd>O</kbd>/<kbd>I</kbd> (back and forward), <kbd>Ctrl</kbd>+<kbd>D</kbd>/<kbd>U</kbd>/<kbd>F</kbd>/<kbd>B</kbd>,
  `zz`, `zc` `zo` `za` `zM` `zR` (folds).
- **The command line** (`:`): `:w`, `:q`, `:wq` and `:x`, `:42` (go to line), `:s/old/new/g` on the line,
  `:%s/old/new/g` on every line (with `\1` and `&` in the replacement), `:noh`, `:set wrap` and `:set number`.

Yanks and deletes go to the system clipboard, so `p` pastes what you copied in another app too.


## The keymap.json file

Your changes are saved in `keymap.json`, next to the designer's settings:

| System | Folder |
| --- | --- |
| Windows | `%APPDATA%\pyzed` |
| macOS | `~/Library/Application Support/pyzed` |
| Linux | `~/.config/pyzed` (or `$XDG_CONFIG_HOME/pyzed`) |

`PYZED_CONFIG_DIR` changes the folder. **Edit keymap.json** in the keymap editor opens it in the code panel, and it
applies as soon as you save it.

It uses Zed's format: a list of blocks, each with a `context` and its `bindings` from keys to an action. `null` takes
a default key away. Comments (`//`) and trailing commas are allowed.

```json
// Pyzed Design key bindings
[
  {
    "context": "Workspace",
    "bindings": {
      "ctrl-alt-s": "workspace::SaveAs",
      "ctrl-shift-s": null
    }
  },
  {
    "context": "Editor",
    "bindings": {
      "ctrl-alt-d": "editor::DuplicateLineDown",
      "ctrl-d": null
    }
  },
  {
    "context": "Canvas",
    "bindings": {
      "ctrl-k ctrl-g": "workspace::Grid"
    }
  }
]
```

- **Keys** are written like Zed's: modifiers `ctrl`, `alt`, `shift` (`cmd` and `super` count as `ctrl`) joined with `-`
  to a key (`a`, `f2`, `enter`, `space`, `up`, `pageup`...). A chord is two keys separated by a space.
- **Actions** are written `namespace::Action`: `workspace::` for the commands of the menus, `canvas::`,
  `project_panel::`, `code_panel::` and `editor::`. The keymap editor shows each action's name.

:::caution
If the file has a mistake (an unknown action, keys or context), the rest still works and the keymap editor lists the
problems at the top.
:::

In earlier versions, the code editor's keys were saved under `"keymap"` in `designer.json`. The designer moves them
to `keymap.json` the first time it starts.

## In your own apps

The code editor component takes the same kind of keymap: `ui.editor(keymap={"ctrl-alt-d": "duplicate_line_down",
"ctrl-d": None})`. See [the code editor component](/pyzed/components/code/#multiple-cursors-and-zeds-keys).
