"""Accessibility: the system's reduce motion setting and keyboard focus with Tab."""

import pytest

import pyzed as pz
from pyzed import accessibility as a11y
from pyzed import animation as anim


@pytest.fixture(autouse=True)
def restore_motion():
    yield
    pz.set_reduced_motion(False)


def test_macos_reads_reduce_motion():
    assert a11y._macos(lambda args: "1") is True
    assert a11y._macos(lambda args: "0") is False
    assert a11y._macos(lambda args: None) is None


def test_gnome_animations_off_means_reduce(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    assert a11y._linux(lambda args: "false", tmp_path) is True
    assert a11y._linux(lambda args: "true", tmp_path) is False
    assert a11y._linux(lambda args: None, tmp_path) is None


def test_kde_instant_animations_mean_reduce(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    (tmp_path / "kdeglobals").write_text("[General]\nAnimationDurationFactor=1\n[KDE]\nAnimationDurationFactor=0\n")
    assert a11y._linux(lambda args: "true", tmp_path) is True
    (tmp_path / "kdeglobals").write_text("[KDE]\nAnimationDurationFactor=0.5\n")
    assert a11y._linux(lambda args: "false", tmp_path) is False
    # Without a KDE setting it falls back to GNOME's.
    (tmp_path / "kdeglobals").write_text("[KDE]\n")
    assert a11y._linux(lambda args: "false", tmp_path) is True


def test_system_preference_applies_until_the_app_chooses(monkeypatch):
    monkeypatch.setattr(a11y, "system_reduced_motion", lambda: True)
    pz.set_reduced_motion(None)
    assert anim.reduced_motion() is True
    pz.set_reduced_motion(False)
    anim._follow_system()  # what run() does: an explicit choice wins
    assert anim.reduced_motion() is False
    pz.set_reduced_motion(None)
    monkeypatch.setattr(a11y, "system_reduced_motion", lambda: None)
    anim._follow_system()
    assert anim.reduced_motion() is False


def test_focus_commands_and_tab_focus_default():
    assert repr(pz.Command.focus_next()) == "Command.focus_next()"
    assert repr(pz.Command.focus_previous()) == "Command.focus_previous()"
    assert pz.App.tab_focus is True
