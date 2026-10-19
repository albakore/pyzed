---
title: Testing
description: How the test suite is organized, how to test ui components without a window and how the visual regression tests and their reference images work.
sidebar:
  order: 5
---

The test suite lives in `tests/` and runs with pytest, off-screen: it needs no GPU and no display.

```bash
pytest tests                      # everything (uv run pytest tests)
pytest tests -m "not visual"      # skip the screenshot comparisons
pytest tests/test_ui_overlays.py  # one file
```

## Testing `ui` components

The components in `pyzed.ui` are plain functions that return widgets. Widgets are opaque Rust objects,
so to look inside them use the `ui_tree` helper: it swaps `pyzed._core` for a recorder while the test runs,
and every widget a component builds becomes a `Node` with its `kind`, positional `args` and keyword `props`.

```python
import pytest

import pyzed as pz
from pyzed.ui import navigation as nav
from ui_tree import install


@pytest.fixture
def tree(monkeypatch):
    return install(monkeypatch)


def test_tab_bar_selects_by_id(tree):
    selected = []
    bar = nav.tab_bar([nav.Tab("a", "a.py")], "a", on_select=selected.append, theme=pz.themes.ONE_DARK)
    bar.button_with("a.py").args[1]()           # press the tab
    assert selected == ["a"]
    assert bar.props["bg"] == pz.themes.ONE_DARK.tab_bar
```

`Node.find(kind, where)`, `find_all`, `walk`, `texts()` and `button_with(text)` search the tree.
Pass an explicit `theme=` so the expected colors do not depend on the current theme. To check that a
component really renders, build it inside an `App` and call `App.screenshot` (see the end of
`tests/test_ui_workspace.py`).

## Visual regression tests

`tests/test_visual.py` renders every scene in `tests/visual/scenes.py` with `App.screenshot` and compares
it, pixel by pixel, with its reference image in `tests/visual/references/`. A pixel counts as changed
when a channel differs by more than 16; the test fails when more than 0.05% of the pixels change.

The references are rendered on **Linux with the CPU renderer** (tiny-skia; `tests/conftest.py` sets
`WGPU_BACKEND=dx12`, which has no backend on Linux, so iced falls back to it). Other platforms rasterize text
slightly differently, so there the comparisons are skipped unless `PYZED_VISUAL=1` is set. The visual tests
need Pillow (`pip install pillow`; it is in the `test` group of `pyproject.toml`).

### When a comparison fails

The test writes two images to `tests/visual/output/` (ignored by git):

- `<scene>.actual.png`: what the code renders now.
- `<scene>.diff.png`: the reference, faded, with the changed pixels in red.

In CI they are uploaded as the **visual-diffs** artifact of the Linux test job.

### Updating the references

If the change is intended (you changed a component's look on purpose, or merged a change that did),
regenerate the references and commit them with your change:

```bash
pytest tests/test_visual.py --update-snapshots                # every scene that changed
pytest tests/test_visual.py --update-snapshots -k palette     # only the scenes matching "palette"
git add tests/visual/references
```

`--update-snapshots` only rewrites the images that really changed, so unrelated references stay untouched.
Run it on Linux (or in the Linux CI job's environment) so the images match what CI renders. When two
branches change the same reference, resolve the conflict by regenerating it after the merge.

### Adding a scene

Add a function to `tests/visual/scenes.py` that returns an `App`, decorated with `@scene`:

```python
@scene("badges", size=(320, 120))
def badges():
    return _app(lambda: pz.container(pz.row([ui.badge("new", tint="accent"), ui.count_badge(3)], spacing=8), padding=16))
```

Then create its reference with `pytest tests/test_visual.py --update-snapshots -k badges` and
commit the PNG. Keep scenes small and deterministic: no clocks, random data or files outside the repository.
Animations are rendered in their final state. A reference whose scene was removed makes
`test_every_reference_has_a_scene` fail, so delete the image together with the scene.
