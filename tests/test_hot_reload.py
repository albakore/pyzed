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


STATEFUL = '''
import pyzed as pz

STARTS = globals().get("STARTS", 0)


class Todo:
    def __init__(self, text):
        self.text = text
{todo_extra}

class Panel(pz.Window):
    def __init__(self, title, *, rows=3):
        self.heading = title
        self.rows = rows
{panel_extra}
    def view(self):
        return pz.text(self.heading)


class Base(pz.App):
    def describe(self):
        return "base"


class Demo(Base):
    def __init__(self):
        global STARTS
        STARTS += 1
        print("init ran")
        self.count = 0
        self.step = 1
        self.todos = [Todo("milk")]
        self.callback = self.label
{app_extra}
    def label(self):
        return "{label}"

    def describe(self):
        return "demo " + super().describe()

    def view(self):
        return pz.text(str(self.count))
'''


def stateful(project, todo_extra="", panel_extra="", app_extra="", label="old"):
    def block(text):
        return textwrap.indent(textwrap.dedent(text), "        ") if text else ""

    write(project.app_file, STATEFUL.format(todo_extra=block(todo_extra), panel_extra=block(panel_extra),
                                            app_extra=block(app_extra), label=label))


@pytest.fixture
def live(project):
    """The stateful app, imported fresh, with a reloader watching it."""
    stateful(project)
    module = importlib.reload(project.module)
    app = module.Demo()
    return types.SimpleNamespace(module=module, app=app, reloader=hot_reload.Reloader(app))


def test_new_attributes_appear_without_restarting(project, live, capsys):
    app = live.app
    app.count = 5
    todos = app.todos
    stateful(project, app_extra="self.tags = ['new']\nself.filter = None")
    assert live.reloader.reload([project.app_file]) is None
    assert live.reloader.error is None
    assert app.tags == ["new"] and app.filter is None
    assert app.count == 5 and app.todos is todos  # the existing state is kept
    [change] = live.reloader.changes
    assert change.name == "Demo" and change.changed == ["__init__"]
    assert change.new_state == ["tags", "filter"]
    err = capsys.readouterr()
    assert "pyzed: reloaded Demo: methods changed: __init__; new state: tags, filter" in err.err
    assert "init ran" not in err.out  # the scratch copy's prints are hidden


def test_new_initial_values_apply_unless_the_app_changed_them(project, live):
    app = live.app
    app.count = 9  # changed while running: kept
    stateful(project, app_extra="")
    source = project.app_file.read_text().replace("self.count = 0", "self.count = 100")
    write(project.app_file, source.replace("self.step = 1", "self.step = 5"))
    live.reloader.reload([project.app_file])
    assert app.count == 9 and app.step == 5
    assert live.reloader.changes[0].updated_state == ["step"]
    # The next edit compares against the new default.
    write(project.app_file, project.app_file.read_text().replace("self.step = 5", "self.step = 2"))
    live.reloader.reload([project.app_file])
    assert app.step == 2


def test_unchanged_classes_do_not_run_init_again(project, live):
    starts = live.module.STARTS
    write(project.app_file, project.app_file.read_text() + "\nEXTRA = 1\n")
    live.reloader.reload([project.app_file])
    assert live.module.STARTS == starts
    assert live.reloader.changes == []


def test_reload_init_false_skips_the_scratch_copy(project, live):
    starts = live.module.STARTS
    stateful(project, app_extra="self.tags = []")
    write(project.app_file, project.app_file.read_text().replace("class Demo(Base):", "class Demo(Base):\n    reload_init = False"))
    live.reloader.reload([project.app_file])
    assert live.module.STARTS == starts
    assert not hasattr(live.app, "tags")


def test_stored_methods_run_the_new_code(project, live):
    app = live.app
    callback = app.callback  # a bound method kept from before the reload
    stateful(project, label="new")
    live.reloader.reload([project.app_file])
    assert callback() == "new" and app.label() == "new"
    assert live.reloader.changes[0].changed == ["label"]
    # `super()` inside a method kept from before the reload still finds the right class.
    describe = app.describe
    stateful(project, label="newer")
    live.reloader.reload([project.app_file])
    assert describe() == "demo base"


def test_windows_rerun_init_with_their_arguments(project, live):
    panel = live.module.Panel("Files", rows=7)
    hot_reload.note_window(panel)
    panel.heading = "Renamed"
    stateful(project, panel_extra="self.summary = f'{title}: {rows}'")
    live.reloader.reload([project.app_file])
    assert panel.summary == "Files: 7" and panel.heading == "Renamed"


def test_plain_objects_get_simple_new_attributes(project, live):
    todo = live.app.todos[0]
    stateful(project, todo_extra="self.done = False\nself.upper = text.upper()")
    live.reloader.reload([project.app_file])
    assert todo.done is False and todo.text == "milk"
    assert not hasattr(todo, "upper")  # needs an argument of __init__, which is unknown


def test_a_failing_init_does_not_break_the_reload(project, live, capsys):
    stateful(project, app_extra="raise RuntimeError('no database')", label="new")
    live.reloader.reload([project.app_file])
    assert live.reloader.error is None
    assert live.app.label() == "new"
    assert "Demo.__init__ failed while reloading its state" in capsys.readouterr().err


def test_components_get_new_state(project, live):
    source = project.app_file.read_text() + textwrap.dedent('''

        class Meter(pz.Component):
            designer = False
            value: int = 0
            level: int = pz.state(1)

            def setup(self):
                self.hover = False

            def render(self):
                return pz.text(str(self.value))
    ''')
    write(project.app_file, source)
    live.reloader.reload([project.app_file])
    meter = live.module.Meter.create(value=3)
    hot_reload.remember(meter)
    meter.level = 4
    source = source.replace("level: int = pz.state(1)", "level: int = pz.state(1)\n    peak: int = pz.state(10)")
    write(project.app_file, source.replace("self.hover = False", "self.hover = False\n        self.history = []"))
    live.reloader.reload([project.app_file])
    assert meter.peak == 10 and meter.history == [] and meter.level == 4 and meter.value == 3
    change = next(c for c in live.reloader.changes if c.name == "Meter")
    assert set(change.new_state) == {"peak", "history"}


def test_windows_still_refuse_unknown_arguments():
    class Plain(pz.Window):
        pass

    with pytest.raises(TypeError):
        Plain(1)
