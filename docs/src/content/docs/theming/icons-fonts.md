---
title: Icons and fonts
description: "Use about 2000 bundled Lucide icons and file-type icons in Python desktop GUIs with Pyzed, and load your own fonts such as IBM Plex."
sidebar:
  order: 3
---

## Icons

Pyzed bundles the [Lucide](https://lucide.dev) icon font (~2000 icons, ISC license).

```python
pz.icon("folder", size=16, color="#74ade8")
ui.button("Open", self.open, icon="folder-open")
ui.list_item("Settings", self.settings, icon="settings")
```

Look up names at [lucide.dev/icons](https://lucide.dev/icons) or from the terminal:

```bash
pyzed icons git
# git-branch, git-commit-horizontal, git-compare, git-fork, git-merge, git-pull-request, ...
```

`pyzed.icons.names()` returns the full list and `pyzed.icons.glyph("folder")` the character,
to mix it with text using `font="icons"`.

### Searching and picking icons

`icons.search` finds icons by name and by Lucide's tags, best first, and `icons.category` groups them for browsing:

```python
from pyzed import icons

icons.search("person")      # ["person-standing", "user", "contact", ...]
icons.category("arrows")    # every arrow, chevron, undo...
```

To let the user choose one, use [`ui.IconPicker`](/pyzed/library/icon-picker/), or `ui.icon_picker_dialog` in a
`ui.dialog_layer`: a search box, categories and a grid of every icon.

### File-type icons

```python
from pyzed import icons

icons.for_file("main.rs")       # ("file-code", "#dea584")
icons.for_file("Cargo.toml")    # ("file-cog", "#9c4221")
icons.language_for("main.py")   # "Python"
```

`ui.Tab.for_file` and `ui.tree` already use them.

## Fonts

Bundled fonts:

| Name | Font |
| --- | --- |
| `"sans"` (default) | IBM Plex Sans |
| `"mono"` | IBM Plex Mono |
| `"icons"` | Lucide |

To use another one, load it before running the app and refer to it by its family name:

```python
pz.load_font("fonts/JetBrainsMono-Regular.ttf")

pz.text("fn main() {}", font="JetBrains Mono")
pz.code_editor("buf", text, font="JetBrains Mono")
```

`load_font` also accepts the file's `bytes`.
