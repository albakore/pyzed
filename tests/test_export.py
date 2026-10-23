"""Exporting apps: build options in pyproject.toml, PyInstaller and Nuitka command lines, icons, the splash
screen, CI workflows and the designer's Export dialog."""

import struct
import sys

import pytest

from pyzed import _appicon, _core, build, project
from test_project import shop  # noqa: F401 - the fixture

HERE = build.host_target()


@pytest.fixture(autouse=True)
def _uv(monkeypatch):
    monkeypatch.setattr(project, "find_uv", lambda: "uv")  # CI runners may not have uv


def _png(tmp_path, name="icon.png", size=(64, 64)):
    """A PNG made by the core (no Pillow needed)."""
    import zlib

    width, height = size
    raw = b"".join(b"\x00" + bytes([200, 80, 40, 255]) * width for _ in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    path = tmp_path / name
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    return path


def test_image_helpers_resize_to_png(tmp_path):
    source = _png(tmp_path, size=(40, 20))
    assert _core.image_size(str(source)) == (40, 20)
    data = _core.resize_image(str(source), 16, 16)
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and _core.image_size(data) == (16, 16)
    with pytest.raises(ValueError):
        _core.resize_image(b"not an image", 16, 16)


def test_icon_files_hold_every_size(tmp_path):
    written = _appicon.write_all(_png(tmp_path), tmp_path / "out")
    ico = written["ico"].read_bytes()
    reserved, kind, count = struct.unpack("<HHH", ico[:6])
    assert (reserved, kind, count) == (0, 1, len(_appicon.ICO_SIZES))
    sides = [ico[6 + 16 * i] or 256 for i in range(count)]
    assert sides == list(_appicon.ICO_SIZES)
    size, offset = struct.unpack("<II", ico[6 + 8: 6 + 16])
    assert ico[offset:offset + 8] == b"\x89PNG\r\n\x1a\n" and size > 0
    icns = written["icns"].read_bytes()
    assert icns[:4] == b"icns" and struct.unpack(">I", icns[4:8])[0] == len(icns)
    kinds, at = [], 8
    while at < len(icns):
        kinds.append(icns[at:at + 4].decode())
        at += struct.unpack(">I", icns[at + 4:at + 8])[0]
    assert kinds == [k for k, _ in _appicon.ICNS_TYPES]
    assert _core.image_size(str(written["png"])) == (256, 256)


def test_options_round_trip_through_pyproject(shop):  # noqa: F811
    opts = build.BuildOptions.from_project(shop)
    assert opts.backend == "pyinstaller" and opts.name == "Shop" and opts.slim
    opts.backend, opts.onefile, opts.icon = "nuitka", True, "assets/icon.png"
    opts.splash = build.Splash("assets/splash.png", 2.0, "Loading…")
    opts.targets = ["linux-x64", "windows-x64"]
    opts.backend_options = {"nuitka": {"args": ["--lto=yes"]}}
    build.save_options(shop, opts)
    text = (shop.root / "pyproject.toml").read_text(encoding="utf-8")
    assert text.count("[tool.pyzed.build]") == 1 and "[tool.pyzed.build.splash]" in text
    assert 'ui = "ui"' in text and "[dependency-groups]" in text  # the rest of the file is kept
    again = build.BuildOptions.from_project(shop)
    assert again.to_table() == opts.to_table()
    assert again.splash == opts.splash and again.backend_options == {"nuitka": {"args": ["--lto=yes"]}}
    assert again.backend_args() == ["--lto=yes"]
    parsed = project._mini_toml(text)["tool"]["pyzed"]["build"]  # Python 3.10 reads it too
    assert parsed["splash"]["text"] == "Loading…" and parsed["targets"] == ["linux-x64", "windows-x64"]
    # saving again replaces the tables instead of adding more
    build.save_options(shop, again)
    assert (shop.root / "pyproject.toml").read_text(encoding="utf-8").count("[tool.pyzed.build.splash]") == 1


def test_pyinstaller_build_with_icon_splash_and_metadata(shop, tmp_path):  # noqa: F811
    _png(shop.root / "assets", "icon.png", (128, 128))
    _png(shop.root / "assets", "splash.png", (300, 200))
    opts = build.BuildOptions.from_project(shop, icon="assets/icon.png", version="2.0.1", publisher="Acme",
                                           splash=build.Splash("assets/splash.png", 1.0, "Hi"), optimize=1)
    plan = build.prepare(shop, opts)
    args = plan.command
    assert args[1:4] == ["run", "--with", build.PYINSTALLER]
    work = shop.root / "build" / "pyzed"
    assert plan.work == work and plan.dist == shop.root / "dist"
    assert args[args.index("--distpath") + 1] == str(plan.dist)
    assert ["--optimize", "1"] == args[args.index("--optimize"):args.index("--optimize") + 2]
    assert "--noupx" in args and ("--strip" in args) == (HERE.os != "windows")
    if HERE.os == "macos":
        assert args[args.index("--icon") + 1] == str(work / "app-icon.icns")
    elif HERE.os == "windows":
        assert args[args.index("--icon") + 1] == str(work / "app-icon.ico")
    assert (work / "app-icon.ico").is_file() and (work / "app-icon.icns").is_file()
    data = [args[i + 1] for i, a in enumerate(args) if a == "--add-data"]
    sep = ";" if HERE.os == "windows" else ":"
    assert f"{work / 'app-icon.png'}{sep}." in data and f"{work / 'splash.png'}{sep}." in data
    # no .venv here, so no Tk for PyInstaller's own splash (which macOS never has): only the Pyzed one
    assert "--splash" not in args
    assert any("Tk" in w for w in plan.warnings) == (HERE.os != "macos")
    excluded = {args[i + 1] for i, a in enumerate(args) if a == "--exclude-module"}
    assert "idlelib" in excluded and "tkinter" not in excluded  # Tk draws PyInstaller's splash
    launcher = (work / "shop_app_launcher.py").read_text(encoding="utf-8")
    compile(launcher, "launcher", "exec")
    assert "pz.Window.icon = str(ROOT / 'app-icon.png')" in launcher
    assert "close_native_splash()" in launcher
    assert "splash=pz.Splash(ROOT / 'splash.png', duration=1.0, text='Hi')" in launcher
    version = build.windows_version_file(shop, opts)
    assert "filevers=(2, 0, 1, 0)" in version and "StringStruct('CompanyName', 'Acme')" in version
    assert plan.output.name in ("Shop", "Shop.app")


def test_nuitka_command_line(shop):  # noqa: F811
    _png(shop.root / "assets", "icon.png", (64, 64))
    opts = build.BuildOptions.from_project(shop, backend="nuitka", icon="assets/icon.png", optimize=2,
                                           exclude=["numpy.tests"])
    plan = build.prepare(shop, opts)
    args = plan.command
    nuitka = args.index("nuitka")
    assert args[:3] == [args[0], "run", "--with"] and build.NUITKA in args and args[nuitka - 2:nuitka] == ["python", "-m"]
    assert ("patchelf" in args) == (HERE.os == "linux")
    assert "--mode=standalone" in args or "--mode=app-dist" in args
    assert "--output-filename=Shop" in args and "--output-folder-name=Shop" in args
    assert f"--include-data-dir={shop.ui_dir}=ui" in args
    assert f"--include-data-files={shop.ui_dir}=ui/=**/*.py" in args
    assert "--include-module=shop_app.plugins" in args and "--include-package=shop_app" in args
    assert "--python-flag=no_asserts" in args and "--python-flag=no_docstrings" in args
    nofollow = next(a for a in args if a.startswith("--nofollow-import-to="))
    assert "tkinter" in nofollow and "numpy.tests" in nofollow
    env = build.environment(plan)
    assert str(shop.root / "src") in env["PYTHONPATH"]
    onefile = build.prepare(shop, build.BuildOptions.from_project(shop, backend="nuitka", onefile=True)).command
    assert "zstandard" in onefile and ("--mode=onefile" in onefile or "--mode=app" in onefile)


def test_finish_moves_nuitka_output_and_packs_it(shop):  # noqa: F811
    opts = build.BuildOptions.from_project(shop, backend="nuitka", archive="zip")
    plan = build.prepare(shop, opts)
    built = plan.work / "nuitka" / "Shop"
    built.mkdir(parents=True)
    (built / "Shop").write_text("binary")
    if HERE.os == "macos":
        pytest.skip("a Nuitka app bundle on macOS")
    notes = build.finish(plan)
    assert (plan.output / "Shop").read_text() == "binary" and not built.exists()
    assert plan.archive_path is not None and plan.archive_path.name == f"shop-{HERE.os}-{HERE.machine}.zip"
    assert plan.archive_path.is_file() and any("Packed" in n for n in notes)
    assert build.size_of(plan.output) == 6 and build.human_size(2048) == "2.0 KB"
    from pyzed import updater

    assert plan.archive_path.name == updater.asset_name("shop")  # what the app's self-updater downloads


def test_finish_fills_in_the_macos_info_plist(shop, monkeypatch):  # noqa: F811
    import plistlib

    mac = build.BY_TARGET["macos-arm64"]
    monkeypatch.setattr(build, "host_target", lambda project=None: mac)
    opts = build.BuildOptions.from_project(shop, version="3.1.0", copyright="© Acme", identifier="com.acme.shop")
    plan = build.prepare(shop, opts)
    assert plan.output == shop.root / "dist" / "Shop.app"
    assert ["--osx-bundle-identifier", "com.acme.shop"] == plan.command[plan.command.index("--osx-bundle-identifier"):][:2]
    info = plan.output / "Contents" / "Info.plist"
    info.parent.mkdir(parents=True)
    info.write_bytes(plistlib.dumps({"CFBundleName": "Shop"}))
    build.finish(plan)
    data = plistlib.loads(info.read_bytes())
    assert data["CFBundleShortVersionString"] == "3.1.0" and data["NSHumanReadableCopyright"] == "© Acme"
    assert data["CFBundleIdentifier"] == "com.acme.shop"


def test_workflow_builds_each_target(shop):  # noqa: F811
    path = build.workflow(shop, targets=["windows-arm64", "linux-x64", "macos-x64"])
    text = path.read_text(encoding="utf-8")
    assert "- { target: windows-arm64, runner: windows-11-arm }" in text
    assert "- { target: macos-x64, runner: macos-15-intel }" in text
    assert "uv run pyzed build --target ${{ matrix.target }}" in text and "path: dist/" in text
    assert "linux-arm64" not in text and "gh release" not in text
    opts = build.BuildOptions.from_project(shop, archive="zip")
    build.save_options(shop, opts)
    text = build.workflow(shop, targets=["linux-x64"]).read_text(encoding="utf-8")
    assert "contents: write" in text and 'gh release upload "$GITHUB_REF_NAME" dist/*.zip --clobber' in text


def test_cli_refuses_other_targets(shop, monkeypatch, capsys):  # noqa: F811
    from pyzed.cli import main as cli_main

    monkeypatch.chdir(shop.root)
    other = next(t for t in build.TARGETS if t.os != HERE.os)
    assert cli_main(["build", "--target", other.id]) == 2
    assert "--workflow" in capsys.readouterr().err
    assert cli_main(["build", "--backend", "nuitka", "--dry-run"]) == 0
    assert "nuitka" in capsys.readouterr().out


def test_host_target_and_identifier(shop, monkeypatch):  # noqa: F811
    assert HERE.id in build.BY_TARGET and HERE.os == {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    opts = build.BuildOptions.from_project(shop, publisher="Acme Inc.")
    assert build.app_identifier(shop, opts) == "com.acmeinc.shop"
    monkeypatch.setattr(type(shop), "environment", property(lambda self: project.Environment("wsl", "Ubuntu")))
    monkeypatch.setattr(sys, "platform", "win32")
    assert build.host_target(shop).os == "linux"  # a WSL project builds inside WSL


def test_splash_window(tmp_path):
    import pyzed as pz

    picture = _png(tmp_path, "splash.png", (1800, 600))
    splash = pz.Splash(picture, duration=0.5, text="Loading…")
    assert splash.size == (900, 300) and not splash.decorations and splash.position == "center"
    assert splash.duration == 0.5 and isinstance(splash.view(), _core.Widget)
    assert pz.Splash(tmp_path / "missing.png").size == (480.0, 320.0)


def test_splash_opens_before_the_main_window(tmp_path):
    """The app's splash shows first; the main window and on_start follow after its duration."""
    import pyzed as pz

    class Main(pz.App):
        started = False

        def on_start(self):
            Main.started = True

        def view(self):
            return pz.text("main")

    app = Main()
    app.splash = pz.Splash(_png(tmp_path), duration=0.0)
    app.icon = str(_png(tmp_path, "icon.png"))
    out = tmp_path / "shot.png"
    app.screenshot(out, size=(200, 100))  # off-screen: no splash, the main window as usual
    assert out.is_file() and Main.started


def test_export_dialog(shop, monkeypatch):  # noqa: F811
    from pyzed.designer.app import Designer
    from pyzed.designer import commands, export_panel

    monkeypatch.chdir(shop.root)  # opening the project changes the folder and sys.path: put both back after
    monkeypatch.setattr(sys, "path", list(sys.path))
    d = Designer(shop.main_form)
    assert d.projects.project is not None and d.projects.project.root == shop.root
    commands.run("export", d)
    e = d.exporter
    assert d.dialog == "export" and e.opts is not None and e.opts.targets == [HERE.id]
    for section in export_panel.SECTIONS:
        e.show(section)
        assert d.dialog_view(d.theme_obj) is not None
    e.setter("backend")("nuitka")
    e.adding["include"] = "data"
    e.add_item("include")
    e.set_splash(True)
    e.splash_setter("image")("assets/splash.png")
    e.toggle_target("linux-arm64", True)
    assert e.dirty
    e.close()
    shop.reload()  # the designer wrote it
    saved = build.BuildOptions.from_project(shop)
    assert saved.backend == "nuitka" and saved.include == ["assets", "data"] and saved.splash.image == "assets/splash.png"
    assert "linux-arm64" in saved.targets and d.dialog is None
    e.write_workflow()
    assert (shop.root / ".github" / "workflows" / "build.yml").is_file()
    d.logs.uninstall()


def test_export_failure_shows_the_reason(shop, monkeypatch):  # noqa: F811
    import asyncio

    from pyzed.designer import commands
    from pyzed.designer.app import Designer

    monkeypatch.chdir(shop.root)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(project, "find_uv", lambda: "uv")
    d = Designer(shop.main_form)
    commands.run("export", d)

    def broken(*args, **kwargs):
        raise RuntimeError("PyInstaller is missing")

    monkeypatch.setattr(build, "prepare", broken)
    then = asyncio.run(d.exporter.build())
    then()  # the error ran out of its except block before this: it must still be there
    assert d.exporter.state == "failed" and d.exporter.message == "PyInstaller is missing"
    d.logs.uninstall()
