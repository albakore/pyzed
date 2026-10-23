"""Tests for @pz.background: commands that run functions off the UI thread."""

import pytest

import pyzed as pz
from pyzed import _core, workers


def double(n):
    return n * 2


@pz.background(process=True)
def doubled_elsewhere(n):
    return n * 2


class Search:
    def __init__(self):
        self.shown = []

    @pz.background(then="show", latest=True)
    def search(self, text):
        return text.upper()

    def show(self, rows):
        self.shown.append(rows)


def test_calls_return_commands():
    app = Search()
    assert repr(app.search("a")) == "Command.perform(...)"
    assert repr(pz.background(double)(2)) == "Command.perform(...)"
    assert Search.search.__wrapped__(app, "x") == "X"  # the function itself is still there
    assert doubled_elsewhere.__pyzed_background__


def test_then_by_name_needs_a_method():
    lone = pz.background(then="show")(double)
    with pytest.raises(TypeError):
        lone(3)


def test_process_jobs_go_by_name():
    # what a worker process runs: the module's function, unwrapped from the decorator
    assert workers._run(__name__, "doubled_elsewhere", (21,), {}) == 42
    assert workers._run(__name__, "double", (4,), {}) == 8


def test_shutdown_without_a_pool():
    workers.shutdown()
    assert workers._pool is None


def test_image_background_option():
    assert repr(_core.image(b"not an image", background=True)) == "<Widget image>"
    assert repr(_core.image("missing.png", background=False)) == "<Widget image>"
