"""Shared test setup."""

import os
import sys

import pytest

# Render off-screen with the CPU renderer (tiny-skia) on Linux, so screenshots are the same on every machine
# with or without a GPU, and match the references in tests/visual/references.
if sys.platform.startswith("linux"):
    os.environ.setdefault("WGPU_BACKEND", "dx12")


def pytest_addoption(parser):
    parser.addoption("--update-snapshots", action="store_true",
                     help="rewrite the reference images of the visual tests that changed (tests/visual/references)")


def pytest_configure(config):
    config.addinivalue_line("markers", "visual: compares a screenshot with its reference image")


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    """Keeps the designer's saved preferences out of the user's real config folder."""
    monkeypatch.setenv("PYZED_CONFIG_DIR", str(tmp_path / "pyzed-config"))
    # every folder a test opens is trusted (tests/test_trust.py turns restricted mode back on)
    monkeypatch.setenv("PYZED_TRUST_ALL", "1")
    yield
    from pyzed import i18n

    i18n.set_language("en")  # a test that switches the designer's language must not leak it into the next


@pytest.fixture(autouse=True)
def _isolated_styles():
    """Keeps the named styles, stylesheet rules and global style an example or test sets out of the next test
    (``examples/styles.py`` names a "card" style that a stylesheet test's ``.card`` would otherwise pick up)."""
    from pyzed import style

    named, rules, global_style = dict(style._named), dict(style._rules), style._global
    yield
    style._named.clear()
    style._named.update(named)
    style._rules.clear()
    style._rules.update(rules)
    style._global = global_style
