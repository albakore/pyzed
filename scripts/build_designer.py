"""Builds Pyzed Design as a standalone app for this platform (with PyInstaller).

The app bundles Python, pyzed-ui, the ``uv`` binary and the example projects of the welcome
window (with their thumbnails), so it can create and manage projects (``uv init``, ``uv add``...)
on machines with nothing else installed. Each
project keeps its own environment in ``.venv``; forms run there through ``uv run``.

    python -m pip install pyzed-ui pyinstaller uv
    python scripts/build_designer.py            # -> dist/Pyzed Design[.app|.exe] and a .zip
    python scripts/build_designer.py --installer   # ...plus the setup .exe (Windows) or the .dmg (macOS)

Run it on each OS (the release workflow does it on Linux, Windows and macOS). The zip is what
the app's updater downloads; the installers are what people download first, like Zed's:

- Windows: ``pyzed-design-windows-x86_64-setup.exe``, made with Inno Setup 6 from
  ``installer/windows/pyzed-design.iss``. It installs for the current user, without admin
  rights, in ``%LOCALAPPDATA%\\Programs\\Pyzed Design``, where the app can update itself.
- macOS: ``pyzed-design-macos-<arch>.dmg`` with the app and a shortcut to Applications.
- Linux: no package to build; ``docs/public/install.sh`` installs the zip into ``~/.local``.

Signing is optional and driven by environment variables, so builds without certificates still work:

- macOS: ``PYZED_CODESIGN_IDENTITY`` (a "Developer ID Application" identity in the keychain) signs the
  app with the hardened runtime; with ``APPLE_ID``, ``APPLE_TEAM_ID`` and ``APPLE_APP_PASSWORD`` it is
  also notarized and the ticket stapled.
- Windows: ``PYZED_SIGN_PFX`` (a .pfx file) and ``PYZED_SIGN_PASSWORD`` sign the executables with
  Authenticode and a timestamp. Or, like Zed's Windows builds, Azure Artifact Signing (formerly Trusted
  Signing): ``PYZED_AZURE_SIGNING_DLIB`` (its ``Azure.CodeSigning.Dlib.dll``), ``PYZED_AZURE_SIGNING_ENDPOINT``,
  ``PYZED_AZURE_SIGNING_ACCOUNT`` and ``PYZED_AZURE_SIGNING_PROFILE``, with the app registration that may sign
  in ``AZURE_TENANT_ID``, ``AZURE_CLIENT_ID`` and ``AZURE_CLIENT_SECRET``. A signed app is trusted by Windows'
  SmartScreen and antivirus, which otherwise hold up the first start of each new version while they check it.

The OAuth apps the Agent panel signs in with are optional too: ``PYZED_GITHUB_CLIENT_ID``,
``PYZED_GOOGLE_CLIENT_ID`` and ``PYZED_GOOGLE_CLIENT_SECRET`` are bundled as the ``pyzed_oauth_apps``
module, so they stay out of the repository and of the PyPI wheels.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
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


def windows_identity() -> "list[str] | None":
    """signtool's arguments for the certificate the environment carries (a .pfx or Azure Artifact Signing, see
    the module docstring), or ``None`` to leave the app unsigned."""
    if os.environ.get("PYZED_SIGN_PFX"):
        return ["/f", os.environ["PYZED_SIGN_PFX"], "/p", os.environ.get("PYZED_SIGN_PASSWORD", ""),
                "/tr", "http://timestamp.digicert.com"]
    dlib = os.environ.get("PYZED_AZURE_SIGNING_DLIB")
    if not dlib:
        return None
    metadata = ROOT / "build" / "designer" / "azure-signing.json"
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(json.dumps({
        "Endpoint": os.environ["PYZED_AZURE_SIGNING_ENDPOINT"],
        "CodeSigningAccountName": os.environ["PYZED_AZURE_SIGNING_ACCOUNT"],
        "CertificateProfileName": os.environ["PYZED_AZURE_SIGNING_PROFILE"],
    }), encoding="utf-8")
    return ["/dlib", dlib, "/dmdf", str(metadata), "/tr", "http://timestamp.acs.microsoft.com"]


def sign(bundle: Path) -> None:
    """Signs the app (or one file, like the setup program) when the environment carries the certificates (see
    the module docstring)."""
    if sys.platform == "darwin" and os.environ.get("PYZED_CODESIGN_IDENTITY"):
        subprocess.run(["codesign", "--force", "--deep", "--options", "runtime", "--timestamp",
                        "--sign", os.environ["PYZED_CODESIGN_IDENTITY"], str(bundle)], check=True)
        print(f"Signed {bundle.name}")
    elif sys.platform == "win32":
        identity = windows_identity()
        if identity is None:
            return
        # the executables and the Python extensions (Pyzed's core is the biggest file Windows checks at start)
        files = [str(bundle)] if bundle.is_file() else sorted(
            str(p) for pattern in ("*.exe", "*.pyd") for p in bundle.rglob(pattern))
        subprocess.run([signtool(), "sign", *identity, "/fd", "sha256", "/td", "sha256", *files], check=True)
        print(f"Signed {len(files)} files")


def notarize(bundle: Path, archive: str) -> bool:
    """Sends ``archive`` (the zipped app or the dmg) to Apple's notary service and staples the ticket to
    ``bundle`` (the app or the dmg); ``False`` when not set up."""
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


def iscc() -> str:
    """Inno Setup's compiler (``choco install innosetup`` installs it)."""
    found = shutil.which("iscc")
    if found:
        return found
    for name in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(name)
        for folder in (("Inno Setup 6",), ("Programs", "Inno Setup 6")):
            candidate = Path(base or ".").joinpath(*folder, "ISCC.exe")
            if base and candidate.exists():
                return str(candidate)
    sys.exit("error: ISCC.exe not found (install Inno Setup 6: choco install innosetup)")


def installer_name(archive: str) -> str:
    """``pyzed-design-windows-x86_64.zip`` -> ``pyzed-design-windows-x86_64-setup.exe`` (``.dmg`` on macOS)."""
    stem = Path(archive).name[:-4]
    return f"{stem}-setup.exe" if sys.platform == "win32" else f"{stem}.dmg"


def windows_installer(bundle: Path, out: Path, name: str, version: str) -> Path:
    """Compiles the per-user setup program from the PyInstaller folder."""
    script = ROOT / "installer" / "windows" / "pyzed-design.iss"
    command = [iscc(), "/Q", f"/DAppVersion={version}", f"/DSourceDir={bundle}", f"/DOutputDir={out}",
               f"/DOutputName={name[:-4]}"]
    icon = ROOT / "assets" / "icon.ico"
    if icon.exists():
        command.append(f"/DSetupIcon={icon}")
    subprocess.run([*command, str(script)], check=True)
    setup = out / name
    sign(setup)
    return setup


def macos_dmg(bundle: Path, out: Path, name: str) -> Path:
    """A compressed disk image with the app and a shortcut to Applications, to drag it in."""
    staging = ROOT / "build" / "designer" / "dmg"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    # ditto keeps the bundle's symlinks, signature and stapled ticket
    subprocess.run(["ditto", str(bundle), str(staging / bundle.name)], check=True)
    (staging / "Applications").symlink_to("/Applications")
    dmg = out / name
    dmg.unlink(missing_ok=True)
    subprocess.run(["hdiutil", "create", "-volname", NAME, "-srcfolder", str(staging), "-fs", "HFS+",
                    "-format", "UDZO", "-ov", str(dmg)], check=True)
    shutil.rmtree(staging, ignore_errors=True)
    if os.environ.get("PYZED_CODESIGN_IDENTITY"):
        subprocess.run(["codesign", "--force", "--timestamp", "--sign", os.environ["PYZED_CODESIGN_IDENTITY"],
                        str(dmg)], check=True)
        notarize(dmg, str(dmg))
    return dmg


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(ROOT / "dist"), help="output folder")
    parser.add_argument("--no-zip", action="store_true", help="do not zip the result")
    parser.add_argument("--installer", action="store_true",
                        help="also make the setup program (Windows) or the disk image (macOS)")
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
    # the Agent panel's optional dependencies (Claude's SDK and the system keychain), when installed: their
    # modules compiled into the archive like the rest, without the sources ``--collect-all`` would add next to them
    # (some 2,400 .py files the app never reads, that only make the download, the install and the antivirus's
    # first scan slower)
    for package in ("anthropic", "keyring"):
        if importlib.util.find_spec(package):
            command += ["--collect-submodules", package, "--collect-data", package, "--collect-binaries", package,
                        "--copy-metadata", package]
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
        if args.installer and sys.platform in ("win32", "darwin"):
            from pyzed import __version__

            name = installer_name(archive)
            made = windows_installer(bundle, out, name, __version__) if sys.platform == "win32" \
                else macos_dmg(bundle, out, name)
            print(f"Wrote {made}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
