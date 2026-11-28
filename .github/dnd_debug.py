"""Temporary pytest plugin for the DnD debug workflow: on a failed drag test, the state it ran in."""

import threading

import pytest

_seen = []


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed and "test_dnd" in item.nodeid:
        from pyzed import animation, bidi, i18n

        lines = [f"direction={bidi.get_direction()} rtl={bidi.is_rtl()} reduced_motion={animation.reduced_motion()} "
                 f"language={i18n.language()}",
                 "threads: " + ", ".join(f"{t.name}{'(daemon)' if t.daemon else ''}" for t in threading.enumerate()),
                 "tests before it in this worker:", *(f"  {n}" for n in _seen)]
        report.sections.append(("dnd-debug", "\n".join(lines)))
    if report.when == "teardown":
        _seen.append(item.nodeid)
