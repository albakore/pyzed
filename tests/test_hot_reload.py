"""Hot reload: code changes reach live objects, state is kept, failures are shown."""

import importlib
import os
import sys
import textwrap
import time
import types

import pytest

import pyzed as pz
from pyzed import hot_reload

from test_features import read_png

APP = '''
import pyzed as pz
from {helpers} import COLOR


class Item:
    def label(self):
        return "old"


class Demo(pz.App):
    size = (60, 40)
    count = 0

    def __init__(self):
        self.items = [Item()]

    def view(self):
        return pz.container(pz.text(""), width="fill", height="fill", bg=COLOR)
'''


def write(path, source):
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    # Make sure the new mtime differs even on file systems with coarse timestamps.
    stamp = time.time() + 2 + len(source) % 7
    os.utime(path, (stamp, stamp))


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A tiny project (an app module and a helpers module) importable from tmp_path."""
    suffix = tmp_path.name.replace("-", "_")
    app_name, helpers_name = f"hr_app_{suffix}", f"hr_helpers_{suffix}"
    write(tmp_path / f"{helpers_name}.py", 'COLOR = "#ff0000"\n')
    write(tmp_path / f"{app_name}.py", APP.format(helpers=helpers_name))
    monkeypatch.syspath_prepend(str(tmp_path))
    module = importlib.import_module(app_name)
    yield types.SimpleNamespace(
        dir=tmp_path,
        module=module,
        app_file=tmp_path / f"{app_name}.py",
        helpers_file=tmp_path / f"{helpers_name}.py",
        helpers=helpers_name,
    )
    for name in (app_name, helpers_name):
        sys.modules.pop(name, None)
    if hot_reload.current() is not None:
        hot_reload.current().stop()


def pixel(app, tmp_path):
    out = tmp_path / "shot.png"
    pz.screenshot(app, out, scale=1.0)
    return read_png(out)[20][30][:3]


def test_watches_only_project_modules(project):
    app = project.module.Demo()
    reloader = hot_reload.Reloader(app)
    files = set(reloader.project_modules())
    assert files == {project.app_file.resolve(), project.helpers_file.resolve()}


def test_scan_reports_saved_files(project):
    reloader = hot_reload.Reloader(project.module.Demo())
    reloader.scan()
    assert reloader.scan() == set()
    write(project.helpers_file, 'COLOR = "#00ff00"\n')
    assert reloader.scan() == {project.helpers_file.resolve()}


def test_reload_updates_methods_and_keeps_state(project, tmp_path):
    app = project.module.Demo()
    app.count = 7
    item = app.items[0]
    assert pixel(app, tmp_path) == (255, 0, 0)

    reloader = hot_reload.Reloader(app)
    write(project.helpers_file, 'COLOR = "#00ff00"\n')
    write(project.app_file, APP.format(helpers=project.helpers).replace('"old"', '"new"'))
    assert reloader.reload([project.helpers_file, project.app_file]) is None
    assert reloader.error is None and reloader.count == 1

    # The same objects, now running the new code, with their state intact.
    assert type(app) is project.module.Demo
    assert app.count == 7 and app.items[0] is item
    assert item.label() == "new"
    assert pixel(app, tmp_path) == (0, 255, 0)


def test_changing_a_dependency_reloads_its_users(project, tmp_path):
    app = project.module.Demo()
    reloader = hot_reload.Reloader(app)
    write(project.helpers_file, 'COLOR = "#0000ff"\n')
    reloader.reload([project.helpers_file])
    # The app module imported COLOR by value, so it had to be re-executed too.
    assert project.module.COLOR == "#0000ff"
    assert pixel(app, tmp_path) == (0, 0, 255)


def test_failed_reload_is_shown_and_recovers(project, tmp_path):
    app = project.module.Demo()
    reloader = hot_reload.enable(app)
    write(project.app_file, "def broken(:\n")
    reloader.reload([project.app_file])
    assert "SyntaxError" in reloader.error
    with pytest.raises(hot_reload.ReloadError):
        app.__pyzed_view__()
    # The window shows the error instead of the app (dark error panel).
    assert pixel(app, tmp_path) != (255, 0, 0)

    write(project.app_file, APP.format(helpers=project.helpers))
    reloader.reload([project.app_file])
    assert reloader.error is None
    assert pixel(app, tmp_path) == (255, 0, 0)


def test_on_reload_hook_can_migrate_state(project):
    app = project.module.Demo()
    reloader = hot_reload.Reloader(app)
    source = APP.format(helpers=project.helpers) + textwrap.indent(
        textwrap.dedent(
            """
            def on_reload(self):
                if not hasattr(self, "tags"):
                    self.tags = ["migrated"]
                return pz.Command.batch([])
            """
        ),
        "    ",
    )
    write(project.app_file, source)
    commands = reloader.reload([project.app_file])
    assert app.tags == ["migrated"]
    assert len(commands) == 1 and isinstance(commands[0], pz.Command)


def test_main_script_is_rerun_without_its_main_block(tmp_path):
    script = tmp_path / "script_app.py"
    write(
        script,
        """
        import pyzed as pz

        MAIN_RUNS = globals().get("MAIN_RUNS", 0)

        class Demo(pz.App):
            def greeting(self):
                return "hello"

        if __name__ == "__main__":
            MAIN_RUNS += 1
        """,
    )
    module = types.ModuleType("__main__")
    module.__file__ = str(script)
    saved = sys.modules["__main__"]
    sys.modules["__main__"] = module
    try:
        exec(compile(script.read_text(), str(script), "exec"), vars(module))
        app = module.Demo()
        reloader = hot_reload.Reloader(app)
        write(script, script.read_text().replace('"hello"', '"bye"'))
        reloader.reload([script])
        assert reloader.error is None, reloader.error
        assert app.greeting() == "bye"
        assert module.MAIN_RUNS == 1  # the `__main__` block did not run again
        assert type(app).__module__ == "__main__"
    finally:
        sys.modules["__main__"] = saved


def test_watch_calls_back_for_other_files(project):
    reloader = hot_reload.Reloader(project.module.Demo())
    data = project.dir / "layout.json"
    data.write_text("{}")
    seen = []
    reloader.watch(data, seen.append)
    write(data, '{"a": 1}')
    changed = reloader.scan()
    reloader.reload(changed)
    assert seen == [data.resolve()]


def test_run_is_ignored_while_reloading(monkeypatch):
    monkeypatch.setattr(hot_reload, "_reloading", True)
    pz.run(object)  # would fail (or open a window) if it really ran


def test_env_var_turns_reload_on(monkeypatch):
    monkeypatch.setenv("PYZED_RELOAD", "1")
    assert hot_reload.enabled_by_env()
    monkeypatch.setenv("PYZED_RELOAD", "0")
    assert not hot_reload.enabled_by_env()
