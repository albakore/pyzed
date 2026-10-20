"""Projects (uv layout, dependencies, activation) and ``pyzed build``'s command line."""

import os
import sys
import textwrap

import pytest

from pyzed import build, designer, project
from pyzed.cli import main as cli_main

PYPROJECT = textwrap.dedent('''\
    [project]
    name = "shop-app"
    version = "1.2.0"
    authors = [
        { name = "Ana", email = "ana@example.com" }
    ]
    dependencies = [
        "pyzed-ui>=0.3",
        "httpx[http2]>=0.27",  # comment
    ]

    [dependency-groups]
    dev = ["ruff>=0.6", "ty"]
    docs = [
        "mkdocs",
    ]

    [tool.pyzed]
    ui = "ui"
    main = "ui/main.pzform"

    [tool.pyzed.build]
    name = "Shop"
    include = ["assets"]
    hidden-imports = ["shop_app.plugins"]
''')

LOCK = textwrap.dedent('''\
    version = 1

    [[package]]
    name = "httpx"
    version = "0.28.1"
    source = { registry = "https://pypi.org/simple" }

    [[package]]
    name = "pyzed-ui"
    version = "0.3.1"
''')


@pytest.fixture
def shop(tmp_path):
    """A uv-style project: backend in src/, UI in ui/ importing it."""
    root = tmp_path / "shop"
    (root / "src" / "shop_app").mkdir(parents=True)
    (root / "ui").mkdir()
    (root / "assets").mkdir()
    (root / "pyproject.toml").write_text(PYPROJECT)
    (root / "uv.lock").write_text(LOCK)
    (root / "src" / "shop_app" / "__init__.py").write_text("def total(items):\n    return sum(items)\n")
    (root / "ui" / "helpers.py").write_text("def money(x):\n    return f'${x:.2f}'\n")
    form = designer.Form(name="Main", title="Shop")
    form.add(designer.component("button").create("pay", 10, 10))
    form["pay"].events["click"] = "pay_click"
    designer.save(form, root / "ui" / "main.pzform")
    (root / "ui" / "main.py").write_text(textwrap.dedent('''\
        import json
        from shop_app import total
        from helpers import money


        def pay_click(form, event):
            return money(total([1, 2.5]))
    '''))
    yield project.Project.open(root)
    for name in ("shop_app", "helpers"):
        sys.modules.pop(name, None)


def test_mini_toml_matches_tomllib():
    tomllib = pytest.importorskip("tomllib")
    expected = tomllib.loads(PYPROJECT)
    parsed = project._mini_toml(PYPROJECT)
    assert parsed["project"]["dependencies"] == expected["project"]["dependencies"]
    assert parsed["dependency-groups"] == expected["dependency-groups"]
    assert parsed["tool"]["pyzed"] == expected["tool"]["pyzed"]


def test_project_settings_and_dependencies(shop):
    assert shop.name == "shop-app" and shop.version == "1.2.0" and shop.is_pyzed
    assert shop.main_form == shop.root / "ui" / "main.pzform"
    assert shop.forms() == [shop.main_form]
    deps = {d.name: d for d in shop.dependencies()}
    assert deps["httpx"].spec == "httpx[http2]>=0.27" and deps["httpx"].locked == "0.28.1"
    assert deps["ruff"].group == "dev" and deps["ruff"].dev and deps["ruff"].locked is None
    assert deps["mkdocs"].group == "docs"
    assert project.requirement_name("Foo_Bar[x]==1") == "Foo_Bar"
    assert project.normalize("Foo_Bar.baz") == "foo-bar-baz"


def test_find_walks_up_to_the_pyzed_project(shop, tmp_path):
    assert project.find(shop.ui_dir).root == shop.root
    assert project.find(shop.main_form).root == shop.root
    assert project.find(tmp_path) is None


def test_forms_import_code_outside_the_ui_folder(shop):
    app = designer.open_form(shop.main_form)
    assert str(shop.root / "src") in sys.path and str(shop.ui_dir) in sys.path
    assert app.runtime.handlers["pay_click"](None, None) == "$3.50"


def test_build_command(shop):
    opts = build.BuildOptions.from_project(shop, onefile=True)
    assert opts.name == "Shop" and opts.onefile and opts.windowed
    args = build.pyinstaller_args(shop, opts)
    launcher = shop.root / "build" / "pyzed" / "shop_app_launcher.py"
    assert args[0] == str(launcher) and "--onefile" in args and "--windowed" in args
    compile(launcher.read_text(), str(launcher), "exec")
    hidden = {args[i + 1] for i, a in enumerate(args) if a == "--hidden-import"}
    assert hidden == {"json", "shop_app", "shop_app.plugins"}  # not the local helpers module
    data = [args[i + 1] for i, a in enumerate(args) if a == "--add-data"]
    assert f"{shop.ui_dir}{os.pathsep}ui" in data and f"{shop.root / 'assets'}{os.pathsep}assets" in data
    assert ["--collect-submodules", "shop_app"] == args[args.index("shop_app") - 1: args.index("shop_app") + 1]
    workflow = build.workflow(shop)
    assert "pyzed build" in workflow.read_text() and "${{ matrix.os }}" in workflow.read_text()


def test_cli_needs_a_project(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert cli_main(["deps"]) == 1
    assert "pyzed init" in capsys.readouterr().err


def test_cli_deps(shop, monkeypatch, capsys):
    monkeypatch.chdir(shop.root)
    assert cli_main(["deps"]) == 0
    out = capsys.readouterr().out
    assert "httpx[http2]>=0.27" in out and "0.28.1" in out and "[dev]" in out


@pytest.mark.skipif(project.find_uv() is None, reason="uv is not installed")
def test_init_creates_a_uv_project(tmp_path):
    created = project.init(tmp_path / "my-app", sync=False, git=False)
    assert created.is_pyzed and created.name == "my-app"
    assert created.main_form.is_file() and created.main_form.with_suffix(".py").is_file()
    assert "from my_app import greeting" in created.main_form.with_suffix(".py").read_text()
    names = {d.name: d.group for d in created.dependencies()}
    assert names["pyzed-ui"] == "main" and names["ruff"] == "dev" and names["ty"] == "dev"
    form = designer.load(created.main_form)
    assert form["greet"].events["click"] == "greet_click"
    # running it again on the same folder changes nothing
    again = project.init(created.root, sync=False, git=False)
    assert again.dependencies() == created.dependencies()


def _write_project(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "0.1.0"\n\n[tool.pyzed]\nui = "ui"\n')
    return project.Project.open(root)


def test_commands_open_no_console_window(tmp_path, monkeypatch):
    """The windowed Pyzed Design must not flash a console for each uv or git command, nor for a run."""
    seen = []

    class Done:
        returncode, stdout = 0, ""

    def run(args, **kwargs):
        seen.append(kwargs)
        return Done()

    def popen(args, **kwargs):
        seen.append(kwargs)
        return None

    monkeypatch.setattr(project.subprocess, "run", run)
    monkeypatch.setattr(project.subprocess, "Popen", popen)
    monkeypatch.setattr(project.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(project, "NO_WINDOW", 0x08000000)
    monkeypatch.setattr(project, "find_uv", lambda: "uv")  # CI runners may not have uv
    project.execute(["uv", "--version"])
    _write_project(tmp_path / "demo").spawn(capture=True)
    assert [kw["creationflags"] for kw in seen] == [0x08000000, 0x08000000]
    assert seen[1]["start_new_session"] == (sys.platform != "win32")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_terminate_stops_the_processes_a_run_started(tmp_path):
    """Stopping ``uv run`` also stops the Python it started, so the next run starts clean."""
    import subprocess
    import time

    pid_file = tmp_path / "child.pid"
    process = subprocess.Popen(["sh", "-c", f"sleep 30 & echo $! > {pid_file}; wait"], start_new_session=True)
    for _ in range(100):
        if pid_file.exists() and pid_file.read_text().strip():
            break
        time.sleep(0.02)
    child = int(pid_file.read_text())
    project.terminate(process)
    process.wait(timeout=5)
    for _ in range(100):
        try:
            os.kill(child, 0)
        except ProcessLookupError:
            break
        time.sleep(0.02)
    else:
        pytest.fail("the child process is still running")
