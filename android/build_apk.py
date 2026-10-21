"""Builds an Android APK of a Pyzed app (a prototype; see README.md next to this file).

    python android/build_apk.py examples/counter.py --name Counter

Needs the Android SDK (``ANDROID_HOME``, with the NDK, build-tools and a platform) and Rust. The
engine is built for Android when it is missing (``--rebuild`` builds it again). Python for Android comes from Maven
Central and is cached in ``~/.cache/pyzed/android``. The APK is signed with a debug key, so it
installs on a phone with ``adb install`` but is not for the Play Store.
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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON_VERSION = "3.13"
PYTHON_RELEASE = "3.13.16-0"
MAVEN = "https://repo1.maven.org/maven2/com/chaquo/python/target/" + PYTHON_RELEASE
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "pyzed" / "android"
#: Android ABI -> Rust target.
ABIS = {"arm64-v8a": "aarch64-linux-android", "x86_64": "x86_64-linux-android"}
MIN_SDK = 26
TARGET_SDK = 35
#: Parts of Pyzed an app on a phone never imports (the editor, its agents and tools).
SKIP = ("designer", "agents", "mcp", "_reference", "templates", "__pycache__")

MANIFEST = """\
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="{package}" android:versionCode="{code}" android:versionName="{version}">
    <uses-sdk android:minSdkVersion="{min_sdk}" android:targetSdkVersion="{target_sdk}" />
    <uses-permission android:name="android.permission.INTERNET" />
    <application android:label="{name}" android:hasCode="false" android:extractNativeLibs="true"
        {icon}android:theme="@android:style/Theme.NoTitleBar">
        <activity android:name="android.app.NativeActivity" android:exported="true"
            android:configChanges="orientation|screenSize|screenLayout|keyboardHidden|keyboard|uiMode|density"
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


def python_for(abi: str) -> Path:
    """Python for Android for one ABI, downloaded once: ``jniLibs/``, ``lib-dynload/``, ``stdlib-pyc/``."""
    folder = CACHE / PYTHON_RELEASE
    for part in (abi, "stdlib-pyc"):
        if (folder / part).is_dir():
            continue
        name = f"target-{PYTHON_RELEASE}-{part}.zip"
        print(f"Downloading {name}")
        with urllib.request.urlopen(f"{MAVEN}/{name}") as response:
            data = response.read()
        with urllib.request.urlopen(f"{MAVEN}/{name}.sha1") as response:
            expected = response.read().decode().split()[0]
        if hashlib.sha1(data).hexdigest() != expected:
            sys.exit(f"{name}: the download does not match its checksum")
        with tempfile.TemporaryDirectory(dir=CACHE.parent if CACHE.parent.exists() else None) as tmp:
            zipfile.ZipFile(_bytes_file(Path(tmp) / name, data)).extractall(Path(tmp) / part)
            folder.mkdir(parents=True, exist_ok=True)
            shutil.move(str(Path(tmp) / part), folder / part)
    return folder


def _bytes_file(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def bundle(app: Path, abis: list, out: Path) -> None:
    """``pyzed-bundle.zip``: Python's standard library, Pyzed (without its core) and the app.

    The compiled modules of every ABI share ``lib-dynload``: their names carry the ABI."""
    stdlib = f"python/lib/python{PYTHON_VERSION}"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        _add_tree(z, python_for(abis[0]) / "stdlib-pyc", stdlib)
        for abi in abis:
            _add_tree(z, python_for(abi) / abi / "lib-dynload" / abi, f"{stdlib}/lib-dynload")
        _add_tree(z, ROOT / "python" / "pyzed", "site-packages/pyzed",
                  skip=lambda p: p.name in SKIP or p.suffix in (".so", ".pyd", ".pyc"))
        if app.is_dir():
            _add_tree(z, app, "app", skip=lambda p: p.name in ("__pycache__", ".venv", ".git", "dist"))
        else:
            z.write(app, "app/main.py")


def _add_tree(z: zipfile.ZipFile, folder: Path, prefix: str, skip=lambda p: False) -> None:
    for path in sorted(folder.rglob("*")):
        if any(skip(part) for part in [path, *path.relative_to(folder).parents][:-1]) or skip(path):
            continue
        if path.is_file():
            z.write(path, f"{prefix}/{path.relative_to(folder).as_posix()}")


def build_engine(sdk: Path, abi: str) -> Path:
    """Builds Pyzed's core for one ABI with the NDK, linked against Python for Android."""
    ndks = sorted((sdk / "ndk").glob("*/toolchains/llvm/prebuilt/*/bin"))
    if not ndks:
        sys.exit("No NDK in the Android SDK: sdkmanager 'ndk;29.0.14206865'")
    bin, triple = ndks[-1], ABIS[abi]
    clang = str(bin / f"{triple}{MIN_SDK}-clang")
    key = triple.replace("-", "_")
    jni = python_for(abi) / abi / "jniLibs" / abi
    env = dict(os.environ, **{
        f"CARGO_TARGET_{key.upper()}_LINKER": clang, f"CC_{key}": clang, f"CXX_{key}": clang + "++",
        f"AR_{key}": str(bin / "llvm-ar"), "PYO3_CROSS_PYTHON_VERSION": PYTHON_VERSION,
        # The core is an extension module everywhere else; here it embeds Python, so it links it.
        "RUSTFLAGS": f"-L {jni} -C link-arg=-lpython{PYTHON_VERSION}",
    })
    subprocess.run(["rustup", "target", "add", triple], check=True, capture_output=True)
    subprocess.run(["cargo", "build", "--release", "--target", triple], cwd=ROOT, env=env, check=True)
    return ROOT / "target" / triple / "release" / "lib_core.so"


def build_tools(sdk: Path) -> Path:
    versions = sorted((sdk / "build-tools").iterdir(), key=lambda p: [int(n) for n in re.findall(r"\d+", p.name)])
    if not versions:
        sys.exit("No build-tools in the Android SDK: sdkmanager 'build-tools;36.0.0'")
    return versions[-1]


def platform_jar(sdk: Path) -> Path:
    jars = sorted((sdk / "platforms").glob("android-*/android.jar"))
    if not jars:
        sys.exit(f"No platform in the Android SDK: sdkmanager 'platforms;android-{TARGET_SDK}'")
    return jars[-1]


def debug_keystore() -> Path:
    """The usual Android debug key (``~/.android/debug.keystore``), made when it is missing."""
    store = Path.home() / ".android" / "debug.keystore"
    if not store.exists():
        store.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["keytool", "-genkeypair", "-keystore", str(store), "-storepass", "android",
                        "-alias", "androiddebugkey", "-keypass", "android", "-keyalg", "RSA",
                        "-validity", "10000", "-dname", "CN=Android Debug,O=Android,C=US"],
                       check=True, capture_output=True)
    return store


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("app", type=Path, help="the app: a main.py, or a folder with main.py in it")
    parser.add_argument("--name", help="the name under the icon (default: the app's file name)")
    parser.add_argument("--package", help="the Android package (default: org.pyzed.<name>)")
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--icon", type=Path, help="a square PNG for the launcher")
    parser.add_argument("--abi", choices=sorted(ABIS), action="append",
                        help="the processors to build for (default: arm64-v8a, the one of phones; "
                             "x86_64 is for emulators on a PC)")
    parser.add_argument("--rebuild", action="store_true", help="build the engine even when it is there")
    parser.add_argument("-o", "--output", type=Path, help="the APK (default: dist/<name>.apk)")
    args = parser.parse_args(argv)

    app = args.app.resolve()
    if not (app / "main.py" if app.is_dir() else app).is_file():
        sys.exit(f"{args.app}: no app there (a .py file, or a folder with main.py)")
    stem = app.name if app.is_dir() else app.stem
    name = args.name or stem.replace("_", " ").title()
    package = args.package or "org.pyzed." + (re.sub(r"\W", "", stem.lower()) or "app")
    sdk = Path(os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or "")
    if not (sdk / "build-tools").is_dir():
        sys.exit("Set ANDROID_HOME to the Android SDK")
    abis = list(dict.fromkeys(args.abi or ["arm64-v8a"]))
    cores = {}
    for abi in abis:
        core = ROOT / "target" / ABIS[abi] / "release" / "lib_core.so"
        cores[abi] = build_engine(sdk, abi) if args.rebuild or not core.exists() else core
    tools = build_tools(sdk)
    out = (args.output or ROOT / "dist" / f"{stem}.apk").resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        icon = ""
        # A debug build, so `adb shell run-as` can read the app's files (last-error.txt).
        link = [str(tools / "aapt2"), "link", "--debug-mode", "-I", str(platform_jar(sdk)), "--manifest",
                str(work / "AndroidManifest.xml"), "-o", str(work / "base.apk")]
        if args.icon:
            res = work / "res" / "mipmap"
            res.mkdir(parents=True)
            shutil.copy(args.icon, res / "ic_launcher.png")
            (work / "compiled").mkdir()
            subprocess.run([str(tools / "aapt2"), "compile", str(res / "ic_launcher.png"), "-o",
                            str(work / "compiled")], check=True)
            link += ["-R", *map(str, (work / "compiled").glob("*.flat"))]
            icon = 'android:icon="@mipmap/ic_launcher" '
        code = sum(n * 1000 ** i for i, n in enumerate(reversed([int(x) for x in re.findall(r"\d+", args.version)[:3]])))
        (work / "AndroidManifest.xml").write_text(MANIFEST.format(
            package=package, code=max(code, 1), version=args.version, name=name, icon=icon,
            min_sdk=MIN_SDK, target_sdk=TARGET_SDK))
        subprocess.run(link, check=True)

        bundle(app, abis, work / "pyzed-bundle.zip")
        unsigned = work / "unsigned.apk"
        shutil.copy(work / "base.apk", unsigned)
        with zipfile.ZipFile(unsigned, "a") as z:
            z.write(work / "pyzed-bundle.zip", "assets/pyzed-bundle.zip", zipfile.ZIP_STORED)
            for abi in abis:
                jni = python_for(abi) / abi / "jniLibs" / abi
                z.write(cores[abi], f"lib/{abi}/lib_core.so", zipfile.ZIP_DEFLATED)
                for lib in sorted(jni.glob("*.so")):
                    z.write(lib, f"lib/{abi}/{lib.name}", zipfile.ZIP_DEFLATED)
        aligned = work / "aligned.apk"
        subprocess.run([str(tools / "zipalign"), "-f", "-P", "16", "4", str(unsigned), str(aligned)], check=True)
        subprocess.run([str(tools / "apksigner"), "sign", "--ks", str(debug_keystore()), "--ks-pass",
                        "pass:android", "--key-pass", "pass:android", "--out", str(out), str(aligned)],
                       check=True)
    out.with_suffix(".apk.idsig").unlink(missing_ok=True)
    print(f"{out} ({out.stat().st_size / 1e6:.1f} MB, {', '.join(abis)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
