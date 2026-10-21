"""File operations behind the Project tab's menu, like Zed's project panel: the trash, a terminal
in a folder, free names for copies, ignore files, permalinks, and the undo history of file changes.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote

from .. import project as _project


# -- the system --------------------------------------------------------------------------------


def send_to_trash(path: Path) -> None:
    """Moves ``path`` (a file or a folder) to the system's trash, where it can be restored."""
    path = Path(path).absolute()
    if not path.exists() and not path.is_symlink():
        raise FileNotFoundError(str(path))
    if sys.platform == "darwin":
        script = f'tell application "Finder" to delete POSIX file "{path}"'
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)  # noqa: S603, S607
    elif sys.platform == "win32":
        _windows_trash(path)
    else:
        gio = shutil.which("gio")
        if gio is not None:
            if subprocess.run([gio, "trash", str(path)], capture_output=True).returncode == 0:  # noqa: S603
                return
        freedesktop_trash(path)


def freedesktop_trash(path: Path, data_home: Optional[Path] = None) -> Path:
    """Moves ``path`` to the home trash of the freedesktop.org spec (Linux and BSD desktops); returns
    where it went."""
    data_home = data_home or Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    files, info = data_home / "Trash" / "files", data_home / "Trash" / "info"
    files.mkdir(parents=True, exist_ok=True)
    info.mkdir(parents=True, exist_ok=True)
    name, n = path.name, 1
    while (files / name).exists() or (info / f"{name}.trashinfo").exists():
        n += 1
        name = f"{path.stem}.{n}{path.suffix}"
    (info / f"{name}.trashinfo").write_text(
        f"[Trash Info]\nPath={quote(str(path))}\nDeletionDate={time.strftime('%Y-%m-%dT%H:%M:%S')}\n",
        encoding="utf-8")
    shutil.move(str(path), str(files / name))
    return files / name


def _windows_trash(path: Path) -> None:
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_uint16), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

    # FO_DELETE with FOF_ALLOWUNDO (to the Recycle Bin), no confirmation, no error dialogs, silent.
    op = SHFILEOPSTRUCTW(None, 3, str(path) + "\0", None, 0x0040 | 0x0010 | 0x0400 | 0x0004, False, None, None)
    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))  # type: ignore[attr-defined]
    if result != 0 or op.fAnyOperationsAborted:
        raise OSError(f"Could not move {path.name} to the Recycle Bin (error {result})")


#: Terminals tried on Linux, with how each is told the folder (``None``: it starts in the working directory).
TERMINALS = (("x-terminal-emulator", None), ("gnome-terminal", "--working-directory={}"),
             ("konsole", "--workdir={}"), ("xfce4-terminal", "--working-directory={}"), ("kitty", "--directory={}"),
             ("alacritty", "--working-directory={}"), ("wezterm", "start --cwd {}"), ("foot", None), ("xterm", None))


def terminal_command(folder: Path) -> List[str]:
    """The command that opens the system's terminal in ``folder`` (``OSError`` when none is found)."""
    if sys.platform == "darwin":
        return ["open", "-a", "Terminal", str(folder)]
    if sys.platform == "win32":
        wt = shutil.which("wt")
        return [wt, "-d", str(folder)] if wt else ["cmd", "/c", "start", "cmd"]
    choices = [(os.environ["TERMINAL"], None)] if os.environ.get("TERMINAL") else []
    for name, arg in [*choices, *TERMINALS]:
        found = shutil.which(name)
        if found:
            return [found, *(arg.format(folder).split(" ") if arg else [])]
    raise OSError("No terminal app was found")


#: How each Linux terminal is told to run a command (the arguments that go before it).
RUN_FLAGS = {"x-terminal-emulator": ["-e"], "gnome-terminal": ["--"], "konsole": ["-e"], "xfce4-terminal": ["-x"],
             "kitty": [], "alacritty": ["-e"], "wezterm": ["start", "--"], "foot": [], "xterm": ["-e"]}


def run_in_terminal_command(args: List[str], folder: Path) -> List[str]:
    """The command that opens the system's terminal running ``args`` in ``folder`` (``OSError`` when none is
    found), for programs that talk to the user, such as a sign-in."""
    if sys.platform == "darwin":
        line = f"cd {shlex.quote(str(folder))} && {shlex.join(args)}"
        script = 'tell application "Terminal" to do script "{}"'.format(line.replace("\\", "\\\\").replace('"', '\\"'))
        return ["osascript", "-e", script, "-e", 'tell application "Terminal" to activate']
    if sys.platform == "win32":
        wt = shutil.which("wt")
        return [wt, "-d", str(folder), "cmd", "/k", *args] if wt else ["cmd", "/c", "start", "", "cmd", "/k", *args]
    names = [os.environ["TERMINAL"]] if os.environ.get("TERMINAL") else []
    if not names:
        wsl = _windows_terminal_command(args, folder)
        if wsl:
            return wsl
    for name in [*names, *RUN_FLAGS]:
        found = shutil.which(name)
        if found:
            return [found, *RUN_FLAGS.get(Path(name).name, ["-e"]), *args]
    raise OSError("No terminal app was found")


def _windows_terminal_command(args: List[str], folder: Path) -> Optional[List[str]]:
    """Under WSL, a Windows terminal running ``args`` back in this Linux (``None`` elsewhere). Its shell runs
    as an interactive login shell, so programs installed through the shell's profile (nvm...) are found."""
    from .._platform import is_wsl, windows_command

    if not is_wsl():
        return None
    distro = os.environ.get("WSL_DISTRO_NAME")
    shell = os.environ.get("SHELL") or "/bin/bash"
    inside = ["wsl.exe", *(["-d", distro] if distro else []), "--cd", str(folder), "--", shell, "-lic",
              shlex.join(args)]
    wt = windows_command("wt.exe")
    if wt:
        return [wt, *inside]
    cmd = windows_command("cmd.exe")
    return [cmd, "/c", "start", "", *inside] if cmd else None


def run_in_terminal(args: List[str], folder: Path, env: Optional[Dict[str, str]] = None) -> None:
    """Opens the system's terminal running ``args`` in ``folder`` (with the extra environment ``env``)."""
    if env and sys.platform != "win32":  # the terminal may be started by a server that has its own environment
        args = ["env", *(f"{k}={v}" for k, v in env.items()), *args]
    subprocess.Popen(run_in_terminal_command(args, folder), cwd=folder, stdout=subprocess.DEVNULL,  # noqa: S603
                     stderr=subprocess.DEVNULL, start_new_session=sys.platform != "win32",
                     env={**os.environ, **env} if env else None)


def open_terminal(folder: Path) -> None:
    """Opens the system's terminal in ``folder``."""
    subprocess.Popen(terminal_command(folder), cwd=folder, stdout=subprocess.DEVNULL,  # noqa: S603
                     stderr=subprocess.DEVNULL, start_new_session=sys.platform != "win32")


# -- names and ignore files ----------------------------------------------------------------------


def free_name(path: Path) -> Path:
    """``path`` if it is free, else ``name copy.ext``, ``name copy 2.ext``... (like Zed's paste)."""
    if not path.exists():
        return path
    stem, suffix = (path.name, "") if path.is_dir() else (path.stem, path.suffix)
    stem = re.sub(r" copy( \d+)?$", "", stem)
    n = 1
    while True:
        name = f"{stem} copy{suffix}" if n == 1 else f"{stem} copy {n}{suffix}"
        candidate = path.with_name(name)
        if not candidate.exists():
            return candidate
        n += 1


def add_ignore(file: Path, rel: str) -> bool:
    """Adds ``/rel`` (anchored at the project folder) to the ignore ``file``; ``False`` if it was there."""
    pattern = "/" + rel.lstrip("/")
    text = file.read_text(encoding="utf-8") if file.exists() else ""
    if pattern in (line.strip() for line in text.splitlines()):
        return False
    file.parent.mkdir(parents=True, exist_ok=True)
    if text and not text.endswith("\n"):
        text += "\n"
    file.write_text(text + pattern + "\n", encoding="utf-8")
    return True


# -- permalinks ------------------------------------------------------------------------------------


def git_command(root: Path, *args: str) -> Optional[Tuple[List[str], Optional[Path], float]]:
    """How to run ``git args`` in ``root``: the command, its working folder and the seconds it may take. A WSL
    folder opened from Windows uses Linux's git through ``wsl.exe`` (Windows' git refuses those folders and is
    slow on them); ``None`` when git is not installed."""
    where = _project.environment(root)
    if where.remote:
        return where.command(["git", *args], root), None, 15
    git = shutil.which("git")
    return ([git, *args], root, 5) if git else None


def run_git(root: Path, *args: str) -> Optional["subprocess.CompletedProcess[bytes]"]:
    """Runs ``git args`` in ``root`` without a window or stdin, and with a time limit (``None`` when it could
    not run or took too long)."""
    found = git_command(root, *args)
    if found is None:
        return None
    command, cwd, timeout = found
    try:
        return subprocess.run(command, cwd=cwd, capture_output=True, stdin=subprocess.DEVNULL,  # noqa: S603
                              timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None


def _git(root: Path, *args: str) -> Optional[str]:
    out = run_git(root, *args)
    text = out.stdout.decode("utf-8", "replace").strip() if out is not None and out.returncode == 0 else ""
    return text or None


def web_url(remote: str) -> Optional[str]:
    """The web address of a git ``remote`` (``git@github.com:me/app.git`` → ``https://github.com/me/app``)."""
    remote = remote.strip()
    m = re.match(r"^(?:ssh://)?git@([^:/]+)[:/](.+?)(?:\.git)?/?$", remote)
    if m:
        return f"https://{m.group(1)}/{m.group(2)}"
    m = re.match(r"^https?://(?:[^@/]+@)?([^/]+)/(.+?)(?:\.git)?/?$", remote)
    if m:
        return f"https://{m.group(1)}/{m.group(2)}"
    return None


def remote_url(root: Path) -> Optional[str]:
    """The web address of the project's ``origin`` remote, if it has one."""
    if not (root / ".git").exists():
        return None
    remote = _git(root, "config", "--get", "remote.origin.url")
    return web_url(remote) if remote else None


def permalink(root: Path, rel: str, base: Optional[str] = None) -> Optional[str]:
    """A link to ``rel`` at the current commit on the project's remote (GitHub, GitLab, Codeberg...)."""
    base = base or remote_url(root)
    sha = _git(root, "rev-parse", "HEAD") if base else None
    if not base or not sha:
        return None
    kind = "tree" if rel.endswith("/") else "blob"
    path = quote(rel.rstrip("/"))
    return f"{base}/-/{kind}/{sha}/{path}" if "gitlab" in base else f"{base}/{kind}/{sha}/{path}"


# -- undo ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Op:
    """A file change that can be undone: ``create`` (``dest``), ``move`` and ``copy`` (``source`` to
    ``dest``). Paths are absolute."""

    kind: str
    dest: Path
    source: Optional[Path] = None
    folder: bool = False


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _check_free(path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"{path.name} already exists")


def copy_entry(source: Path, dest: Path) -> None:
    """Copies the file or folder ``source`` to ``dest``."""
    if source.is_dir() and not source.is_symlink():
        shutil.copytree(source, dest, symlinks=True)
    else:
        shutil.copy2(source, dest, follow_symlinks=False)


def undo(op: Op) -> Sequence[Path]:
    """Reverts ``op``; returns the paths whose open files must follow (``(old, new)`` for a move)."""
    if op.kind in ("create", "copy"):
        if op.kind == "create" and op.folder and op.dest.is_dir() and any(op.dest.iterdir()):
            raise OSError(f"{op.dest.name} is not empty anymore")
        _remove(op.dest)
        return (op.dest,)
    assert op.source is not None
    _check_free(op.source)
    shutil.move(str(op.dest), str(op.source))
    return (op.dest, op.source)


def redo(op: Op) -> Sequence[Path]:
    """Does ``op`` again; returns the paths like ``undo``."""
    _check_free(op.dest)
    if op.kind == "create":
        if op.folder:
            op.dest.mkdir(parents=True)
        else:
            op.dest.parent.mkdir(parents=True, exist_ok=True)
            op.dest.touch()
        return (op.dest,)
    assert op.source is not None
    if op.kind == "copy":
        copy_entry(op.source, op.dest)
        return (op.dest,)
    shutil.move(str(op.source), str(op.dest))
    return (op.source, op.dest)
