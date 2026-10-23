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



def _install(root, **packages):
    """A fake ``.venv`` with ``packages`` (name=version) installed in it."""
    site = root / ".venv" / ("Lib/site-packages" if os.name == "nt" else "lib/python3.12/site-packages")
    site.mkdir(parents=True, exist_ok=True)
    for name, version in packages.items():
        (site / f"{name}-{version}.dist-info").mkdir()
    return site


def test_installed_versions_and_problems(shop):
    assert [p.kind for p in shop.problems("0.3.1")] == ["no-environment"]
    old = shop.problems("1.7.0")
    assert [p.kind for p in old] == ["pyzed-old", "no-environment"]
    assert old[0].values == {"have": "0.3.1", "editor": "1.7.0"} and "pyzed-ui 0.3.1" in old[0].message
    _install(shop.root, pyzed_ui="1.2.0", httpx="0.28.1", ruff="0.6.0", ty="0.0.1")
    deps = {d.name: d for d in shop.dependencies()}
    assert deps["pyzed-ui"].installed == "1.2.0" and deps["pyzed-ui"].locked == "0.3.1"
    found = shop.problems("1.7.0")
    assert [p.kind for p in found] == ["pyzed-old", "not-installed"]  # .venv also disagrees with uv.lock
    assert found[0].values["have"] == "1.2.0" and found[1].values == {"count": "1", "names": "pyzed-ui"}
    assert [p.kind for p in shop.problems("1.2.0")] == ["not-installed"]
    assert project.is_older("1.2.0", "1.7.0") and not project.is_older("1.7.0", "1.7.0")
    assert not project.is_older("1.2.0", "0+unknown")  # a source tree: no version to compare with


def test_missing_pyzed_and_local_checkouts(shop):
    text = shop.root.joinpath("pyproject.toml").read_text()
    shop.root.joinpath("pyproject.toml").write_text(text.replace('"pyzed-ui>=0.3",\n', ""))
    assert [p.kind for p in shop.reload().problems("1.7.0")] == ["pyzed-missing", "no-environment"]
    shop.root.joinpath("pyproject.toml").write_text(text + '\n[tool.uv.sources]\npyzed-ui = { path = "../pyzed" }\n')
    assert shop.reload().pyzed_from_source and [p.kind for p in shop.problems("1.7.0")] == ["no-environment"]


def test_stamp_notices_changes(shop):
    before = shop.stamp()
    os.utime(shop.root / "uv.lock", ns=(1, 1))
    assert shop.stamp() != before


def test_update_pyzed(shop, monkeypatch):
    calls = []
    fails = {"add"}
    monkeypatch.setattr(project.Project, "uv", lambda self, *a, **k: calls.append(a) or
                        project.Result(["uv", *a], 1 if a[0] in fails else 0, a[0]))
    shop.update_pyzed("1.7.0")
    assert calls == [("add", "pyzed-ui>=1.7.0"), ("lock", "--upgrade-package", "pyzed-ui"), ("sync",)]
    calls.clear()
    fails.clear()
    assert shop.update_pyzed("1.7.0").ok and calls == [("add", "pyzed-ui>=1.7.0")]


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
    assert "pyzed build" in workflow.read_text() and "${{ matrix.target }}" in workflow.read_text()


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
    assert created.data["tool"]["uv"]["no-build-package"] == ["pyzed-ui"]  # wheels only, never compiled
    form = designer.load(created.main_form)
    assert form["greet"].events["click"] == "greet_click"
    # running it again on the same folder changes nothing
    again = project.init(created.root, sync=False, git=False)
    assert again.dependencies() == created.dependencies()


def test_prebuilt_installs_pyzed_from_wheels_only():
    plain = '[project]\nname = "demo"\n'
    assert project.prebuilt(plain).endswith('\n\n[tool.uv]\nno-build-package = ["pyzed-ui"]\n')
    with_table = '[project]\nname = "demo"\n\n[tool.uv]\npackage = true\n'
    assert '[tool.uv]\nno-build-package = ["pyzed-ui"]\npackage = true\n' in project.prebuilt(with_table)
    once = project.prebuilt(plain)
    assert project.prebuilt(once) == once
    checkout = plain + '\n[tool.uv.sources]\npyzed-ui = { path = "../.." }\n'  # a Pyzed checkout is built
    assert project.prebuilt(checkout) == checkout


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


def test_uv_moves_its_pythons_when_windows_cannot_open_them(tmp_path, monkeypatch):
    """Windows 11 may refuse uv's Python junctions in %APPDATA% (os error 448): uv's Pythons move to a folder of
    Pyzed's, the .venv made with the unreadable one is remade and the command runs again."""
    monkeypatch.setattr(project.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    demo = _write_project(tmp_path / "demo")
    demo.venv.mkdir()
    (demo.venv / "pyvenv.cfg").write_text(
        "home = C:\\Users\\me\\AppData\\Roaming\\uv\\python\\cpython-3.12-windows-x86_64-none\n")
    calls = []

    def run(args, cwd=None, *, timeout=None):
        calls.append(project._clean_env().get("UV_PYTHON_INSTALL_DIR"))
        if len(calls) == 1:
            return project.Result(list(args), 2, "error: La ruta no se puede recorrer (os error 448)")
        return project.Result(list(args), 0, "")

    monkeypatch.setattr(project, "execute", run)
    monkeypatch.setattr(project, "find_uv", lambda: "uv")
    assert demo.uv("add", "pyzed-ui>=1.9.0").ok
    assert calls == [None, str(project.python_install_dir())]
    assert project.python_install_dir().is_dir() and not demo.venv.exists()
    # from then on uv uses that folder, and an error 448 that moving can't fix is reported as it is
    calls.clear()
    monkeypatch.setattr(project, "execute",
                        lambda *a, **k: calls.append(1) or project.Result(["uv"], 2, "os error 448"))
    assert not demo.uv("sync").ok and calls == [1]


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
