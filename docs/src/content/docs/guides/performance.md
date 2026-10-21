---
title: Large data and performance
description: "Python GUI performance with Pyzed: show hundreds of thousands of rows with virtual lists and tables, and skip unchanged views with @pz.memo."
sidebar:
  order: 18
---

Pyzed calls `view()` after every message and turns the widget tree it returns into Iced
widgets. For most apps that takes well under a millisecond. Two things make it slow: building
**many rows** that are not even on screen, and rebuilding **big subtrees** that did not change.
Pyzed has a tool for each.

## Fast by default

You don't have to turn any of this on. Pyzed does it in every app, following what fast native editors do to keep
their UI fast: start drawing as soon as possible, and don't redo work nobody asked for.

- **Fast start.** `import pyzed` loads only what an app needs to open a window. The designer,
  the API reference, asyncio and the package metadata load the first time you use them.
- **Fonts in parallel.** Scanning the system fonts starts the moment Pyzed is imported, on its
  own thread, while Python runs the rest of your imports.
- **Native GPU APIs first.** The GPU renderer starts Vulkan, Metal or DirectX 12. The OpenGL
  backend, slower to start and heavier on memory, is started only when none of those works.
- **Cheap widget trees.** Building containers, buttons and theme colors costs less, and the
  native core allocates with [mimalloc](https://github.com/microsoft/mimalloc), which is much
  faster than the system allocator with the many small objects every `view()` creates.
- **Shared pieces of components.** `ui.button`, `ui.icon_button`, `ui.kbd` and tooltips reuse the
  widgets that only depend on the theme and on their text, icon or keys. Widgets never change once
  built, so one copy serves every button that says "Open". A view of 1,000 buttons and labels
  builds in about a third less time.
- **The CPU renderer when there is no real GPU.** On a virtual machine, a remote desktop or a
  computer without a graphics driver, the GPU that Vulkan, DirectX or OpenGL offer is an emulation
  running on the CPU (Mesa's llvmpipe and lavapipe, Windows' WARP). There Pyzed draws with its CPU
  renderer (tiny-skia) instead: it is faster and takes about 100 MB less memory.
- **No rebuilds for keys nobody listens to.** Key presses and releases only reach your app
  (and rebuild the view) when a window defines `on_key` or `on_key_up`. Typing in a field
  rebuilds the view once per key instead of three times.

Measured with the [benchmark app](/pyzed/why/benchmarks/) (640×480 window, a label and a
button per row, Xvfb without a GPU, medians of 5 launches) on the same machine:

| | Before | Now |
| --- | --- | --- |
| `import pyzed` | 178 ms | 78 ms |
| First frame, 10 rows | 454 ms | 323 ms |
| Update of 1,000 rows | 40.7 ms | 34.9 ms |
| Memory, 10 rows (RSS) | 174 MB | 146 MB |

:::note
`WGPU_BACKEND=gl` (or `vulkan`, `metal`, `dx12`) still picks a GPU backend yourself,
`ICED_BACKEND=wgpu` keeps the GPU renderer even on an emulated GPU (what [shaders](/pyzed/shading/shaders/)
need), and `ICED_BACKEND=tiny-skia` always uses the CPU renderer.
:::

## Virtual lists and tables

A virtual list builds only the rows in view. Rows are built when they scroll into view and
dropped when they leave it, so a list of a million items costs the same as one of fifty.

```python
import pyzed as pz
from pyzed import ui

class Logs(pz.App):
    def __init__(self):
        self.lines = [f"[{i:06}] request handled" for i in range(500_000)]

    def view(self):
        return ui.virtual_list(
            self.lines,
            lambda line: pz.text(line, font="mono", size=12),
            item_height=20,
            id="logs",
        )
```

- [`ui.virtual_list(items, render)`](/pyzed/library/virtual-list/) is a themed, scrolling list:
  `render(item)` returns the widget for one item.
- [`ui.table`](/pyzed/library/table/) is virtualized too: pass it all your rows.
- [`pz.virtual_column(count, item, item_height=...)`](/pyzed/reference/widgets/#virtual_column)
  is the building block: `item(index)` returns row `index`. Put it inside any `pz.scrollable`.

Every row has the same height (`item_height`), which is what lets Pyzed know where each row
goes without building it. To scroll to row `i`, scroll the list's `id` to
`i * (item_height + spacing)`:

```python
pz.Command.scroll_to("logs", 0, 1_000 * 20)   # row 1000
```

Measured on a 200 000-row table, building the view went from 3.7 s to 0.2 ms.

:::tip
`items` and `rows` should be lists (or other sequences): other iterables are copied into a list
on every `view()`. Sorting a huge table on every `view()` is the remaining cost; keep the rows
sorted in your state, or sort them in a `@pz.memo` function.
:::

## Memoized subtrees

`@pz.memo` caches what a function returns by its arguments. While the arguments are equal, the
next `view()` reuses the same widget tree instead of building it again:

```python
@pz.memo
def sidebar(files: tuple, selected: str):
    return pz.column([ui.list_item(f, icon="file", selected=f == selected) for f in files])

class Editor(pz.App):
    def view(self):
        return pz.row([sidebar(tuple(self.files), self.selected), self.editor()])
```

How arguments are compared:

| Argument | Compared by |
| --- | --- |
| Numbers, strings, tuples, frozen dataclasses... | Value (their hash). |
| Lists, dicts and sets | Their contents. |
| Anything else (your objects, `self`) | Identity: mutating it in place does not refresh the cache. |

The current theme and language are always part of the key, so switching them rebuilds every
memoized subtree.

:::caution
A memoized function only sees its arguments. If it reads `self.something` or a global, the
cached subtree keeps the old value until the arguments change. Pass everything it depends on,
or a version number you bump when the data changes.
:::

- `@pz.memo(maxsize=256)` keeps more results (64 by default). It is handy on a function called
  once per row, such as the `render` of a virtual list.
- `function.cache_clear()` empties one function's cache, `pz.clear_memos()` all of them.
- `pz.memo_stats()` returns `{"hits": ..., "misses": ...}` to check that a subtree is reused.

## Other tips

- Keep `view()` free of slow work: load files, query databases and sort data in handlers or
  [async tasks](/pyzed/guides/async/), and keep the results in your state.
- Draw thousands of shapes with one [canvas](/pyzed/guides/canvas/) instead of thousands of widgets.
- `pz.every` subscriptions call `view()` on every tick: stop them when nothing moves.
