"""Saved agent conversations: ``pyzed.agents.threads``."""

import json
import os
import sys

import pytest

from pyzed.agents import threads
from pyzed.agents.threads import Thread, ThreadStore


def _user(text):
    return {"role": "user", "content": [{"type": "text", "text": text}]}


@pytest.fixture
def clock(monkeypatch):
    """A clock that moves one second per call, so saves never share a timestamp."""
    now = [1_000_000.0]

    def tick():
        now[0] += 1
        return now[0]

    monkeypatch.setattr(threads.time, "time", tick)
    return now


def test_new_threads_get_unique_ids():
    ids = {Thread().id for _ in range(50)}
    assert len(ids) == 50 and all(len(i) == 12 for i in ids)


@pytest.mark.parametrize("messages, title", [
    ([], "New thread"),
    ([{"role": "assistant", "content": [{"type": "text", "text": "Hi"}]}], "New thread"),
    ([_user("   ")], "New thread"),
    ([{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": "Fix the\nbug"}]}], "Fix the"),
    ([_user(""), _user("Second")], "Second"),
    ([_user("x" * 61)], "x" * 57 + "…"),
    ([_user("x" * 60)], "x" * 60),
])
def test_display_title(messages, title):
    assert Thread(messages=messages).display_title == title


def test_an_explicit_title_wins():
    assert Thread(title="Refactor", messages=[_user("hello")]).display_title == "Refactor"


def test_round_trip_through_dict():
    thread = Thread(title="T", model="anthropic:claude-opus-5-5", messages=[_user("hi")])
    again = Thread.from_dict(json.loads(json.dumps(thread.to_dict())))
    assert again == thread


def test_from_dict_tolerates_bad_data():
    thread = Thread.from_dict({"id": None, "title": None, "messages": "nope", "created": None, "model": 3})
    assert len(thread.id) == 12 and thread.title == "" and thread.messages == [] and thread.model == "3"
    assert thread.created > 0 and thread.updated > 0


def test_save_load_delete(tmp_path, clock):
    store = ThreadStore(tmp_path / "threads")
    thread = Thread(model="ollama:llama3", messages=[_user("hello")])
    path = store.save(thread)
    assert path == tmp_path / "threads" / f"{thread.id}.json"
    assert thread.updated == clock[0]
    assert store.load(thread.id) == thread
    store.delete(thread.id)
    assert store.load(thread.id) is None
    store.delete(thread.id)  # deleting twice is fine


def test_files_keep_unicode_readable(tmp_path):
    store = ThreadStore(tmp_path)
    thread = Thread(messages=[_user("¿Qué tal? 🚀")])
    assert "¿Qué tal? 🚀" in store.save(thread).read_text(encoding="utf-8")


def test_ids_cannot_escape_the_folder(tmp_path):
    store = ThreadStore(tmp_path / "threads")
    thread = Thread(id="../../evil")
    path = store.save(thread)
    assert path.parent == tmp_path / "threads" and path.name == "evil.json"
    assert store.load("../../evil") == thread


def test_list_is_newest_first_and_skips_broken_files(tmp_path, clock):
    store = ThreadStore(tmp_path)
    first, second = Thread(title="first"), Thread(title="second")
    store.save(first)
    store.save(second)
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "list.json").write_text("[1, 2]", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    assert [t.title for t in store.list()] == ["second", "first"]
    store.save(first)  # saving again moves it to the top
    assert [t.title for t in store.list()] == ["first", "second"]


def test_load_missing_or_broken(tmp_path):
    store = ThreadStore(tmp_path)
    assert store.load("missing") is None
    (tmp_path / "bad.json").write_text("[]", encoding="utf-8")
    assert store.load("bad") is None


def test_missing_folder_lists_nothing(tmp_path):
    assert ThreadStore(tmp_path / "nowhere").list() == []


def test_old_threads_are_pruned(tmp_path, clock, monkeypatch):
    monkeypatch.setattr(threads, "KEEP", 3)
    store = ThreadStore(tmp_path)
    saved = [Thread(title=str(i)) for i in range(5)]
    for thread in saved:
        store.save(thread)
    assert [t.title for t in store.list()] == ["4", "3", "2"]
    assert sorted(p.stem for p in tmp_path.glob("*.json")) == sorted(t.id for t in saved[2:])


def test_unsaveable_threads_return_none(tmp_path):
    store = ThreadStore(tmp_path)
    thread = Thread(messages=[{"role": "user", "content": [{"type": "text", "text": object()}]}])
    assert store.save(thread) is None


@pytest.mark.skipif(sys.platform == "win32" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                    reason="needs a folder the user cannot write")
def test_read_only_folder_returns_none(tmp_path):
    folder = tmp_path / "ro"
    folder.mkdir()
    folder.chmod(0o500)
    try:
        assert ThreadStore(folder).save(Thread()) is None
    finally:
        folder.chmod(0o700)


def test_default_folder_is_in_the_config_dir(tmp_path):
    # tests/conftest.py points PYZED_CONFIG_DIR at a temporary folder
    store = ThreadStore()
    assert store.folder == tmp_path / "pyzed-config" / "agents" / "threads"
    assert store.save(Thread()).parent == store.folder
