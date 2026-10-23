"""Android apps: ``pyzed build --target android-arm64`` packs a Pyzed app as an APK, or an AAB for Google Play.

The app is a NativeActivity, so the APK has no Java code. Pyzed's engine built for Android
(``lib_core.so``, with Python embedded) is its entry point: on the first start it unpacks
``pyzed-bundle.zip`` from the APK's assets (Python's standard library, Pyzed and the app), starts
Python 3.13 and runs the app's ``main.py``. Python for Android comes from Maven Central
(``com.chaquo.python:target``) and is cached in ``~/.cache/pyzed/android``.

The engine for each processor comes from, in this order: a Pyzed source checkout (built with the
NDK), the cache, or the GitHub Release of the installed Pyzed version
(``pyzed-android-engine-<abi>.so``, checked against the release's ``SHA256SUMS``).

What it needs: the Android SDK (``ANDROID_HOME``) with build-tools and a platform, and Java
(``keytool``; ``jarsigner`` for an AAB)::

    sdkmanager "build-tools;36.0.0" "platforms;android-36"

Settings come from ``[tool.pyzed.build.android]`` in ``pyproject.toml``::

    [tool.pyzed.build.android]
    package = "com.acme.notes"   # the application id (default: the build's identifier)
    abis = ["arm64-v8a"]         # phones; add "x86_64" for an emulator on a PC
    format = "apk"               # or "aab", what Google Play takes
    version-code = 7             # default: made from the version (1.2.3 -> 1002003)
    keystore = "release.jks"     # the release key (default: the debug key, for trying the app)
    key-alias = "upload"

The keystore's passwords come from ``PYZED_KEYSTORE_PASSWORD`` and ``PYZED_KEY_PASSWORD`` (the
same as the keystore's when it is not set), so they stay out of the project.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

PYTHON_VERSION = "3.13"
PYTHON_RELEASE = "3.13.16-0"
MAVEN = "https://repo1.maven.org/maven2/com/chaquo/python/target/" + PYTHON_RELEASE
BUNDLETOOL_VERSION = "1.18.1"
BUNDLETOOL = (f"https://github.com/google/bundletool/releases/download/{BUNDLETOOL_VERSION}/"
              f"bundletool-all-{BUNDLETOOL_VERSION}.jar")
RELEASES = "https://github.com/albakore/pyzed/releases/download"
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "pyzed" / "android"
#: Android ABI -> Rust target.
ABIS = {"arm64-v8a": "aarch64-linux-android", "x86_64": "x86_64-linux-android"}
#: ``pyzed build`` targets -> Android ABI.
TARGET_ABIS = {"android-arm64": "arm64-v8a", "android-x64": "x86_64"}
FORMATS = ("apk", "aab")
MIN_SDK = 26
#: What Google Play asks of new apps and updates.
TARGET_SDK = 36
#: The Pyzed source tree, when this module runs from a checkout (it can build the engine there).
SOURCE = Path(__file__).resolve().parents[2]
#: Parts of Pyzed an app on a phone never imports (the editor, its agents and tools).
SKIP = ("agents", "mcp", "__pycache__")
#: Folders of the ``pyzed`` package itself that only the editor and the command line read.
TOP_SKIP = ("_reference", "templates", "cli.py", "build.py", "android.py")
#: Modules of the editor a form never imports (see ``pyzed.build.EDITOR_ONLY``).
EDITOR_FILES = ("cli.py", "build.py", "android.py", "app.py", "agent_panel.py", "agent_tools.py", "lsp.py",
                "intellisense.py", "export_panel.py", "updates.py", "welcome.py", "project_panel.py",
                "project_picker.py", "keymap_editor.py")
#: What a project's ``.venv`` has that an app on a phone does not need.
VENV_SKIP = ("pyzed", "pip", "setuptools", "wheel", "_distutils_hack", "distutils-precedence.pth", "_virtualenv.py",
             "_virtualenv.pth", "__pycache__")

MANIFEST = """\
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="{package}" android:versionCode="{code}" android:versionName="{version}">
    <uses-sdk android:minSdkVersion="{min_sdk}" android:targetSdkVersion="{target_sdk}" />
    <uses-permission android:name="android.permission.INTERNET" />
    <application android:label="{name}" android:hasCode="false" android:extractNativeLibs="true"
        {icon}android:theme="@android:style/Theme.NoTitleBar"
        android:enableOnBackInvokedCallback="false">
        <activity android:name="android.app.NativeActivity" android:exported="true"
            android:configChanges="orientation|screenSize|screenLayout|smallestScreenSize|keyboardHidden|keyboard|uiMode|density"
            android:windowSoftInputMode="adjustResize">
            <meta-data android:name="android.app.lib_name" android:value="_core" />
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
"""

#: ``main.py`` of a project's app: opens its main form, or runs its script.
PROJECT_MAIN = '''"""Generated by `pyzed build`: starts {name} on Android."""

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "project"
sys.path[:0] = [str(ROOT / p) for p in {paths!r}]
{start}
'''


class AndroidError(Exception):
    """Something the build needs is missing or failed; the message says what to do."""


@dataclass
class Signing:
    """The key an app is signed with: the debug key (the default) or a release key."""

    keystore: Path
    alias: str
    store_password: str
    key_password: str

    @property
    def debug(self) -> bool:
        return self.keystore == debug_keystore_path()

    @classmethod
    def release(cls, keystore: Path, alias: str) -> "Signing":
        """A release key; the passwords come from ``PYZED_KEYSTORE_PASSWORD`` and ``PYZED_KEY_PASSWORD``."""
        if not keystore.is_file():
            raise AndroidError(f"The keystore {keystore} does not exist (make one with keytool -genkeypair)")
        password = os.environ.get("PYZED_KEYSTORE_PASSWORD")
        if not password:
            raise AndroidError("Set PYZED_KEYSTORE_PASSWORD to the keystore's password to sign a release")
        return cls(keystore, alias, password, os.environ.get("PYZED_KEY_PASSWORD") or password)


@dataclass
class AndroidOptions:
    """``[tool.pyzed.build.android]``."""

    package: Optional[str] = None
    abis: List[str] = field(default_factory=lambda: ["arm64-v8a"])
    format: str = "apk"
    version_code: Optional[int] = None
    keystore: Optional[str] = None
    key_alias: str = "upload"
    min_sdk: int = MIN_SDK

    @classmethod
    def from_table(cls, table: Dict) -> "AndroidOptions":
        abis = [a for a in table.get("abis", []) if a in ABIS] or ["arm64-v8a"]
        fmt = str(table.get("format", "apk")).lower()
        code = table.get("version-code")
        return cls(package=table.get("package"), abis=abis, format=fmt if fmt in FORMATS else "apk",
                   version_code=int(code) if code else None, keystore=table.get("keystore"),
                   key_alias=str(table.get("key-alias", "upload")), min_sdk=int(table.get("min-sdk", MIN_SDK)))

    def to_table(self) -> Dict:
        table: Dict = {}
        if self.package:
            table["package"] = self.package
        if self.abis != ["arm64-v8a"]:
            table["abis"] = list(self.abis)
        if self.format != "apk":
            table["format"] = self.format
        if self.version_code:
            table["version-code"] = self.version_code
        if self.keystore:
            table["keystore"] = self.keystore
            table["key-alias"] = self.key_alias
        if self.min_sdk != MIN_SDK:
            table["min-sdk"] = self.min_sdk
        return table


# -- the Android SDK and the tools ----------------------------------------------------------

def find_sdk() -> Optional[Path]:
    """The Android SDK: ``ANDROID_HOME``, ``ANDROID_SDK_ROOT`` or where Android Studio puts it."""
    home = Path.home()
    candidates = [os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"),
                  os.environ.get("LOCALAPPDATA") and Path(os.environ["LOCALAPPDATA"]) / "Android" / "Sdk",
                  home / "Android" / "Sdk", home / "Library" / "Android" / "sdk"]
    for candidate in candidates:
        if candidate and (Path(candidate) / "build-tools").is_dir():
            return Path(candidate)
    return None


def sdk_or_fail() -> Path:
    sdk = find_sdk()
    if sdk is None:
        raise AndroidError('No Android SDK found: install it (Android Studio, or the command line tools and '
                           'sdkmanager "build-tools;36.0.0" "platforms;android-36") and set ANDROID_HOME')
    return sdk


def build_tools(sdk: Path) -> Path:
    versions = sorted((p for p in (sdk / "build-tools").iterdir() if (p / "zipalign").exists()
                       or (p / "zipalign.exe").exists()),
                      key=lambda p: [int(n) for n in re.findall(r"\d+", p.name)])
    if not versions:
        raise AndroidError('No build-tools in the Android SDK: sdkmanager "build-tools;36.0.0"')
    return versions[-1]


def _tool(tools: Path, name: str) -> str:
    for candidate in (name, name + ".exe", name + ".bat"):
        if (tools / candidate).exists():
            return str(tools / candidate)
    return str(tools / name)


def platform_jar(sdk: Path) -> Path:
    jars = sorted(sdk.glob("platforms/android-*/android.jar"),
                  key=lambda p: [int(n) for n in re.findall(r"\d+", p.parent.name)])
    if not jars:
        raise AndroidError(f'No platform in the Android SDK: sdkmanager "platforms;android-{TARGET_SDK}"')
    return jars[-1]


def java_tool(name: str) -> str:
    """``keytool`` or ``jarsigner``: from ``JAVA_HOME``, the ``PATH`` or Android Studio's own Java."""
    places = [os.environ.get("JAVA_HOME"), "/Applications/Android Studio.app/Contents/jbr/Contents/Home",
              os.environ.get("ProgramFiles") and str(Path(os.environ["ProgramFiles"]) / "Android" / "Android Studio" / "jbr")]
    for place in places:
        if place:
            for exe in (name, name + ".exe"):
                if (Path(place) / "bin" / exe).exists():
                    return str(Path(place) / "bin" / exe)
    found = shutil.which(name)
    if not found:
        raise AndroidError(f"{name} not found: install a JDK (17 or newer) or set JAVA_HOME")
    return found


def _run(args: Sequence[str], **kwargs) -> None:
    done = subprocess.run([str(a) for a in args], capture_output=True, text=True, **kwargs)
    if done.returncode != 0:
        raise AndroidError(f"{Path(str(args[0])).name} failed:\n{(done.stdout + done.stderr).strip()}")


def _download(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            return response.read()
    except OSError as err:
        raise AndroidError(f"Could not download {url}: {err}") from err


# -- Python for Android -----------------------------------------------------------------------

def python_for(abi: str, report: Callable[[str], None] = print) -> Path:
    """Python for Android for one ABI, downloaded once: ``<abi>/jniLibs/``, ``<abi>/lib-dynload/``, ``stdlib-pyc/``."""
    folder = CACHE / PYTHON_RELEASE
    for part in (abi, "stdlib-pyc"):
        if (folder / part).is_dir():
            continue
        name = f"target-{PYTHON_RELEASE}-{part}.zip"
        report(f"Downloading {name}")
        data = _download(f"{MAVEN}/{name}")
        expected = _download(f"{MAVEN}/{name}.sha1").decode().split()[0]
        if hashlib.sha1(data).hexdigest() != expected:
            raise AndroidError(f"{name}: the download does not match its checksum")
        CACHE.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=CACHE) as tmp:
            archive = Path(tmp) / name
            archive.write_bytes(data)
            zipfile.ZipFile(archive).extractall(Path(tmp) / part)
            folder.mkdir(parents=True, exist_ok=True)
            shutil.move(str(Path(tmp) / part), folder / part)
    return folder


# -- the engine -------------------------------------------------------------------------------

def pyzed_version() -> str:
    """The installed Pyzed's version (the checkout's ``Cargo.toml`` when running from one)."""
    cargo = SOURCE / "Cargo.toml"
    if cargo.is_file():
        found = re.search(r'^version = "([^"]+)"', cargo.read_text(encoding="utf-8"), re.M)
        if found:
            return found.group(1)
    from importlib.metadata import version

    return version("pyzed-ui")


def is_checkout() -> bool:
    return (SOURCE / "Cargo.toml").is_file() and (SOURCE / "src" / "android.rs").is_file()


def engine(abi: str, *, rebuild: bool = False, sdk: Optional[Path] = None,
           report: Callable[[str], None] = print) -> Path:
    """``lib_core.so`` for ``abi``: built from the checkout, cached, or downloaded from Pyzed's release."""
    if is_checkout():
        built = SOURCE / "target" / ABIS[abi] / "release" / "lib_core.so"
        if rebuild or not built.exists():
            build_engine(sdk or sdk_or_fail(), abi, report=report)
        return built
    version = pyzed_version()
    cached = CACHE / "engine" / version / abi / "lib_core.so"
    if cached.exists() and not rebuild:
        return cached
    name = f"pyzed-android-engine-{abi}.so"
    report(f"Downloading {name} (Pyzed {version})")
    data = _download(f"{RELEASES}/v{version}/{name}")
    sums = _download(f"{RELEASES}/v{version}/SHA256SUMS").decode()
    expected = next((line.split()[0] for line in sums.splitlines() if line.strip().endswith(name)), None)
    if expected != hashlib.sha256(data).hexdigest():
        raise AndroidError(f"{name}: the download does not match the release's SHA256SUMS")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(data)
    return cached


def ndk(sdk: Path) -> Path:
    """The ``bin`` folder of the newest NDK's LLVM toolchain."""
    found = sorted(sdk.glob("ndk/*/toolchains/llvm/prebuilt/*/bin"),
                   key=lambda p: [int(n) for n in re.findall(r"\d+", p.parents[4].name)])
    if not found:
        raise AndroidError('No NDK in the Android SDK: sdkmanager "ndk;29.0.14206865"')
    return found[-1]


def build_engine(sdk: Path, abi: str, *, report: Callable[[str], None] = print) -> Path:
    """Builds Pyzed's core for one ABI with the NDK, linked against Python for Android (needs a checkout)."""
    bin, triple = ndk(sdk), ABIS[abi]
    clang = str(bin / f"{triple}{MIN_SDK}-clang")
    if os.name == "nt":
        clang += ".cmd"
    key = triple.replace("-", "_")
    jni = python_for(abi, report) / abi / "jniLibs" / abi
    env = dict(os.environ, **{
        f"CARGO_TARGET_{key.upper()}_LINKER": clang, f"CC_{key}": clang, f"CXX_{key}": clang.replace("clang", "clang++"),
        f"AR_{key}": str(bin / "llvm-ar"), "PYO3_CROSS_PYTHON_VERSION": PYTHON_VERSION,
        # The core is an extension module everywhere else; here it embeds Python, so it links it.
        "RUSTFLAGS": f"-L {jni} -C link-arg=-lpython{PYTHON_VERSION}",
    })
    report(f"Building the engine for {abi}")
    _run(["rustup", "target", "add", triple])
    done = subprocess.run(["cargo", "build", "--release", "--target", triple], cwd=SOURCE, env=env)
    if done.returncode != 0:
        raise AndroidError(f"cargo build --target {triple} failed")
    return SOURCE / "target" / triple / "release" / "lib_core.so"


# -- the bundle ---------------------------------------------------------------------------------

def _add_tree(z: zipfile.ZipFile, folder: Path, prefix: str, skip: Callable[[Path], bool] = lambda p: False) -> None:
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder)
        if any(skip(folder / part) for part in [*reversed(rel.parents)][1:]) or skip(path):
            continue
        if path.is_file():
            z.write(path, f"{prefix}/{rel.as_posix()}")


def _pyzed_skip(forms: bool) -> Callable[[Path], bool]:
    """What of Pyzed stays out: the editor (all of ``designer`` for a script, its editor parts for forms)."""
    package = Path(__file__).resolve().parent

    def skip(path: Path) -> bool:
        if path.name in SKIP or path.suffix in (".so", ".pyd", ".pyc"):
            return True
        if path.parent == package / "designer":
            return path.name in EDITOR_FILES
        if path.parent == package:
            return (path.name == "designer" and not forms) or path.name in TOP_SKIP
        return False

    return skip


def binary_packages(site: Path) -> List[str]:
    """Top-level packages of ``site`` with compiled modules, which a phone cannot load."""
    found = set()
    for path in site.rglob("*"):
        if path.suffix in (".so", ".pyd", ".dylib") and "__pycache__" not in path.parts:
            found.add(path.relative_to(site).parts[0])
    return sorted(found - set(VENV_SKIP))


def bundle(app: Path, abis: Sequence[str], out: Path, *, site_packages: Optional[Path] = None,
           forms: bool = False, report: Callable[[str], None] = print) -> None:
    """``pyzed-bundle.zip``: Python's standard library, Pyzed (without its core), the app and its dependencies.

    ``app`` is a ``.py`` file or a folder with ``main.py``. The compiled modules of every ABI share
    ``lib-dynload``: their names carry the ABI."""
    stdlib = f"python/lib/python{PYTHON_VERSION}"
    package = Path(__file__).resolve().parent
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        _add_tree(z, python_for(abis[0], report) / "stdlib-pyc", stdlib)
        for abi in abis:
            _add_tree(z, python_for(abi, report) / abi / "lib-dynload" / abi, f"{stdlib}/lib-dynload")
        _add_tree(z, package, "site-packages/pyzed", skip=_pyzed_skip(forms))
        if site_packages is not None and site_packages.is_dir():
            _add_tree(z, site_packages, "site-packages",
                      skip=lambda p: p.name in VENV_SKIP or p.suffix in (".pyc", ".so", ".pyd")
                      or p.name.startswith("pyzed_ui-"))
        if app.is_dir():
            _add_tree(z, app, "app", skip=lambda p: p.name in ("__pycache__", ".venv", ".git", "dist", "build"))
        else:
            z.write(app, "app/main.py")


def project_app(project, folder: Path) -> Path:
    """Writes the app folder of a ``pyzed.project.Project``: the project and a ``main.py`` that starts it."""
    if folder.exists():
        shutil.rmtree(folder)
    copy = folder / "project"
    shutil.copytree(project.root, copy, ignore=shutil.ignore_patterns(
        ".venv", ".git", "dist", "build", "__pycache__", "*.pyc", ".pyzed", "*.jks", "*.keystore"))
    paths = [p.relative_to(project.root).as_posix() or "." for p in project.paths()]
    if project.script is not None:
        script = project.script.relative_to(project.root).as_posix()
        start = f"if __name__ == '__main__':\n    runpy.run_path(str(ROOT / {script!r}), run_name='__main__')"
    else:
        main = project.main_form.relative_to(project.root).as_posix()
        start = (f"from pyzed import designer  # noqa: E402\n\nif __name__ == '__main__':\n"
                 f"    designer.run(ROOT / {main!r})")
    text = PROJECT_MAIN.format(name=project.name, paths=paths, start=start)
    (folder / "main.py").write_text(text.replace("import runpy\n", "") if project.script is None else text,
                                    encoding="utf-8")
    return folder


# -- the package --------------------------------------------------------------------------------

def debug_keystore_path() -> Path:
    return Path.home() / ".android" / "debug.keystore"


def debug_signing() -> Signing:
    """The usual Android debug key (``~/.android/debug.keystore``), made when it is missing."""
    store = debug_keystore_path()
    if not store.exists():
        store.parent.mkdir(parents=True, exist_ok=True)
        _run([java_tool("keytool"), "-genkeypair", "-keystore", store, "-storepass", "android", "-alias",
              "androiddebugkey", "-keypass", "android", "-keyalg", "RSA", "-validity", "10000", "-dname",
              "CN=Android Debug,O=Android,C=US"])
    return Signing(store, "androiddebugkey", "android", "android")


def version_code(version: str) -> int:
    """``1.2.3`` -> ``1002003`` (each part up to 999)."""
    parts = [min(int(n), 999) for n in re.findall(r"\d+", version)[:3]]
    parts += [0] * (3 - len(parts))
    return max(1, parts[0] * 1_000_000 + parts[1] * 1000 + parts[2])


def package_name(text: str) -> str:
    """A valid application id from ``text`` (``com.acme.My-App`` -> ``com.acme.myapp``)."""
    parts = [re.sub(r"\W", "", p.lower()) for p in text.split(".")]
    parts = [("a" + p if p[0].isdigit() else p) for p in parts if p]
    if len(parts) < 2:
        parts = ["org", "pyzed", *parts] if parts else ["org", "pyzed", "app"]
    return ".".join(parts)


def package(app: Path, out: Path, *, name: str, package: str, version: str = "1.0.0", code: Optional[int] = None,
            icon: Optional[Path] = None, abis: Sequence[str] = ("arm64-v8a",), fmt: str = "apk",
            signing: Optional[Signing] = None, min_sdk: int = MIN_SDK, site_packages: Optional[Path] = None,
            forms: bool = False, rebuild: bool = False, report: Callable[[str], None] = print) -> Path:
    """Builds the app's APK (or AAB) at ``out`` and returns it.

    Without ``signing`` it is signed with the debug key and marked debuggable (``adb shell run-as`` then
    reads its files); with a release key it is a release build."""
    sdk = sdk_or_fail()
    tools = build_tools(sdk)
    signing = signing or debug_signing()
    cores = {abi: engine(abi, rebuild=rebuild, sdk=sdk, report=report) for abi in abis}
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        link = [_tool(tools, "aapt2"), "link", "-I", platform_jar(sdk), "--manifest", work / "AndroidManifest.xml",
                "-o", work / "base.apk"]
        if signing.debug:
            link.append("--debug-mode")
        if fmt == "aab":
            link.append("--proto-format")
        icon_attr = ""
        if icon is not None:
            res = work / "res" / "mipmap"
            res.mkdir(parents=True)
            shutil.copy(icon, res / "ic_launcher.png")
            (work / "compiled").mkdir()
            _run([_tool(tools, "aapt2"), "compile", res / "ic_launcher.png", "-o", work / "compiled"])
            link += ["-R", *sorted((work / "compiled").glob("*.flat"))]
            icon_attr = 'android:icon="@mipmap/ic_launcher" '
        (work / "AndroidManifest.xml").write_text(MANIFEST.format(
            package=package, code=code or version_code(version), version=version, name=_xml(name), icon=icon_attr,
            min_sdk=min_sdk, target_sdk=TARGET_SDK), encoding="utf-8")
        _run(link)
        report("Packing Python, Pyzed and the app")
        bundle(app, list(abis), work / "pyzed-bundle.zip", site_packages=site_packages, forms=forms, report=report)
        libs = {}
        for abi in abis:
            libs[f"lib/{abi}/lib_core.so"] = cores[abi]
            for lib in sorted((python_for(abi, report) / abi / "jniLibs" / abi).glob("*.so")):
                libs[f"lib/{abi}/{lib.name}"] = lib
        if fmt == "aab":
            _aab(work, out, libs, signing)
        else:
            _apk(work, tools, out, libs, signing)
    return out


def _xml(text: str) -> str:
    return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def _apk(work: Path, tools: Path, out: Path, libs: Dict[str, Path], signing: Signing) -> None:
    unsigned = work / "unsigned.apk"
    shutil.copy(work / "base.apk", unsigned)
    with zipfile.ZipFile(unsigned, "a") as z:
        z.write(work / "pyzed-bundle.zip", "assets/pyzed-bundle.zip", zipfile.ZIP_STORED)
        for name, lib in libs.items():
            z.write(lib, name, zipfile.ZIP_DEFLATED)
    aligned = work / "aligned.apk"
    _run([_tool(tools, "zipalign"), "-f", "-P", "16", "4", unsigned, aligned])
    _run([_tool(tools, "apksigner"), "sign", "--ks", signing.keystore, "--ks-key-alias", signing.alias,
          "--ks-pass", "env:PYZED_KS_PASS", "--key-pass", "env:PYZED_KEY_PASS", "--out", out, aligned],
         env=dict(os.environ, PYZED_KS_PASS=signing.store_password, PYZED_KEY_PASS=signing.key_password))
    out.with_suffix(".apk.idsig").unlink(missing_ok=True)


def bundletool() -> Path:
    """Google's ``bundletool`` jar, which turns a module into an AAB (downloaded once)."""
    jar = CACHE / f"bundletool-{BUNDLETOOL_VERSION}.jar"
    if not jar.exists():
        jar.parent.mkdir(parents=True, exist_ok=True)
        jar.write_bytes(_download(BUNDLETOOL))
    return jar


def _aab(work: Path, out: Path, libs: Dict[str, Path], signing: Signing) -> None:
    """An Android App Bundle: the module ``base`` (laid out as bundletool wants it), signed with jarsigner."""
    module = work / "base.zip"
    with zipfile.ZipFile(work / "base.apk") as linked, zipfile.ZipFile(module, "w", zipfile.ZIP_DEFLATED) as z:
        for item in linked.infolist():
            data = linked.read(item)
            if item.filename == "AndroidManifest.xml":
                z.writestr("manifest/AndroidManifest.xml", data)
            elif item.filename == "resources.pb" or item.filename.startswith("res/"):
                z.writestr(item.filename, data)
            else:
                z.writestr(f"root/{item.filename}", data)
        z.write(work / "pyzed-bundle.zip", "assets/pyzed-bundle.zip", zipfile.ZIP_STORED)
        for name, lib in libs.items():
            z.write(lib, name)
    java = shutil.which("java") or java_tool("java")
    if out.exists():
        out.unlink()
    _run([java, "-jar", bundletool(), "build-bundle", f"--modules={module}", f"--output={out}"])
    _run([java_tool("jarsigner"), "-keystore", signing.keystore, "-storepass:env", "PYZED_KS_PASS", "-keypass:env",
          "PYZED_KEY_PASS", "-sigalg", "SHA256withRSA", "-digestalg", "SHA-256", out, signing.alias],
         env=dict(os.environ, PYZED_KS_PASS=signing.store_password, PYZED_KEY_PASS=signing.key_password))


# -- command line (android/build_apk.py in the checkout) --------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Builds an Android APK (or AAB) of a Pyzed app.")
    parser.add_argument("app", type=Path, nargs="?", help="the app: a main.py, or a folder with main.py in it")
    parser.add_argument("--name", help="the name under the icon (default: the app's file name)")
    parser.add_argument("--package", help="the Android package (default: org.pyzed.<name>)")
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--icon", type=Path, help="a square PNG for the launcher")
    parser.add_argument("--abi", choices=sorted(ABIS), action="append",
                        help="the processors to build for (default: arm64-v8a, the one of phones; "
                             "x86_64 is for emulators on a PC)")
    parser.add_argument("--aab", action="store_true", help="an Android App Bundle for Google Play")
    parser.add_argument("--keystore", type=Path, help="sign with this release key (passwords: PYZED_KEYSTORE_PASSWORD"
                                                      " and PYZED_KEY_PASSWORD)")
    parser.add_argument("--key-alias", default="upload")
    parser.add_argument("--rebuild", action="store_true", help="build the engine even when it is there")
    parser.add_argument("--engine-only", action="store_true", help="only build the engine (lib_core.so)")
    parser.add_argument("-o", "--output", type=Path, help="the result (default: dist/<name>.apk)")
    args = parser.parse_args(argv)
    abis = list(dict.fromkeys(args.abi or ["arm64-v8a"]))
    try:
        if args.engine_only:
            for abi in abis:
                print(engine(abi, rebuild=args.rebuild))
            return 0
        app = (args.app or Path.cwd()).resolve()
        if not (app / "main.py" if app.is_dir() else app).is_file():
            raise AndroidError(f"{args.app or '.'}: no app there (a .py file, or a folder with main.py)")
        stem = app.name if app.is_dir() else app.stem
        fmt = "aab" if args.aab else "apk"
        out = (args.output or Path.cwd() / "dist" / f"{stem}.{fmt}").resolve()
        signing = Signing.release(args.keystore.resolve(), args.key_alias) if args.keystore else None
        package(app, out, name=args.name or stem.replace("_", " ").title(),
                package=args.package or package_name(f"org.pyzed.{stem}"), version=args.version, icon=args.icon,
                abis=abis, fmt=fmt, signing=signing, rebuild=args.rebuild)
    except AndroidError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    print(f"{out} ({out.stat().st_size / 1e6:.1f} MB, {', '.join(abis)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
