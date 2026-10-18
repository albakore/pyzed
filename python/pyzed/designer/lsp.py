"""Language servers for the designer's code editor: ty (types, completion, references) and ruff (lint).

The client speaks JSON-RPC over the server's stdin/stdout. A reader thread parses replies and
notifications and hands them to ``dispatch`` (in the designer, ``pyzed.post``) so callbacks run
on the UI thread. Nothing here imports the UI.

Servers are started in the form's *project*: the nearest folder with a ``pyproject.toml``
(a uv project), with its ``.venv`` as the Python environment. That is what lets ``import httpx``
resolve and complete in a form that lives in ``ui/`` while the dependencies are declared at the
project root.
"""

from __future__ import annotations

import itertools
import json
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote, unquote, urlparse

Callback = Callable[[Any], None]
Dispatch = Callable[[Callable[[], None]], None]

#: Files whose presence marks a project root, from most to least specific.
ROOT_MARKERS = ("pyproject.toml", "uv.lock", "setup.py", "setup.cfg", ".git")


# ---------------------------------------------------------------------------
# The project environment
# ---------------------------------------------------------------------------


@dataclass
class Environment:
    """Where a form's code runs: its project root, virtual environment and import roots."""

    root: Path
    venv: Optional[Path] = None
    #: Extra folders searched for first-party imports (the form's own folder, ``src/``...).
    extra_paths: List[Path] = field(default_factory=list)

    @property
    def python(self) -> str:
        if self.venv is not None:
            exe = self.venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            if exe.exists():
                return str(exe)
        return sys.executable

    @property
    def bin_dirs(self) -> List[Path]:
        dirs = []
        if self.venv is not None:
            dirs.append(self.venv / ("Scripts" if os.name == "nt" else "bin"))
        dirs.append(Path(sys.executable).parent)
        return dirs

    def tool(self, name: str) -> Optional[str]:
        """The ``ty``/``ruff`` executable: the project's venv first, then the designer's, then ``PATH``."""
        exe = name + (".exe" if os.name == "nt" else "")
        for folder in self.bin_dirs:
            if (folder / exe).exists():
                return str(folder / exe)
        return shutil.which(name)

    def settings(self) -> Dict[str, Any]:
        """ty's inline configuration: the interpreter and the extra import roots."""
        env: Dict[str, Any] = {"extra-paths": [str(p) for p in self.extra_paths]}
        if self.venv is not None:
            env["python"] = str(self.venv)
        return {"environment": env}


def find_root(start: Path) -> Path:
    """The closest folder at or above ``start`` holding a project marker (``start`` itself if none)."""
    start = start if start.is_dir() else start.parent
    for marker in ROOT_MARKERS:
        for folder in (start, *start.parents):
            if (folder / marker).exists():
                return folder
    return start


def find_environment(path: Optional[Path]) -> Environment:
    """The environment of the code at ``path`` (a form, its handlers or a folder).

    Uses ``pyzed.project`` when a Pyzed project is open there; otherwise walks up to the
    project root and takes its ``.venv`` (uv's default), then ``$VIRTUAL_ENV``.
    """
    here = (path or Path.cwd()).resolve()
    folder = here if here.is_dir() else here.parent
    project = _pyzed_project(folder)
    if project is not None:
        return project
    root = find_root(folder)
    venv = None
    for candidate in (root / ".venv", folder / ".venv", Path(os.environ.get("VIRTUAL_ENV", "") or "/nonexistent")):
        if (candidate / "pyvenv.cfg").exists():
            venv = candidate
            break
    extra = [folder] if folder != root else []
    if (root / "src").is_dir():
        extra.append(root / "src")
    return Environment(root=root, venv=venv, extra_paths=extra)


def _pyzed_project(folder: Path) -> Optional[Environment]:
    """Reuses ``pyzed.project`` (uv projects made with Pyzed Design) when it is available."""
    try:
        from .. import project as _project  # type: ignore[attr-defined]
    except ImportError:
        return None
    try:
        proj = _project.find(folder) if hasattr(_project, "find") else None
        if proj is None:
            return None
        root = Path(proj.root)
        venv = Path(proj.venv) if getattr(proj, "venv", None) else None
        if venv is None or not (venv / "pyvenv.cfg").exists():
            python = proj.python_executable()
            venv = Path(python).parent.parent if python else None
        paths = [Path(p) for p in proj.paths() if Path(p) != root]
        if folder != root and folder not in paths:
            paths.insert(0, folder)
        return Environment(root=root, venv=venv, extra_paths=paths)
    except Exception:  # noqa: BLE001 - fall back to our own detection
        return None


def uri(path: Path) -> str:
    text = Path(path).resolve().as_posix()
    if not text.startswith("/"):
        text = "/" + text
    return "file://" + quote(text)


def path_of(uri_: str) -> Path:
    parsed = urlparse(uri_)
    text = unquote(parsed.path)
    if os.name == "nt" and text.startswith("/") and len(text) > 2 and text[2] == ":":
        text = text[1:]
    return Path(text)


# ---------------------------------------------------------------------------
# The JSON-RPC client
# ---------------------------------------------------------------------------

CLIENT_CAPABILITIES: Dict[str, Any] = {
    "general": {"positionEncodings": ["utf-16"]},
    "textDocument": {
        "synchronization": {"didSave": True, "dynamicRegistration": False},
        "completion": {
            "completionItem": {
                "snippetSupport": False,
                "documentationFormat": ["markdown", "plaintext"],
                "labelDetailsSupport": True,
                "resolveSupport": {"properties": ["documentation", "detail"]},
            },
            "contextSupport": True,
        },
        "hover": {"contentFormat": ["markdown", "plaintext"]},
        "publishDiagnostics": {"relatedInformation": False, "codeDescriptionSupport": True},
        "references": {},
        "definition": {},
        "implementation": {},
        "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
        "codeLens": {},
    },
    "workspace": {"configuration": True, "workspaceFolders": True},
    "window": {"workDoneProgress": False},
}


class LanguageServer:
    """One language server process.

    ``status`` is ``"stopped"``, ``"starting"``, ``"ready"``, ``"missing"`` (not installed)
    or ``"error"``; ``detail`` says more (the version, or what went wrong). ``on_status`` and
    ``on_notification(method, params)`` are called through ``dispatch``.
    """

    def __init__(
        self,
        name: str,
        command: Optional[Sequence[str]],
        root: Path,
        *,
        settings: Optional[Dict[str, Any]] = None,
        initialization_options: Optional[Dict[str, Any]] = None,
        env: Optional[Dict[str, str]] = None,
        dispatch: Optional[Dispatch] = None,
        on_status: Optional[Callable[["LanguageServer"], None]] = None,
        on_notification: Optional[Callable[[str, Any], None]] = None,
    ) -> None:
        self.name = name
        self.command = list(command) if command else None
        self.root = Path(root)
        self.settings = settings or {}
        self.initialization_options = initialization_options
        self.env = env
        self.dispatch: Dispatch = dispatch or (lambda fn: fn())
        self.on_status = on_status
        self.on_notification = on_notification
        self.status = "stopped" if command else "missing"
        self.detail = "" if command else f"{name} not found: add it with `uv add --dev {name}`"
        self.capabilities: Dict[str, Any] = {}
        self.process: Optional[subprocess.Popen] = None
        self._ids = itertools.count(1)
        self._pending: Dict[int, Callback] = {}
        self._lock = threading.Lock()
        self._queue: List[Tuple[str, Any]] = []  # notifications sent before the server is ready
        self.versions: Dict[str, int] = {}

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        if self.command is None or self.process is not None:
            return
        try:
            self.process = subprocess.Popen(
                self.command,
                cwd=str(self.root),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env={**os.environ, **(self.env or {})},
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as err:
            self._set_status("error", str(err))
            return
        self._set_status("starting", "")
        threading.Thread(target=self._read, name=f"lsp-{self.name}", daemon=True).start()
        params = {
            "processId": os.getpid(),
            "clientInfo": {"name": "pyzed-designer"},
            "rootUri": uri(self.root),
            "workspaceFolders": [{"uri": uri(self.root), "name": self.root.name}],
            "capabilities": CLIENT_CAPABILITIES,
        }
        if self.initialization_options is not None:
            params["initializationOptions"] = self.initialization_options
        id_ = next(self._ids)
        self._pending[id_] = self._initialized
        self._send({"jsonrpc": "2.0", "id": id_, "method": "initialize", "params": params})

    def _initialized(self, result: Any) -> None:
        if not isinstance(result, dict):
            return
        self.capabilities = result.get("capabilities") or {}
        info = result.get("serverInfo") or {}
        self._send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
        if self.settings:
            self._send({"jsonrpc": "2.0", "method": "workspace/didChangeConfiguration",
                        "params": {"settings": self.settings}})
        queued, self._queue = self._queue, []
        for method, params in queued:
            self._send({"jsonrpc": "2.0", "method": method, "params": params})
        self._set_status("ready", " ".join(x for x in (info.get("name"), info.get("version")) if x))

    def stop(self) -> None:
        process, self.process = self.process, None
        if process is None:
            return
        try:
            self._write(process, {"jsonrpc": "2.0", "id": next(self._ids), "method": "shutdown"})
            self._write(process, {"jsonrpc": "2.0", "method": "exit"})
            process.wait(timeout=1)
        except Exception:  # noqa: BLE001
            process.kill()
        self._pending.clear()
        self.versions.clear()
        self._set_status("stopped", "")

    def restart(self) -> None:
        self.stop()
        self.start()

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def supports(self, capability: str) -> bool:
        return bool(self.capabilities.get(capability))

    # -- messages -----------------------------------------------------------
    def request(self, method: str, params: Any, callback: Callback) -> Optional[int]:
        """Sends a request; ``callback(result)`` runs through ``dispatch`` (``None`` on error)."""
        if not self.ready:
            return None
        id_ = next(self._ids)
        with self._lock:
            self._pending[id_] = callback
        self._send({"jsonrpc": "2.0", "id": id_, "method": method, "params": params})
        return id_

    def cancel(self, id_: Optional[int]) -> None:
        if id_ is not None and self._pending.pop(id_, None) is not None:
            self.notify("$/cancelRequest", {"id": id_})

    def notify(self, method: str, params: Any) -> None:
        if self.status == "starting":
            self._queue.append((method, params))
        elif self.ready:
            self._send({"jsonrpc": "2.0", "method": method, "params": params})

    # -- documents (full sync) ----------------------------------------------
    def open(self, uri_: str, text: str, language: str = "python") -> None:
        if uri_ in self.versions:
            return self.change(uri_, text)
        self.versions[uri_] = 1
        self.notify("textDocument/didOpen",
                    {"textDocument": {"uri": uri_, "languageId": language, "version": 1, "text": text}})

    def change(self, uri_: str, text: str) -> None:
        if uri_ not in self.versions:
            return self.open(uri_, text)
        self.versions[uri_] += 1
        self.notify("textDocument/didChange", {"textDocument": {"uri": uri_, "version": self.versions[uri_]},
                                               "contentChanges": [{"text": text}]})

    def close(self, uri_: str) -> None:
        if self.versions.pop(uri_, None) is not None:
            self.notify("textDocument/didClose", {"textDocument": {"uri": uri_}})

    # -- plumbing -----------------------------------------------------------
    def _set_status(self, status: str, detail: str) -> None:
        self.status, self.detail = status, detail
        if self.on_status is not None:
            self.dispatch(lambda: self.on_status(self))

    def _send(self, message: Dict[str, Any]) -> None:
        if self.process is not None:
            try:
                self._write(self.process, message)
            except (OSError, ValueError) as err:
                self._died(str(err))

    @staticmethod
    def _write(process: subprocess.Popen, message: Dict[str, Any]) -> None:
        body = json.dumps(message).encode("utf-8")
        assert process.stdin is not None
        process.stdin.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
        process.stdin.flush()

    def _died(self, reason: str) -> None:
        if self.process is not None:
            self.process = None
            self._pending.clear()
            self.versions.clear()
            self._set_status("error", reason or "the server stopped")

    def _read(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return
        stream = process.stdout
        while True:
            length = 0
            while True:
                line = stream.readline()
                if not line:
                    if self.process is process:
                        self.dispatch(lambda: self._died(f"{self.name} exited"))
                    return
                line = line.strip()
                if not line:
                    break
                key, _, value = line.partition(b":")
                if key.lower() == b"content-length":
                    length = int(value)
            if length <= 0:
                continue
            try:
                message = json.loads(stream.read(length))
            except ValueError:
                continue
            self._handle(message)

    def _handle(self, message: Dict[str, Any]) -> None:
        if "method" in message and "id" in message:
            self._answer(message)
        elif "method" in message:
            if self.on_notification is not None:
                method, params = message["method"], message.get("params")
                self.dispatch(lambda: self.on_notification(method, params))
        elif "id" in message:
            with self._lock:
                callback = self._pending.pop(message["id"], None)
            if callback is not None:
                result = message.get("result")
                self.dispatch(lambda: callback(result))

    def _answer(self, request: Dict[str, Any]) -> None:
        """Replies to server-to-client requests (configuration, registrations, progress)."""
        result: Any = None
        if request["method"] == "workspace/configuration":
            items = (request.get("params") or {}).get("items") or []
            result = [self._section(item.get("section")) for item in items]
        elif request["method"] == "workspace/workspaceFolders":
            result = [{"uri": uri(self.root), "name": self.root.name}]
        self._send({"jsonrpc": "2.0", "id": request["id"], "result": result})

    def _section(self, section: Optional[str]) -> Any:
        if not section:
            return self.settings
        value: Any = self.settings
        for part in section.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        return value if value is not None else {}


# ---------------------------------------------------------------------------
# Servers for a project
# ---------------------------------------------------------------------------


def ty_server(env: Environment, **kwargs: Any) -> LanguageServer:
    exe = env.tool("ty")
    settings = {"ty": {"configuration": env.settings()}}
    return LanguageServer(
        "ty", [exe, "server"] if exe else None, env.root, settings=settings,
        initialization_options={"configuration": env.settings()},
        env={"VIRTUAL_ENV": str(env.venv)} if env.venv else None, **kwargs)


def ruff_server(env: Environment, **kwargs: Any) -> LanguageServer:
    exe = env.tool("ruff")
    return LanguageServer("ruff", [exe, "server"] if exe else None, env.root,
                          settings={"ruff": {}}, initialization_options={"settings": {}}, **kwargs)
