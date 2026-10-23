"""Android apps: settings, the app folder of a project, what the bundle leaves out, the CLI and the dialog."""

import sys

import pytest

from pyzed import android, build, cli, project
from test_project import shop  # noqa: F401 - the fixture


@pytest.fixture(autouse=True)
def _uv(monkeypatch):
    monkeypatch.setattr(project, "find_uv", lambda: "uv")


def test_version_code_and_package_name():
    assert android.version_code("1.2.3") == 1_002_003
    assert android.version_code("0.0.0") == 1
    assert android.version_code("2.0") == 2_000_000
    assert android.package_name("com.acme.My-App") == "com.acme.myapp"
    assert android.package_name("shop") == "org.pyzed.shop"
    assert android.package_name("com.2fast.app") == "com.a2fast.app"


def test_options_round_trip():
    opts = android.AndroidOptions.from_table({"abis": ["x86_64", "mips"], "format": "AAB", "version-code": "7",
                                              "keystore": "release.jks"})
    assert opts.abis == ["x86_64"] and opts.format == "aab" and opts.version_code == 7
    assert opts.to_table() == {"abis": ["x86_64"], "format": "aab", "version-code": 7, "keystore": "release.jks",
                               "key-alias": "upload"}
    assert android.AndroidOptions.from_table({}).to_table() == {}


def test_release_signing_needs_the_password(tmp_path, monkeypatch):
    store = tmp_path / "release.jks"
    with pytest.raises(android.AndroidError, match="does not exist"):
        android.Signing.release(store, "upload")
    store.write_bytes(b"x")
    monkeypatch.delenv("PYZED_KEYSTORE_PASSWORD", raising=False)
    with pytest.raises(android.AndroidError, match="PYZED_KEYSTORE_PASSWORD"):
        android.Signing.release(store, "upload")
    monkeypatch.setenv("PYZED_KEYSTORE_PASSWORD", "secret")
    signing = android.Signing.release(store, "upload")
    assert signing.key_password == "secret" and not signing.debug


def test_project_app_starts_the_main_form(shop, tmp_path):  # noqa: F811
    (shop.root / ".venv").mkdir()
    (shop.root / ".venv" / "big.bin").write_bytes(b"x")
    app = android.project_app(shop, tmp_path / "app")
    main = (app / "main.py").read_text()
    assert "designer.run(ROOT / 'ui/main.pzform')" in main and "runpy" not in main
    assert (app / "project" / "ui" / "main.pzform").is_file() and not (app / "project" / ".venv").exists()
    compile(main, "main.py", "exec")


def test_project_app_runs_the_script(shop, tmp_path):  # noqa: F811
    (shop.root / "game.py").write_text("print('hi')\n")
    shop.set_startup(shop.root / "game.py")
    main = (android.project_app(shop, tmp_path / "app") / "main.py").read_text()
    assert "runpy.run_path(str(ROOT / 'game.py'), run_name='__main__')" in main
    compile(main, "main.py", "exec")


def test_bundle_leaves_out_the_editor():
    package = android.Path(android.__file__).parent
    for_forms, for_script = android._pyzed_skip(True), android._pyzed_skip(False)
    assert for_forms(package / "build.py") and for_forms(package / "cli.py") and for_forms(package / "agents")
    assert not for_forms(package / "designer") and not for_forms(package / "designer" / "runtime.py")
    assert for_forms(package / "designer" / "export_panel.py") and for_forms(package / "designer" / "app.py")
    assert for_forms(package / "templates") and not for_forms(package / "designer" / "templates")
    assert for_script(package / "designer") and not for_script(package / "app.py")


def test_binary_packages(tmp_path):
    (tmp_path / "numpy" / "core").mkdir(parents=True)
    (tmp_path / "numpy" / "core" / "_multiarray.cpython-312-x86_64-linux-gnu.so").write_bytes(b"")
    (tmp_path / "attrs").mkdir()
    (tmp_path / "attrs" / "__init__.py").write_text("")
    assert android.binary_packages(tmp_path) == ["numpy"]


def test_android_targets_and_cli(shop, monkeypatch, capsys):  # noqa: F811
    assert build.BY_TARGET["android-arm64"].os == "android" and build.host_target().os != "android"
    monkeypatch.chdir(shop.root)
    calls = []
    monkeypatch.setattr(build, "build_android", lambda p, opts, abis: calls.append(abis) or project.Result([], 1, "no SDK"))
    assert cli.build(target="android-x64") == 1 and calls == [["x86_64"]]
    assert cli.build(target="android-mips") == 2
    assert build.android_output(shop, build.BuildOptions.from_project(shop)).name == "shop.apk"


def test_build_android_reports_a_missing_sdk(shop, monkeypatch):  # noqa: F811
    monkeypatch.setattr(android, "find_sdk", lambda: None)
    result = build.build_android(shop)
    assert not result.ok and "Android SDK" in result.output


def test_export_dialog_android_section(shop, monkeypatch):  # noqa: F811
    from pyzed.designer.app import Designer
    from pyzed.designer import commands

    monkeypatch.chdir(shop.root)
    monkeypatch.setattr(sys, "path", list(sys.path))
    d = Designer(shop.main_form)
    commands.run("export", d)
    e = d.exporter
    e.show("android")
    assert d.dialog_view(d.theme_obj) is not None
    e.toggle_abi("x86_64", True)
    e.android_setter("format")("aab")
    e.android_setter("package")("com.acme.shop")
    e.android_setter("keystore")("release.jks")
    assert d.dialog_view(d.theme_obj) is not None  # with the keystore notes
    e.close()
    shop.reload()
    saved = android.AndroidOptions.from_table(shop.config["build"]["android"])
    assert saved.abis == ["arm64-v8a", "x86_64"] and saved.format == "aab" and saved.package == "com.acme.shop"
    d.logs.uninstall()
