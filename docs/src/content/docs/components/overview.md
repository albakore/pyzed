---
title: Overview
description: The pyzed.ui components, inspired by the Zed editor.
sidebar:
  order: 0
---

:::tip[Component library]
Every component now has its own page, with a live preview, examples and its full API, in the
[component library](/pyzed/library/). This page is kept as a summary.
:::

`pyzed.ui` is a collection of ready-to-use components that reproduce the look of the
[Zed](https://zed.dev) editor. They are **functions** that return widgets, so they combine freely
with the [base widgets](/pyzed/reference/widgets/) and with each other.

![Component gallery (One Dark)](../../../../screenshots/components-dark.png)

```python
import pyzed as pz
from pyzed import ui

ui.button("Save", self.save, icon="save", variant="solid", keys="ctrl-s")
```

## Common rules

- **Theme colors.** Every component reads the current theme (`App.theme`, or the window's theme in
  [multi-window](/pyzed/guides/windows/) apps). Changing the theme restyles the whole UI. All of them accept `theme=` to use a different one.
- **Tokens or hex.** Color parameters (`color`, `icon_color`, `tint`…) accept a theme token such as
  `"accent"`, `"text_muted"` or `"error"`, or a `"#rrggbb"` color.
- **Messages or callables.** `on_press`, `on_select`, `on_toggle`… accept a message for `update`
  or a callable. Those that produce a value (text, `bool`, id) call the callable with that value.
- **Icons.** The `icon=` parameter accepts any [Lucide](https://lucide.dev) name.
- **Shortcuts.** `keys="ctrl-shift-p"` displays the shortcut Zed-style (symbols on macOS).

## Groups

| Group | Components |
| --- | --- |
| [Basics](/pyzed/components/basics/) | `button`, `icon_button`, `label`, `muted`, `heading`, `badge`, `indicator`, `kbd`, `avatar`, `tooltip`, `divider`, `card` |
| [Forms](/pyzed/components/forms/) | `input`, `search_input`, `switch`, `checkbox`, `slider`, `progress`, `segmented`, `field` |
| [Lists and tree](/pyzed/components/lists/) | `list_item`, `list_header`, `tree` + `TreeNode`, `menu` + `MenuItem` |
| [Navigation](/pyzed/components/navigation/) | `tab_bar` + `Tab`, `breadcrumbs`, `toolbar` |
| [Workspace](/pyzed/components/workspace/) | `workspace`, `title_bar`, `title_button`, `status_bar`, `status_item`, `panel`, `panel_header` |
| [Overlays](/pyzed/components/overlays/) | `layer`, `modal`, `command_palette`, `picker`, `fuzzy_filter`, `toast`, `toasts` |
| [Code](/pyzed/components/code/) | `editor`, `terminal`, `ansi` |
| [More controls](/pyzed/components/controls/) | `select`, `radio_group`, `number_field`, `split_button`, `toggle_group`, `chip`, `disclosure` |
| [Data and feedback](/pyzed/components/data/) | `table` + `Column`, `callout`, `empty_state`, `settings_group`, `stat`, `sparkline`, `bar_chart`, `donut`, `spinner`, `count_badge`, `facepile`, `diff_stat`, `keybinding_hint` |
| [Content and panels](/pyzed/components/content/) | `markdown`, `split`, `popover`; base widgets `pz.image`, `pz.image_viewer`, `pz.rich_text`, `pz.qr_code`, `pz.grid` |
| [Dialogs and tools](/pyzed/components/dialogs/) | `dialog_layer`, `alert`, `confirm`, `prompt`, `choice`, `unsaved_changes`, `accordion`, `Log` + `console`, `shortcuts`, `about`, `ColorPicker`, `color_swatch` |

To see them all in action, run the gallery:

```bash
python examples/gallery.py
```

:::tip[Illustrations]
The images in this section are generated with `python docs/scripts/component_shots.py`, which
renders each example offscreen with `App.screenshot`.
:::
