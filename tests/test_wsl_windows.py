"""Native Windows windows for apps started in WSL (pyzed._wsl_windows), with Windows faked."""

import os
import stat
import sys

import pytest
from pathlib import Path

from pyzed import _platform
from pyzed import _wsl_windows as ww

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the WSL side runs on Linux")


@pytest.fixture
def wsl(monkeypatch):
    """Under WSL, with paths kept as they are (no wslpath) and nothing left over between tests."""
    for name in ("PYZED_WINDOWS", "PYZED_WINDOWS_WHEEL", "PYZED_WINDOWS_ENV", "PYZED_WATCH", "PYZED_CONFIG_DIR",
                 "WSLENV", "PYTHONPATH"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    monkeypatch.setattr(_platform, "is_wsl", lambda release=None: True)
    monkeypatch.setattr(ww, "to_windows", lambda path: os.path.abspath(str(path)))
    monkeypatch.setattr(ww, "_fell_back", False)
    monkeypatch.setattr(ww, "_warned", set())
    return monkeypatch


def test_paths():
    assert ww.windows_form("/mnt/c/Users/kev") == "C:\\Users\\kev"
    assert ww.windows_form("/mnt/d") == "D:\\"
    assert ww.windows_form("/home/kev/app", "Debian") == "\\\\wsl.localhost\\Debian\\home\\kev\\app"
    assert ww.linux_form("C:\\Users\\Kev Pérez\\AppData\\Local") == "/mnt/c/Users/Kev Pérez/AppData/Local"
    assert ww.linux_form("D:\\") == "/mnt/d"
    assert ww.linux_form("\\\\server\\share") is None


def test_on_under_wsl_unless_turned_off(wsl):
    assert ww.enabled()
    for value in ("0", "off", "false", "wslg"):
        wsl.setenv("PYZED_WINDOWS", value)
        assert not ww.enabled()
    wsl.setenv("PYZED_WINDOWS", "1")
    assert ww.enabled()
    wsl.setattr(_platform, "is_wsl", lambda release=None: False)
    assert not ww.enabled()


def test_requirements_leave_out_pyzed_and_local_folders():
    keep = ["httpx==0.27.2", "pywin32==306 ; sys_platform == 'win32'", "numpy>=2", "rich", "uvicorn[standard]>=0.30"]
    drop = ["pyzed-ui==1.5.0", "pyzed_ui==1.5.0", "-e ./libs/core", "./libs/core", "--only-binary pyzed-ui",
            "# via httpx", "", "core @ file:///home/kev/core", "core @ ./libs/core",
            "warning: The `UV_NATIVE_TLS` environment variable is deprecated"]
    assert [line for line in keep + drop if ww.keep_requirement(line)] == keep


def test_script_requirements(tmp_path):
    script = tmp_path / "main.py"
    script.write_text('# /// script\n# dependencies = ["httpx", "pyzed-ui"]\n# ///\nimport pyzed\n', encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("--only-binary pyzed-ui\npyzed-ui\nrich\n", encoding="utf-8")
    assert ww.script_requirements(script) == ["httpx", "rich"]


def test_pyzed_requirement(wsl, tmp_path):
    wheel = tmp_path / "pyzed_ui-9.9.9-cp310-abi3-win_amd64.whl"
    wheel.write_bytes(b"")
    wsl.setenv("PYZED_WINDOWS_WHEEL", str(wheel))
    assert ww.pyzed_requirement() == (str(wheel), True)
    wsl.setenv("PYZED_WINDOWS_WHEEL", "https://example.com/pyzed_ui.whl")
    assert ww.pyzed_requirement() == ("https://example.com/pyzed_ui.whl", True)
    wsl.delenv("PYZED_WINDOWS_WHEEL")
    spec, exact = ww.pyzed_requirement()
    assert spec == "pyzed-ui" or (exact and spec.startswith("pyzed-ui=="))


def test_script_args(tmp_path):
    script = tmp_path / "app.py"
    script.write_text("", encoding="utf-8")
    assert ww.script_args([str(script), "--big"], ["python3", "-X", "utf8", str(script), "--big"]) == [
        str(script), "--big"]
    # -m after the script belongs to the script
    assert ww.script_args([str(script), "-m", "x"], ["python3", str(script), "-m", "x"]) == [str(script), "-m", "x"]
    assert ww.script_args(["/x/demo/__main__.py", "a"], ["python3", "-u", "-m", "demo", "a"]) == ["-m", "demo", "a"]
    assert ww.script_args(["-c"], ["python3", "-c", "import pyzed"]) is None
    assert ww.script_args([""], ["python3"]) is None


def _fake_host(tmp_path, *, fail_exact=False):
    """A Windows with a fake uv.exe that makes ``Scripts/python.exe`` and logs what it installs."""
    log = tmp_path / "uv.log"
    uv = tmp_path / "uv.exe"
    uv.write_text(f"""#!/bin/sh
echo "$@" >> {log}
if [ "$1" = venv ]; then
  for last; do :; done
  mkdir -p "$last/Scripts"
  printf '#!/bin/sh\\nexit 0\\n' > "$last/Scripts/python.exe"
  chmod +x "$last/Scripts/python.exe"
fi
if [ "$1" = pip ] && {'true' if fail_exact else 'false'}; then
  for last; do :; done
  grep -q '==' "$last" && {{ echo 'No solution found: pyzed-ui==1.0 has no wheels'; exit 1; }}
fi
exit 0
""", encoding="utf-8")
    uv.chmod(uv.stat().st_mode | stat.S_IEXEC)
    lad = tmp_path / "AppData" / "Local"
    lad.mkdir(parents=True)
    return ww.Host(str(lad), str(tmp_path), uv=str(uv)), log


def test_environment_is_made_once(wsl, tmp_path):
    host, log = _fake_host(tmp_path)
    env = ww.WindowsEnv(host, "ubuntu-app-1234abcd-py312", ["httpx==0.27.2"], "pyzed-ui==1.5.0",
                        python_version="3.12")
    notes = []
    assert env.prepare(notes.append) is None
    assert env.ready and env.python.is_file() and env.bootstrap.read_text(encoding="utf-8") == ww.BOOTSTRAP
    assert "pyzed-ui==1.5.0\nhttpx==0.27.2\n" in (env.base / "installed.txt").read_text(encoding="utf-8")
    calls = log.read_text(encoding="utf-8").splitlines()
    assert calls[0].startswith("venv --allow-existing --python 3.12 ")
    assert "--only-binary pyzed-ui" in calls[1]
    assert notes and "preparing the Windows environment" in notes[0]
    # nothing to do the second time; a new dependency installs again
    assert env.prepare(notes.append) is None and len(log.read_text(encoding="utf-8").splitlines()) == 2
    env.requirements.append("rich")
    assert not env.ready and env.prepare(notes.append) is None and env.ready


def test_unpublished_version_falls_back_to_the_latest_release(wsl, tmp_path):
    host, _ = _fake_host(tmp_path, fail_exact=True)
    env = ww.WindowsEnv(host, "ubuntu-scripts-0-py312", [], "pyzed-ui==1.0", python_version="3.12")
    notes = []
    assert env.prepare(notes.append) is None and env.ready
    assert any("using the latest release" in n for n in notes)


def test_environment_variables_cross_to_windows(wsl, tmp_path):
    host, _ = _fake_host(tmp_path)
    env = ww.WindowsEnv(host, "e", [], "pyzed-ui", paths=["\\\\wsl.localhost\\Ubuntu\\app\\ui", "\\\\wsl\\app"])
    wsl.setenv("WSLENV", "USERPROFILE/p:PYTHONPATH/l")
    wsl.setenv("PYZED_DESIGNER_RUN", "1")
    wsl.setenv("PYZED_WINDOWS", "1")
    wsl.setenv("PYZED_WATCH", f"{tmp_path}:/srv")
    wsl.setenv("OPENAI_API_KEY", "sk-test")
    wsl.setenv("SECRET", "no")
    wsl.setenv("PYZED_WINDOWS_ENV", "OPENAI_API_KEY, MISSING")
    found = env.environ(str(tmp_path))
    listed = found["WSLENV"].split(":")
    assert "USERPROFILE/p" in listed and "PYTHONPATH/l" not in listed and "PYTHONPATH" in listed
    assert {"PYZED_DESIGNER_RUN", "PYZED_WATCH", "OPENAI_API_KEY", "PYTHONUTF8", "PYZED_WSL_CWD"} <= set(listed)
    assert "PYZED_WINDOWS" not in listed and "SECRET" not in listed and "MISSING" not in listed
    assert found["PYTHONPATH"] == "\\\\wsl.localhost\\Ubuntu\\app\\ui;\\\\wsl\\app"
    assert found["PYZED_WATCH"] == f"{tmp_path};/srv" and found["PYZED_WSL_CWD"] == str(tmp_path)


def test_launch_waits_and_passes_the_exit_code(wsl, tmp_path):
    import subprocess
    import threading

    host, _ = _fake_host(tmp_path)
    env = ww.WindowsEnv(host, "e", [], "pyzed-ui")
    env.python.parent.mkdir(parents=True)
    out = tmp_path / "args.txt"
    # The fake python.exe records its arguments, then waits for stdin to close like the bootstrap does.
    env.python.write_text(f'#!/bin/sh\necho "$@" > {out}\ncat > /dev/null\nexit 7\n', encoding="utf-8")
    env.python.chmod(0o755)
    script = tmp_path / "app.py"
    script.write_text("", encoding="utf-8")
    started, codes = [], []
    real = subprocess.Popen
    wsl.setattr(subprocess, "Popen", lambda *a, **k: started.append(real(*a, **k)) or started[-1])
    thread = threading.Thread(target=lambda: codes.append(env.launch([str(script), "rel/path", "-v"],
                                                                      str(tmp_path))))
    thread.start()
    thread.join(0.5)
    assert thread.is_alive()  # the pipe from this side stays open while this side runs
    assert out.read_text(encoding="utf-8").split() == [str(env.bootstrap), str(script), "rel/path", "-v"]
    started[0].stdin.close()
    thread.join(5)
    assert codes == [7]


def test_falls_back_to_wslg_without_python_on_windows(wsl, capsys):
    wsl.setattr(ww, "host", lambda refresh=False: ww.Host("/mnt/c/x", "/mnt/c/u"))
    assert ww.handoff(["-m", "pyzed", "design"]) is None
    assert "pyzed windows setup" in capsys.readouterr().err
    # decided once: a later pz.run does not look again
    wsl.setattr(ww, "host", lambda refresh=False: pytest.fail("looked again"))
    assert ww.handoff(["app.py"]) is None


def test_turned_off_never_looks(wsl):
    wsl.setenv("PYZED_WINDOWS", "0")
    wsl.setattr(ww, "host", lambda refresh=False: pytest.fail("looked"))
    assert ww.handoff(["app.py"]) is None


def test_cli_hands_design_over(wsl, tmp_path):
    from pyzed import cli

    seen = {}

    def handoff(args, project=None, script=None, cwd=None):
        seen.update(args=args, project=project, script=script)
        return 5

    wsl.setattr(ww, "handoff", handoff)
    wsl.chdir(tmp_path)
    assert cli.main(["design", "main.pzform"]) == 5
    assert seen["args"] == ["-m", "pyzed", "design", "main.pzform"] and seen["project"] is None
    (tmp_path / "app.py").write_text("", encoding="utf-8")
    assert cli.main(["dev", "app.py", "--x"]) == 5
    assert seen["script"] == (tmp_path / "app.py").resolve()


def test_cli_wslg_option(wsl, tmp_path):
    from pyzed import cli

    wsl.setattr(ww, "handoff", lambda *a, **k: pytest.fail("handed over"))
    wsl.setattr(cli, "design", lambda form: 0)
    assert cli.main(["design", "--wslg"]) == 0
    assert os.environ["PYZED_WINDOWS"] == "0"


def test_pz_run_hands_over_under_wsl(wsl):
    import pyzed as pz
    from pyzed import app as app_module

    wsl.setattr(ww, "handoff_script", lambda: 3)
    wsl.setattr(app_module._core, "run", lambda app: pytest.fail("opened here"))

    class Demo(pz.App):
        def view(self):
            return pz.text("hi")

    with pytest.raises(SystemExit) as exit_info:
        pz.run(Demo)
    assert exit_info.value.code == 3


def test_status_outside_wsl(monkeypatch, capsys):
    from pyzed import cli

    monkeypatch.setattr(_platform, "is_wsl", lambda release=None: False)
    assert cli.main(["windows"]) == 0
    assert "not WSL" in capsys.readouterr().out


def test_bootstrap_runs_a_script_and_a_module(tmp_path):
    import subprocess

    boot = tmp_path / "bootstrap.py"
    boot.write_text(ww.BOOTSTRAP, encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "__main__.py").write_text("import sys\nprint('module', sys.argv[1:])\n", encoding="utf-8")
    app = tmp_path / "sub" / "app.py"
    app.parent.mkdir()
    (app.parent / "helper.py").write_text("X = 42\n", encoding="utf-8")
    app.write_text("import sys, helper\nprint('script', helper.X, sys.argv[1:])\nsys.exit(4)\n", encoding="utf-8")
    env = {**os.environ, "PYZED_WSL_CWD": str(tmp_path)}

    def run(*args):  # stdin stays open, like the pipe from the WSL side
        process = subprocess.Popen([sys.executable, str(boot), *args], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, env=env, cwd="/")
        out = process.stdout.read()
        code = process.wait(30)
        process.stdin.close()
        return code, out

    code, out = run("sub/app.py", "a")
    assert code == 4 and b"script 42 ['a']" in out
    assert b"module ['b']" in run("-m", "pkg", "b")[1]
    # a long-running app ends when the WSL side closes the pipe
    app.write_text("import time\nprint('up', flush=True)\ntime.sleep(60)\n", encoding="utf-8")
    process = subprocess.Popen([sys.executable, str(boot), str(app)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               env=env)
    assert process.stdout.readline() == b"up\n"
    process.stdin.close()
    assert process.wait(10) == 0


def test_describe_mentions_windows(wsl):
    from pyzed import project

    env = project.Environment("wsl", "Ubuntu")
    assert "native Windows windows" in env.describe()
    wsl.setenv("PYZED_WINDOWS", "0")
    assert "WSLg" in env.describe()


def test_mcp_environment_reports_where_windows_open(wsl):
    from pyzed.mcp import projects

    wsl.setattr(projects, "_is_wsl", lambda: True)
    assert projects.environment()["windows_open_on"].startswith("Windows")


# -- a checkout of Pyzed ------------------------------------------------------------------------------------


def test_checkout_is_found_next_to_the_sources(monkeypatch, tmp_path):
    module = tmp_path / "python" / "pyzed" / "_wsl_windows.py"
    module.parent.mkdir(parents=True)
    monkeypatch.setattr(ww, "__file__", str(module))
    assert ww.checkout() is None  # an installed wheel: no Cargo.toml above it
    (tmp_path / "Cargo.toml").write_text("[package]", encoding="utf-8")
    assert ww.checkout() == tmp_path.resolve()


def test_core_hash_follows_the_rust_sources(tmp_path):
    (tmp_path / "src").mkdir()
    rs = tmp_path / "src" / "lib.rs"
    rs.write_text("fn main() {}", encoding="utf-8")
    (tmp_path / "Cargo.toml").write_text("[package]", encoding="utf-8")
    first = ww.core_hash(tmp_path)
    (tmp_path / "python.py").write_text("x = 1", encoding="utf-8")  # Python files do not count
    assert ww.core_hash(tmp_path) == first
    rs.write_text("fn main() { loop {} }", encoding="utf-8")
    assert ww.core_hash(tmp_path) != first


def _fake_maturin(tmp_path, *, fail=False):
    """A maturin that writes a wheel with a fake Windows core into --out."""
    import zipfile

    wheel = tmp_path / "built.whl"
    with zipfile.ZipFile(wheel, "w") as zf:
        zf.writestr("pyzed/_core.pyd", b"MZ fake core")
        zf.writestr("pyzed/__init__.py", "")
    script = tmp_path / "maturin"
    script.write_text(f"""#!/bin/sh
echo "Compiling pyzed v1.0.0"
echo "PATH=$PATH"
{'exit 1' if fail else ''}
while [ "$1" != "--out" ]; do shift; done
cp {wheel} "$2/pyzed_ui-1.0.0-cp310-abi3-win_amd64.whl"
""", encoding="utf-8")
    script.chmod(0o755)
    return [str(script)]


def test_build_core_extracts_the_windows_core(wsl, tmp_path):
    wsl.setenv("PATH", "/mnt/c/Windows/System32:/usr/bin:/bin:/mnt/c/Users/kev/AppData/Local/Microsoft/WindowsApps")
    wsl.setattr(ww, "_maturin", lambda: _fake_maturin(tmp_path))
    wsl.setattr(ww, "_rustup", lambda: None)
    wsl.setenv("PYZED_WINDOWS_TARGET", "x86_64-pc-windows-msvc")
    lines = []
    assert ww.build_core(tmp_path, tmp_path / "core", lines.append) is None
    assert (tmp_path / "core" / "_core.pyd").read_bytes() == b"MZ fake core"
    assert any("Compiling pyzed" in line for line in lines)
    # Windows' folders are left out, so maturin does not find the Microsoft Store's python.exe
    path = next(line for line in lines if line.startswith("PATH="))
    assert "/mnt/c/Windows" not in path and "/usr/bin" in path


def test_build_core_explains_the_toolchain_when_it_fails(wsl, tmp_path):
    wsl.setattr(ww, "_maturin", lambda: _fake_maturin(tmp_path, fail=True))
    wsl.setattr(ww, "_rustup", lambda: None)
    wsl.setenv("PYZED_WINDOWS_TARGET", "x86_64-pc-windows-msvc")
    error = ww.build_core(tmp_path, tmp_path / "core", lambda line: None)
    assert "the build failed" in error and "Compiling" in error and not (tmp_path / "core").exists()
    assert "mingw-w64" not in error  # the cross compiler is there: the advice to install it would mislead


def test_checkout_uses_its_sources_and_a_core_built_for_windows(wsl, tmp_path):
    host, log = _fake_host(tmp_path)
    source = tmp_path / "pyzed-checkout"
    (source / "python" / "pyzed").mkdir(parents=True)
    (source / "Cargo.toml").write_text("[package]", encoding="utf-8")
    wsl.setattr(ww, "checkout", lambda: source)
    wsl.setattr(ww, "editor_requirements", lambda: ["anthropic>=1.0"])
    built = []

    def build(root, out, log=print):
        built.append(root)
        out.mkdir(parents=True)
        (out / "_core.pyd").write_bytes(b"MZ")

    wsl.setattr(ww, "build_core", build)
    env = ww.WindowsEnv.for_target(host, None, None)
    assert env.source == source and env.pyzed == "" and env.paths == [str(source / "python")]
    assert env.prepare(lambda line: None) is None and built == [source]
    assert "# Pyzed from" in (env.base / "installed.txt").read_text(encoding="utf-8")
    assert "pyzed-ui" not in (env.base / "requirements.txt").read_text(encoding="utf-8")  # not from the index
    variables = env.variables()
    assert variables["PYZED_CORE_DIR"] == str(env.core) and variables["PYTHONPATH"] == str(source / "python")
    # built once per version of the Rust sources
    assert env.prepare(lambda line: None) is None and len(built) == 1


def test_the_project_and_what_crossed_are_named(wsl, tmp_path):
    host, _ = _fake_host(tmp_path)
    env = ww.WindowsEnv(host, "e", [], "pyzed-ui", project_root="/home/kev/app")
    found = env.environ(str(tmp_path))
    assert found["PYZED_WSL_PROJECT"] == "/home/kev/app" and found["PYZED_WSL_DISTRO"] == "Ubuntu"
    crossed = found["PYZED_WSL_CROSSED"].split(":")
    assert {"PYZED_WSL_PROJECT", "PYTHONUTF8", "PYZED_WSL_CWD", "PYZED_WSL_CROSSED"} <= set(crossed)


def test_bootstrap_keeps_what_crossed_out_of_wslenv(tmp_path):
    import subprocess

    boot = tmp_path / "bootstrap.py"
    boot.write_text(ww.BOOTSTRAP, encoding="utf-8")
    app = tmp_path / "app.py"
    app.write_text("import os\nprint(os.environ['WSLENV'])\n", encoding="utf-8")
    env = {**os.environ, "WSLENV": "USERPROFILE/p:PYTHONPATH:PYZED_WSL_CROSSED",
           "PYZED_WSL_CROSSED": "PYTHONPATH:PYZED_WSL_CROSSED"}
    process = subprocess.Popen([sys.executable, str(boot), str(app)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               env=env)
    out = process.stdout.read()
    process.wait(30)
    process.stdin.close()
    assert out.strip() == b"USERPROFILE/p"


# -- Pyzed Design on Windows, started from WSL ------------------------------------------------------------------


@pytest.fixture
def served(monkeypatch, tmp_path):
    """A WSL project opened by Pyzed Design on Windows, which Pyzed started from WSL for it."""
    from pyzed import project

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "app"\n\n[tool.pyzed]\nscript = "main.py"\n',
                                             encoding="utf-8")
    (tmp_path / "main.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(project.Environment, "remote", property(lambda self: self.is_wsl))
    monkeypatch.setattr(project, "environment", lambda path=None: project.Environment("wsl", "Ubuntu"))
    monkeypatch.setenv("PYZED_WSL_PROJECT", str(tmp_path))
    monkeypatch.setenv("PYZED_WSL_DISTRO", "Ubuntu")
    return project.Project.open(tmp_path)


def test_served_project_runs_on_windows(served, monkeypatch):
    assert served.served_from_wsl and served.uses_own_venv and served.can_run_in_process
    assert served.run_args(served.root / "ui" / "main.pzform", reload=True) == [
        sys.executable, "-m", "pyzed", "run", str(served.root / "ui" / "main.pzform"), "--reload"]
    monkeypatch.setenv("PYZED_WSL_PROJECT", "/home/kev/other")
    assert not served.served_from_wsl and served.run_args()[1] == "run"


def test_served_script_starts_here(served):
    process = served.spawn_script(capture=True)
    assert process.args == [sys.executable, str(served.root / "main.py")]
    assert process.wait(30) == 0


def test_creating_and_cloning_in_wsl_use_linux_tools(monkeypatch, tmp_path):
    from pyzed import project

    monkeypatch.setattr(project.Environment, "remote", property(lambda self: self.is_wsl))
    monkeypatch.setattr(project, "environment", lambda path=None: project.Environment("wsl", "Ubuntu"))
    seen = []
    monkeypatch.setattr(project, "execute", lambda args, cwd=None, timeout=None: seen.append(args) or
                        project.Result(args, 1, "stop here"))
    assert not project.clone("https://example.com/app.git", tmp_path / "work" / "app").ok
    assert seen[-1][:2] == ["wsl.exe", "-d"] and seen[-1][-4:] == ["git", "clone", "https://example.com/app.git",
                                                                    str(tmp_path / "work" / "app")]
    with pytest.raises(RuntimeError, match="stop here"):
        project.init(tmp_path / "new")
    assert seen[-1][0] == "wsl.exe" and "uv" in seen[-1] and "init" in seen[-1]


def test_targets_follow_the_installed_cross_compilers(wsl):
    tools = set()
    wsl.setattr(ww.shutil, "which", lambda name, *a, **k: f"/usr/bin/{name}" if name in tools else None)
    # The wheel tests run without maturin installed.
    wsl.setattr(ww, "_maturin", lambda: ["maturin"])
    assert ww.targets() == []
    assert "sudo apt install mingw-w64" in ww.build_core(Path("."), Path("core"), lambda line: None)
    tools.add("x86_64-w64-mingw32-gcc")
    assert ww.targets() == ["x86_64-pc-windows-gnu"]
    tools.update({"clang", "lld-link"})
    assert ww.targets() == ["x86_64-pc-windows-msvc", "x86_64-pc-windows-gnu"]
    wsl.setenv("PYZED_WINDOWS_TARGET", "aarch64-pc-windows-msvc")
    assert ww.targets() == ["aarch64-pc-windows-msvc"]


def test_bootstrap_gives_its_programs_no_stdin(tmp_path):
    """The WSL side's pipe is the bootstrap's stdin; a program started from the app must not get it (on Windows
    a read waiting on that pipe blocks any other use of it, so git or wsl.exe hung the editor for ever)."""
    import subprocess

    boot = tmp_path / "bootstrap.py"
    boot.write_text(ww.BOOTSTRAP, encoding="utf-8")
    app = tmp_path / "app.py"
    app.write_text("import subprocess, sys\n"
                   "out = subprocess.run([sys.executable, '-c', 'import sys; print(len(sys.stdin.read()))'],\n"
                   "                     capture_output=True, text=True, timeout=20)\n"
                   "print('child read', out.stdout.strip(), len(sys.stdin.read()))\n", encoding="utf-8")
    process = subprocess.Popen([sys.executable, str(boot), str(app)], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        out = process.stdout.read()
        assert process.wait(30) == 0
    finally:
        process.stdin.close()
    assert b"child read 0 0" in out
