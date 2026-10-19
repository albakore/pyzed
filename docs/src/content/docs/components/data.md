---
title: Data and feedback
description: Tables, callouts, empty states, grouped settings, stats, charts and indicators.
sidebar:
  order: 9
---

:::tip[Component library]
Every component now has its own page, with a live preview, examples and its full API, in the
[component library](/pyzed/library/). This page is kept as a summary.
:::

## Callouts and indicators

![Callouts and indicators](../../../assets/components/feedback.png)

```python
ui.callout("A new version is available", "Pyzed 0.2 adds windows, async and canvas.", tint="info",
           actions=[ui.button("What's new", self.whats_new, size="sm")], on_dismiss=self.close)
ui.callout("Could not save", "The file is read-only.", tint="error")

pz.row([
    ui.spinner(),                                  # only spins while on screen
    ui.count_badge(7),
    ui.count_badge(120, tint="error"),            # shows "99+"
    ui.facepile(["Ana", "Luis", "Kev", "Marta"]), # overlapping avatars
    ui.diff_stat(42, 9),                          # +42 −9 and blocks, as in Zed
    ui.keybinding_hint("Open palette", "ctrl-shift-p"),
], spacing=14, align="center")
```

`tint` accepts `"info"`, `"success"`, `"warning"`, `"error"` or any theme token or color.

:::note
`ui.spinner()` is animated by the app clock, so it needs redraws. While it is shown,
return a subscription such as `pz.every(1 / 30, lambda: None)` (see [Async](/pyzed/guides/async/)).
:::

## Tables

![Table](../../../assets/components/table.png)

```python
ui.table(
    [ui.Column("File", "name"),
     ui.Column("Language", "lang", width=120),
     ui.Column("Lines", "lines", width=80, align="end")],
    self.rows,                      # dicts or objects
    sort_by=self.sort_column, descending=self.desc, on_sort=self.sort,
    on_row_press=self.select, selected=self.selection, striped=True,
)

def sort(self, title):
    self.desc = not self.desc if self.sort_column == title else False
    self.sort_column = title
```

`ui.Column(title, key, width="fill", align="start", render=None, sortable=True)`: `key` is a
dict key, an attribute or a `row -> value` function; `render(value)` returns a widget for the
cell. The table sorts by the column whose **title** is `sort_by`; you only store the title and
the direction.

## Stats and charts

![Stats and charts](../../../assets/components/charts.png)

```python
ui.stat("Users", "1,284", delta=12.5, trend=[3, 5, 4, 6, 8, 7, 9])
ui.stat("Errors", "37", delta=-8.0)
ui.bar_chart([12, 19, 8, 15, 22, 17], labels=["M", "T", "W", "T", "F", "S"], width=260, height=150)
ui.donut([60, 25, 15], label="60%")
ui.sparkline([1, 4, 2, 6, 3, 7, 5, 8])
```

They are drawn with [`pz.canvas`](/pyzed/guides/canvas/) and use the theme colors
(`tint`, `colors`).

## Empty states and settings

![Empty state and settings group](../../../assets/components/empty.png)

```python
ui.empty_state("No results", "Try a different search.", icon="search",
               actions=[ui.button("Clear filters", self.clear, size="sm")])

ui.settings_group("Editor", [
    ui.field("Font size", ui.number_field(self.font, self.set_font, suffix="px")),
    ui.field("Soft wrap", ui.switch(self.wrap, self.set_wrap)),
], description="Editor preferences.")
```

Full reference: [Data and feedback](/pyzed/reference/ui/#data-and-feedback).
