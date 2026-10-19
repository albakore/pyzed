"""Shared test setup."""

import pytest


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    """Keeps the designer's saved preferences out of the user's real config folder."""
    monkeypatch.setenv("PYZED_CONFIG_DIR", str(tmp_path / "pyzed-config"))
