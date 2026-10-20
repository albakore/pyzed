"""Builds Pyzed Design as a standalone app for this platform (with PyInstaller).

The app bundles Python, pyzed-ui, the ``uv`` binary and the example projects of the welcome
window (with their thumbnails), so it can create and manage projects (``uv init``, ``uv add``...)
on machines with nothing else installed. Each
project keeps its own environment in ``.venv``; forms run there through ``uv run``.

    python -m pip install pyzed-ui pyinstaller uv
    python scripts/build_designer.py            # -> dist/Pyzed Design[.app|.exe] and a .zip

Run it on each OS (the release workflow does it on Linux, Windows and macOS).

Signing is optional and driven by environment variables, so builds without certificates still work:

- macOS: ``PYZED_CODESIGN_IDENTITY`` (a "Developer ID Application" identity in the keychain) signs the
  app with the hardened runtime; with ``APPLE_ID``, ``APPLE_TEAM_ID`` and ``APPLE_APP_PASSWORD`` it is
  also notarized and the ticket stapled.
- Windows: ``PYZED_SIGN_PFX`` (a .pfx file) and ``PYZED_SIGN_PASSWORD`` sign the executables with
  Authenticode and a timestamp.

The OAuth apps the Agent panel signs in with are optional too: ``PYZED_GITHUB_CLIENT_ID``,
``PYZED_GOOGLE_CLIENT_ID`` and ``PYZED_GOOGLE_CLIENT_SECRET`` are bundled as the ``pyzed_oauth_apps``
module, so they stay out of the repository and of the PyPI wheels.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

NAME = "Pyzed Design"
ROOT = Path(__file__).resolve().parent.parent

ENTRY = '''"""Pyzed Design: the visual designer and project manager of Pyzed."""

import sys

from pyzed.designer import design

if __name__ == "__main__":
    design(sys.argv[1] if len(sys.argv) > 1 else None)
'''


def uv_binary() -> str:
    try:
        from uv import find_uv_bin  # type: ignore[import-not-found]

        return find_uv_bin()
    except ImportError:
        found = shutil.which("uv")
        if not found:
            sys.exit("error: install uv first (python -m pip install uv)")
        return found


def signtool() -> str:
    found = shutil.which("signtool")
    if found:
        return found
    kits = sorted(Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")).glob(
        "Windows Kits/10/bin/*/x64/signtool.exe"))
    if not kits:
        sys.exit("error: signtool.exe not found (install the Windows SDK)")
    return str(kits[-1])


def sign(bundle: Path) -> None:
    """Signs the app when the environment carries the certificates (see the module docstring)."""
    if sys.platform == "darwin" and os.environ.get("PYZED_CODESIGN_IDENTITY"):
        subprocess.run(["codesign", "--force", "--deep", "--options", "runtime", "--timestamp",
                        "--sign", os.environ["PYZED_CODESIGN_IDENTITY"], str(bundle)], check=True)
        print(f"Signed {bundle.name}")
    elif sys.platform == "win32" and os.environ.get("PYZED_SIGN_PFX"):
        exes = sorted(str(p) for p in bundle.rglob("*.exe"))
        subprocess.run([signtool(), "sign", "/f", os.environ["PYZED_SIGN_PFX"],
                        "/p", os.environ.get("PYZED_SIGN_PASSWORD", ""), "/fd", "sha256",
                        "/tr", "http://timestamp.digicert.com", "/td", "sha256", *exes], check=True)
        print(f"Signed {len(exes)} executables")


def notarize(bundle: Path, archive: str) -> bool:
    """Sends the zipped app to Apple's notary service and staples the ticket; ``False`` when not set up."""
    names = ("APPLE_ID", "APPLE_TEAM_ID", "APPLE_APP_PASSWORD")
    if sys.platform != "darwin" or not os.environ.get("PYZED_CODESIGN_IDENTITY") \
            or not all(os.environ.get(n) for n in names):
        return False
    subprocess.run(["xcrun", "notarytool", "submit", archive, "--wait",
                    "--apple-id", os.environ["APPLE_ID"], "--team-id", os.environ["APPLE_TEAM_ID"],
                    "--password", os.environ["APPLE_APP_PASSWORD"]], check=True)
    subprocess.run(["xcrun", "stapler", "staple", str(bundle)], check=True)
    return True


def oauth_apps(work: Path) -> "Path | None":
    """Writes the OAuth apps given in the environment as a module for the bundle (``None`` when none is)."""
    names = ("GITHUB_CLIENT_ID", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET")
    values = {name: os.environ.get(f"PYZED_{name}", "").strip() for name in names}
    path = work / "oauth" / "pyzed_oauth_apps.py"
    shutil.rmtree(path.parent, ignore_errors=True)
    if not any(values.values()):
        return None
    path.parent.mkdir(parents=True)
    path.write_text("".join(f"{name} = {value!r}\n" for name, value in values.items()), encoding="utf-8")
    print(f"Bundling the OAuth apps: {', '.join(n for n, v in values.items() if v)}")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "dist"), help="output folder")
    parser.add_argument("--no-zip", action="store_true", help="do not zip the result")
    args = parser.parse_args()
    out = Path(args.out).resolve()
    work = ROOT / "build" / "designer"
    work.mkdir(parents=True, exist_ok=True)
    entry = work / "pyzed_design.py"
    entry.write_text(ENTRY, encoding="utf-8")
    icon = ROOT / "assets" / ("icon.icns" if sys.platform == "darwin" else "icon.ico")
    command = [
        sys.executable, "-m", "PyInstaller", str(entry), "--name", NAME, "--noconfirm", "--clean", "--windowed",
        "--distpath", str(out), "--workpath", str(work), "--specpath", str(work),
        "--collect-all", "pyzed",
        # uv goes next to the executable, where pyzed.project.find_uv() looks for it
        "--add-binary", f"{uv_binary()}{os.pathsep}.",
    ]
    # the example projects of the welcome window, read from sys._MEIPASS/examples
    from pyzed.designer import samples

    staged = work / "examples"
    shutil.rmtree(staged, ignore_errors=True)
    samples.stage(staged, ROOT / "examples")
    size = sum(f.stat().st_size for f in staged.rglob("*") if f.is_file())
    print(f"Bundling {len(samples.CATALOG)} examples ({size / 1e6:.1f} MB)")
    command += ["--add-data", f"{staged}{os.pathsep}examples"]
    apps = oauth_apps(work)
    if apps:
        command += ["--paths", str(apps.parent), "--hidden-import", apps.stem]
    # the Agent panel's optional dependencies (Claude's SDK and the system keychain), when installed
    for package in ("anthropic", "keyring"):
        if importlib.util.find_spec(package):
            command += ["--collect-all", package]
    if icon.exists():
        command += ["--icon", str(icon)]
    if sys.platform == "darwin":
        command += ["--osx-bundle-identifier", "dev.pyzed.design"]
    print(" ".join(command))
    subprocess.run(command, check=True)
    bundle = out / (f"{NAME}.app" if sys.platform == "darwin" else NAME)
    sign(bundle)
    if not args.no_zip:
        from pyzed import updater

        # the same name the designer's updater looks for in each release
        archive = str(out / updater.asset_name("pyzed-design"))
        if sys.platform == "darwin":
            # ditto keeps the bundle's symlinks and signature, which the updater unpacks with ditto too
            zip_app = ["ditto", "-c", "-k", "--keepParent", str(bundle), archive]
            subprocess.run(zip_app, check=True)
            if notarize(bundle, archive):
                # zip again so the download carries the stapled ticket
                os.remove(archive)
                subprocess.run(zip_app, check=True)
        else:
            archive = shutil.make_archive(archive[:-4], "zip", bundle.parent, bundle.name)
        print(f"Wrote {archive}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
