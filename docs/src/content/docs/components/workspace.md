---
title: Workspace
description: The layout of a Zed window, with title bar, docks and status bar.
sidebar:
  order: 5
---

:::tip[Component library]
Every component now has its own page, with a live preview, examples and its full API, in the
[component library](/pyzed/library/). This page is kept as a summary.
:::

`ui.workspace` builds the structure of a Zed window: title bar on top, docks on the left, right
and bottom, the central area and the status bar.

![Workspace](../../../assets/components/workspace.png)

```python
def view(self):
    return ui.workspace(
        pz.column([
            ui.tab_bar([ui.Tab.for_file("src/main.py")], "src/main.py", on_close=self.close),
            ui.editor("src/main.py", self.code, path="main.py"),
        ]),
        title_bar=ui.title_bar(
            [ui.title_button("pyzed", chevron=True),
             ui.title_button("main", icon="git-branch", muted=True)],
            [ui.icon_button("bell", self.notifications, size="sm"), ui.avatar("KV")],
        ),
        left=pz.column([
            ui.panel_header("Project", [ui.icon_button("plus", self.new, size="xs")]),
            ui.tree(self.nodes, expanded=self.expanded, selected="src/main.py"),
        ]) if self.show_left else None,
        bottom=pz.column([
            ui.panel_header("Terminal", icon="terminal"),
            ui.terminal("$ python main.py\n\x1b[32m✓\x1b[0m done"),
        ]) if self.show_bottom else None,
        status_bar=ui.status_bar(
            [ui.status_item("0", icon="circle-x"), ui.status_item("1", icon="triangle-alert")],
            [ui.status_item("Ln 4, Col 8"), ui.status_item("Python")],
        ),
        left_width=200,
        bottom_height=110,
    )
```

## Docks

- Pass `None` as `left`, `right` or `bottom` to hide a dock. That is how shortcuts like
  <kbd>Ctrl</kbd>+<kbd>B</kbd> are implemented (`self.show_left = not self.show_left`).
- `left_width`, `right_width` and `bottom_height` set their size.
- Inside a dock, `ui.panel_header(title, actions, icon=...)` acts as the header.
- `ui.panel(content, header=..., side=...)` is useful if you build your own layout.

## Title bar

```python
ui.title_bar(
    start=[ui.title_button("my-project", self.projects, chevron=True)],
    end=[ui.icon_button("settings", self.settings, size="sm")],
    center=ui.muted("main.py"),
)
```

## Status bar

```python
ui.status_bar(
    [ui.status_item(icon="panel-left", on_press=self.toggle_left, selected=self.show_left,
                    tooltip="Project panel", keys="ctrl-b")],
    [ui.status_item(f"Ln {line}, Col {col}"), ui.status_item(pz.icons.language_for(self.active))],
)
```

Full reference: [Workspace](/pyzed/reference/ui/#workspace).
