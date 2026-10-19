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
