"""The "Handling the events" snippets of the component library (docs/scripts/library_events.py) run.

Every imperative and declarative snippet defines an app: it is created and rendered off-screen. Every
functional snippet defines a frozen ``State`` and ``view(state, set_state)``: it runs inside a small app
that keeps the state, and ``set_state`` must accept the fields of ``State``.
"""

import dataclasses
import sys
from pathlib import Path

import pytest

import pyzed as pz
from pyzed import draw, ui

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "docs" / "scripts"))

import library_events  # noqa: E402

SNIPPETS = [(slug, style, code) for slug, styles in sorted(library_events.EXAMPLES.items())
            for style, code in styles.items()]


def main_view():
    return pz.container(pz.text("The rest of the app"), width="fill", height="fill")


def run(code: str) -> dict:
    ns = {"pz": pz, "ui": ui, "draw": draw, "main_view": main_view, "__name__": "snippet"}
    exec(compile(code, "snippet.py", "exec"), ns)
    return ns


def app_of(ns: dict):
    apps = [v for v in ns.values() if isinstance(v, type) and issubclass(v, pz.App) and v is not pz.App]
    assert apps, "the snippet defines no pz.App"
    return apps[-1]


@pytest.mark.parametrize("slug,style,code", SNIPPETS, ids=[f"{s}-{k}" for s, k, _ in SNIPPETS])
def test_snippet_renders(slug, style, code, tmp_path):
    ns = run(code)
    if style == "functional":
        state_cls, view = ns["State"], ns["view"]
        assert dataclasses.is_dataclass(state_cls) and state_cls.__dataclass_params__.frozen

        class Shell(pz.App):
            state = state_cls()

            def set_state(self, **changes):
                self.state = dataclasses.replace(self.state, **changes)

            def view(self):
                return view(self.state, self.set_state)

        app = Shell()
    else:
        app = app_of(ns)()
    app.screenshot(tmp_path / "shot.png", size=(720, 420), scale=1)
    assert (tmp_path / "shot.png").exists()


def test_every_component_with_events_has_examples():
    sys.path.insert(0, str(ROOT / "docs" / "scripts"))
    import gen_library

    with_events = {e["slug"] for e in gen_library.library_data.COMPONENTS if gen_library.own_events(e)}
    assert with_events == set(library_events.EXAMPLES)
    for slug, styles in library_events.EXAMPLES.items():
        assert set(styles) == {"imperative", "declarative", "functional"}, slug
