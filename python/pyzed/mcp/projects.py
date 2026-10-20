"""What the MCP server does in a folder: create a Pyzed project, edit its files, add dependencies,
check it, run its tests and take screenshots of its forms and scripts.

Every path is relative to a ``root`` folder (where the server was started, or ``pyzed mcp --root``)
and can never leave it. Files that may hold secrets (``.env``, keys...) are out of reach, like for the
agents of Pyzed Design (see ``pyzed.agents.tools.SECRET_FILES``).
"""

from __future__ import annotations

import fnmatch
import platform
import sys
import tempfile
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
    entry = _entry(project)

    def designed(suffix: str) -> List[str]:
        return [_rel(root, p) for p in _walk(proj_root) if p.suffix == suffix]

    return {
        "project": project.name, "folder": _rel(root, proj_root) or ".", "version": project.version,
        "is_pyzed": project.is_pyzed,
        "entry": _rel(root, entry) if entry is not None else None,
        "main_form": _rel(root, project.main_form) if project.main_form.exists() else None,
        "script": _rel(root, project.script) if project.script is not None and project.script.exists() else None,
        "forms": [_rel(root, p) for p in project.forms()],
        "components": designed(".pzcomp"), "shaders": designed(".pzshad"),
        "package": _rel(root, project.src_dir) if project.src_dir else None,
        "dependencies": deps, "environment": environment(project), "files": files,
        "run": "start_live_preview shows the entry with hot reload while you edit; screenshot_project for a "
               "picture; the user runs it with `pyzed run` (forms) or `pyzed dev <script>.py`",
    }


def _entry(project) -> Optional[Path]:
    """Where the app starts: the ``script`` of ``[tool.pyzed]``, else the main form."""
    for path in (project.script, project.main_form):
        if path is not None and path.exists():
            return path
    return None


def _is_wsl() -> bool:
    try:
        from .._platform import is_wsl
    except ImportError:  # pragma: no cover - older layout
        return False
    return is_wsl()


def environment(project=None) -> Dict[str, Any]:
    """Where the code runs: the system, whether it is WSL, the interpreter and the project's ``.venv``."""
    from .. import project as _project

    out: Dict[str, Any] = {"system": platform.system(), "wsl": _is_wsl(), "uv": _project.find_uv(),
                           "server_python": sys.version.split()[0]}
    if project is not None:
        python = project.python_executable()
        out.update(venv=str(project.venv) if python else None, venv_python=project.venv_python_version(),
                   runs_in="the project's .venv (through uv run)" if python and not project.uses_own_venv
                   else "this interpreter")
        if python is None:
            out["note"] = "No .venv yet: add_dependency or `uv sync` creates it."
    return out


def launcher(root: Path, path: str = ".") -> Tuple[List[str], Dict[str, str]]:
    """The command and variables that start Python for the project at ``path``: its own ``.venv`` through
    ``uv run`` when it has one (so its dependencies import), else this interpreter with this same pyzed."""
    from .. import project as _project
    from .preview import this_python

    project = _find(root, path)
    uv = _project.find_uv()
    if project is not None and uv and project.python_executable() is not None and not project.uses_own_venv:
        return [uv, "run", "--project", str(project.root), "python"], _project._clean_env()
    return this_python()


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
    if path.suffix == ".pzshad":
        from . import shaders

        try:
            result = shaders.check(path.read_text(encoding="utf-8"))
        except Exception as err:  # noqa: BLE001 - a file that is not a shader graph
            return {"ok": False, "issues": [{"severity": "error", "message": f"not a valid .pzshad: {err}"}]}
        issues = [{"severity": "error", "message": f"node {node_id} ({e['node']}): {e['error']}"}
                  for node_id, e in result["errors"].items()]
        if result["compiler"]:
            issues.append({"severity": "error", "message": f"WGSL: {result['compiler']}"})
        return {"ok": not issues, "issues": issues}
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


DESIGNED = (".pzform", ".pzcomp", ".pzshad")


def screenshot(root: Path, target: str = "", *, size: Optional[Tuple[int, int]] = None) -> Tuple[str, bytes]:
    """Renders a script, form, component or shader graph of the folder off-screen, in the project's own
    environment; by default the project's entry (its script, else its main form). Returns a caption and the PNG."""
    from .preview import render_file

    path = _target(root, target)
    python, env = launcher(root, _rel(root, path.parent))
    if path.suffix == ".py":
        return f"Screenshot of {_rel(root, path)}.", render_file(path, size=size, python=python, env=env)
    if path.suffix == ".pzform" and size is None:
        from ..designer.model import load

        form = load(path)
        size = (int(form.width) or 480, int(form.height) or 320)
    with tempfile.TemporaryDirectory(prefix="pyzed-mcp-") as tmp:
        script = Path(tmp) / "run_designed.py"
        script.write_text(f"import sys\nsys.path.insert(0, {str(path.parent)!r})\n"
                          f"from pyzed.designer.runtime import run\nrun({str(path)!r})\n", encoding="utf-8")
        png = render_file(script, size=size or (640, 400), python=python, env=env)
    return f"Screenshot of {_rel(root, path)}.", png


def _target(root: Path, target: str) -> Path:
    if not target:
        entry = _entry(_project(root))
        if entry is None:
            raise FileNotFoundError("the project has no script or main form yet; pass the file to show")
        target = _rel(root, entry)
    path = resolve(root, target)
    if not path.is_file():
        raise FileNotFoundError(target)
    if path.suffix != ".py" and path.suffix not in DESIGNED:
        raise ValueError("this shows .py scripts and .pzform, .pzcomp and .pzshad files")
    return path
