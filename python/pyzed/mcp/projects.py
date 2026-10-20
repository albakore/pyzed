"""What the MCP server does in a folder: create a Pyzed project, edit its files, add dependencies,
check it, run its tests and take screenshots of its forms and scripts.

Every path is relative to a ``root`` folder (where the server was started, or ``pyzed mcp --root``)
and can never leave it. Files that may hold secrets (``.env``, keys...) are out of reach, like for the
agents of Pyzed Design (see ``pyzed.agents.tools.SECRET_FILES``).
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import validate

#: Folders the file tools skip.
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "target", "__pycache__", "dist", "build", ".ruff_cache",
             ".pytest_cache", ".mypy_cache"}
#: Bytes ``read_file`` returns at most, and the most ``write_files`` takes per file.
READ_LIMIT = 200_000
WRITE_LIMIT = 1_000_000
#: Characters of command output kept in results.
OUTPUT_LIMIT = 6000


def _secret_patterns() -> Sequence[str]:
    from ..agents.tools import SECRET_FILES

    return SECRET_FILES


def resolve(root: Path, path: str = ".") -> Path:
    """``path`` under ``root``; raises ``PermissionError`` when it points outside it or at a secret file."""
    root = Path(root).resolve()
    target = (root / (path or ".")).resolve()
    if target != root and root not in target.parents:
        raise PermissionError(f"{path} is outside the folder this server works in ({root})")
    if any(fnmatch.fnmatch(target.name, p) for p in _secret_patterns()):
        raise PermissionError(f"{path} may hold secrets, so it is out of reach")
    return target


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(Path(root).resolve()).as_posix()


def _walk(base: Path) -> List[Path]:
    hidden = _secret_patterns()
    out = []
    for path in sorted(base.rglob("*")):
        rel = path.relative_to(base)
        if any(part in SKIP_DIRS for part in rel.parts) or not path.is_file():
            continue
        if any(fnmatch.fnmatch(path.name, p) for p in hidden):
            continue
        out.append(path)
    return out


def _clip(text: str) -> str:
    return text if len(text) <= OUTPUT_LIMIT else "…" + text[-OUTPUT_LIMIT:]


def _find(root: Path, path: str = "."):
    """The project that holds ``path``, when its folder is inside ``root``."""
    from ..project import Project

    found = Project.find(resolve(root, path))
    if found is None:
        return None
    base, folder = Path(root).resolve(), Path(found.root).resolve()
    return found if folder == base or base in folder.parents else None


def _project(root: Path, path: str = "."):
    found = _find(root, path)
    if found is None:
        raise FileNotFoundError(f"no pyproject.toml in {path} or its parents inside {root}; "
                                "create one with create_project")
    return found


# -- reading -------------------------------------------------------------------------------------------


def info(root: Path, path: str = ".") -> Dict[str, Any]:
    """The project at ``path``: name, version, main form, forms, components, package, dependencies and files."""
    base = resolve(root, path)
    project = _find(root, path)
    files = [_rel(root, p) for p in _walk(base)][:300]
    if project is None:
        return {"project": None, "root": str(Path(root).resolve()), "files": files,
                "note": "No Pyzed project here: create_project makes one (uv, ui/ with a main form, src/<package>)."}
    proj_root = Path(project.root)
    deps = []
    try:
        deps = [{"name": d.name, "spec": d.spec, "locked": d.locked, "group": d.group} for d in project.dependencies()]
    except Exception:  # noqa: BLE001 - an unreadable lock file still leaves the rest useful
        pass
    return {
        "project": project.name, "folder": _rel(root, proj_root) or ".", "version": project.version,
        "is_pyzed": project.is_pyzed,
        "main_form": _rel(root, project.main_form) if project.main_form.exists() else None,
        "forms": [_rel(root, p) for p in project.forms()],
        "components": [_rel(root, p) for p in sorted(proj_root.rglob("*.pzcomp")) if ".venv" not in p.parts],
        "package": _rel(root, project.src_dir) if project.src_dir else None,
        "dependencies": deps, "files": files,
        "run": "pyzed run (the main form) or python <script>.py; pyzed dev <script>.py for hot reload",
    }


def list_files(root: Path, pattern: str = "*", path: str = ".", limit: int = 300) -> Dict[str, Any]:
    """Files under ``path`` whose relative path or name matches the glob ``pattern``."""
    base = resolve(root, path)
    out = []
    for p in _walk(base):
        rel = _rel(root, p)
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(p.name, pattern):
            out.append(rel)
            if len(out) >= limit:
                break
    return {"root": str(Path(root).resolve()), "files": out}


def read_file(root: Path, path: str) -> str:
    """The text of a file (the first ``READ_LIMIT`` bytes)."""
    target = resolve(root, path)
    if not target.is_file():
        raise FileNotFoundError(path)
    return target.read_bytes()[:READ_LIMIT].decode("utf-8", "replace")


# -- writing -------------------------------------------------------------------------------------------


def write_files(root: Path, files: Dict[str, str]) -> Dict[str, Any]:
    """Writes each ``{path: text}`` (creating folders), then checks the Python files and forms it wrote."""
    written, checks = [], {}
    for path, text in files.items():
        if len(text.encode("utf-8")) > WRITE_LIMIT:
            raise ValueError(f"{path} is larger than {WRITE_LIMIT // 1000} KB")
        target = resolve(root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))  # as given: no newline translation on Windows
        written.append(_rel(root, target))
    for rel in written:
        result = _check_file(Path(root).resolve() / rel)
        if result is not None and result["issues"]:
            checks[rel] = result
    return {"written": written, "checks": checks, "ok": all(c["ok"] for c in checks.values())}


def create_project(root: Path, name: str, *, folder: str = ".", package: bool = True, git: bool = True,
                   sync: bool = True) -> Dict[str, Any]:
    """Creates a Pyzed project with uv in ``folder/name`` and returns its ``info``."""
    from .. import project as _project

    if _project.find_uv() is None:
        raise RuntimeError("uv is needed to create projects: https://docs.astral.sh/uv/getting-started/installation/")
    target = resolve(root, f"{folder.rstrip('/')}/{name}" if folder not in ("", ".") else name)
    if target.exists() and any(target.iterdir()) and not (target / "pyproject.toml").exists():
        raise FileExistsError(f"{_rel(root, target)} exists and is not empty")
    _project.init(target, package=package, git=git, sync=sync)
    return info(root, _rel(root, target))


def add_dependency(root: Path, packages: Sequence[str], *, dev: bool = False, path: str = ".") -> Dict[str, Any]:
    """``uv add`` in the project at ``path``."""
    result = _project(root, path).add(*packages, dev=dev)
    return {"ok": result.ok, "output": _clip(result.output)}


# -- checking and running --------------------------------------------------------------------------------


def _check_file(path: Path) -> Optional[Dict[str, Any]]:
    if path.suffix == ".py":
        return validate.check_code(path.read_text(encoding="utf-8"), lint=False)
    if path.suffix == ".pzform":
        handlers = path.with_suffix(".py")
        return validate.check_form(path.read_text(encoding="utf-8"),
                                   handlers.read_text(encoding="utf-8") if handlers.is_file() else "")
    return None


def check_project(root: Path, path: str = ".", *, tools: bool = True) -> Dict[str, Any]:
    """Pyzed's own checks of every Python file and form under ``path`` and, with ``tools``, ruff and ty."""
    base = resolve(root, path)
    files: Dict[str, Any] = {}
    for p in _walk(base):
        result = _check_file(p)
        if result is not None and result["issues"]:
            files[_rel(root, p)] = result["issues"]
    out: Dict[str, Any] = {"pyzed": files}
    ok = not any(i["severity"] == "error" for issues in files.values() for i in issues)
    if tools:
        try:
            project = _project(root, path)
        except FileNotFoundError:
            project = None
        if project is not None:
            lint, types = project.check(), project.typecheck()
            out["ruff"] = {"ok": lint.ok, "output": _clip(lint.output)}
            out["ty"] = {"ok": types.ok, "output": _clip(types.output)}
            ok = ok and lint.ok
    out["ok"] = ok
    return out


def run_tests(root: Path, path: str = ".", args: Sequence[str] = ()) -> Dict[str, Any]:
    """``uv run pytest -q`` in the project at ``path``."""
    result = _project(root, path).uv("run", "pytest", "-q", *args, timeout=600)
    return {"ok": result.ok, "output": _clip(result.output)}


def screenshot(root: Path, target: str = "", *, size: Optional[Tuple[int, int]] = None) -> Tuple[str, bytes]:
    """Renders a form (``.pzform``) or a script of the folder off-screen; by default the project's main form.
    Returns a caption and the PNG."""
    from .preview import render, render_file

    if not target:
        project = _project(root)
        if not project.main_form.exists():
            raise FileNotFoundError("the project has no main form; pass the script or form to show")
        target = _rel(root, project.main_form)
    path = resolve(root, target)
    if not path.is_file():
        raise FileNotFoundError(target)
    if path.suffix == ".pzform":
        from ..designer.model import load

        form = load(path)
        size = size or (int(form.width) or 480, int(form.height) or 320)
        script = (f"import sys\nsys.path.insert(0, {str(path.parent)!r})\nimport pyzed as pz\n"
                  f"from pyzed.designer.runtime import open_form\npz.run(open_form({str(path)!r}))\n")
        png = render(script, size=size)
    elif path.suffix == ".py":
        png = render_file(path, size=size)
    else:
        raise ValueError("screenshot shows .pzform forms and .py scripts")
    return f"Screenshot of {_rel(root, path)}.", png
