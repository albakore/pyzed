"""Pyzed's MCP server in the AI agents of this computer: Claude Code, Claude Desktop, Cursor, Windsurf, Gemini
CLI, Codex, VS Code and Zed. Pyzed Design finds the ones installed and adds the server to their settings
(once each, Settings → AI agents lists them), so they know Pyzed's components, docs and checks; each agent
reads it the next time it starts.

    from pyzed.agents import mcp_install

    for client in mcp_install.detected():
        if mcp_install.status(client) == "missing":
            mcp_install.install(client)

Only the ``pyzed`` entry is touched: the rest of each settings file is kept as it was, a copy of the file
is left next to it (``.pyzed-backup``) before the first change, and files that are not plain JSON (with
comments, say) are left alone.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

#: The server's name in every agent's settings.
SERVER = "pyzed"
#: What ``uvx`` runs: the published package with the MCP extra, so it works without installing anything.
PACKAGE = "pyzed-ui[mcp]"


@dataclass(frozen=True)
class Client:
    """An AI agent that reads MCP servers from a settings file."""

    id: str
    name: str
    #: ``"json"`` (the servers under ``key``), ``"toml"`` (Codex's ``[mcp_servers.<name>]``) or ``"claude"``
    #: (Claude Code: its ``claude mcp`` command when found, else its JSON file).
    format: str
    path: Path
    #: A folder that only exists when the agent is installed.
    marker: Path
    key: str = "mcpServers"
    #: A program on ``PATH`` that also shows the agent is installed.
    program: str = ""


def _app_data(home: Path) -> Path:
    """Where desktop apps keep their settings: ``%APPDATA%``, ``~/Library/Application Support`` or ``~/.config``."""
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming")
    if sys.platform == "darwin":
        return home / "Library" / "Application Support"
    return Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")


def clients(home: Optional[Path] = None) -> List[Client]:
    """Every agent Pyzed knows, with where its settings are on this platform."""
    home = Path(home) if home is not None else Path.home()
    data = _app_data(home)
    zed = data / "Zed" if os.name == "nt" else Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config") / "zed"
    return [
        Client("claude-code", "Claude Code", "claude", home / ".claude.json", home / ".claude", program="claude"),
        Client("claude-desktop", "Claude Desktop", "json", data / "Claude" / "claude_desktop_config.json",
               data / "Claude"),
        Client("cursor", "Cursor", "json", home / ".cursor" / "mcp.json", home / ".cursor"),
        Client("windsurf", "Windsurf", "json", home / ".codeium" / "windsurf" / "mcp_config.json",
               home / ".codeium" / "windsurf"),
        Client("gemini", "Gemini CLI", "json", home / ".gemini" / "settings.json", home / ".gemini", program="gemini"),
        Client("codex", "Codex", "toml", home / ".codex" / "config.toml", home / ".codex", program="codex"),
        Client("vscode", "VS Code", "json", data / "Code" / "User" / "mcp.json", data / "Code" / "User",
               key="servers"),
        Client("zed", "Zed", "json", zed / "settings.json", zed, key="context_servers"),
    ]


def detected(home: Optional[Path] = None) -> List[Client]:
    """The agents installed on this computer."""
    return [c for c in clients(home) if c.marker.is_dir() or (c.program and shutil.which(c.program))]


def server_command() -> Optional[List[str]]:
    """How an agent starts Pyzed's MCP server: ``uvx`` with the published package (always there, whatever
    project is open), Pyzed Design's own ``uv``, else this Python when it has the MCP SDK; ``None`` when none
    of them can."""
    uvx = shutil.which("uvx")
    if uvx:
        return [uvx, "--from", PACKAGE, "pyzed", "mcp"]
    from ..project import find_uv

    uv = find_uv()
    if uv:
        return [uv, "tool", "run", "--from", PACKAGE, "pyzed", "mcp"]
    if not getattr(sys, "frozen", False):
        try:
            import mcp  # noqa: F401
        except ImportError:
            return None
        return [sys.executable, "-m", "pyzed", "mcp"]
    return None


def _entry(client: Client, command: List[str]) -> Dict[str, Any]:
    entry: Dict[str, Any] = {"command": command[0], "args": command[1:]}
    return {"type": "stdio", **entry} if client.key == "servers" else entry


def _read_json(path: Path) -> Dict[str, Any]:
    """A settings file as a dict (``{}`` when it does not exist). Raises ``ValueError`` when it is not plain
    JSON, so it is left alone."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    if not text.strip():
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not hold a JSON object")
    return data


def _write(path: Path, text: str) -> None:
    """Writes ``text`` safely: a backup of the old file the first time, then a write-and-rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_name(path.name + ".pyzed-backup")
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
    tmp = path.with_name(path.name + ".pyzed-tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


#: Codex's table of the server (and its sub-tables, such as ``.env``) up to the next table.
_TOML_TABLE = re.compile(r"^\[mcp_servers\.(?:pyzed|\"pyzed\")(?:\.[\w\"-]+)*\][^\n]*\n(?:(?!\[)[^\n]*\n?)*", re.M)


def status(client: Client) -> str:
    """``"installed"`` (the agent has a ``pyzed`` server), ``"missing"`` or ``"unreadable"`` (its settings are
    not plain JSON, so Pyzed does not change them)."""
    try:
        if client.format == "toml":
            text = client.path.read_text(encoding="utf-8") if client.path.exists() else ""
            return "installed" if _TOML_TABLE.search(text + "\n") else "missing"
        servers = _read_json(client.path).get(client.key)
    except (OSError, ValueError):
        return "unreadable"
    return "installed" if isinstance(servers, dict) and SERVER in servers else "missing"


def install(client: Client, command: Optional[List[str]] = None) -> None:
    """Adds Pyzed's MCP server to ``client``'s settings. Raises ``OSError`` or ``ValueError`` when it cannot."""
    command = command or server_command()
    if not command:
        raise OSError("uv is not installed, so agents could not start Pyzed's MCP server")
    if client.format == "claude" and _claude_cli(["add", "--scope", "user", SERVER, "--", *command]):
        return
    if client.format == "toml":
        text = client.path.read_text(encoding="utf-8") if client.path.exists() else ""
        text = _TOML_TABLE.sub("", text + "\n" if text and not text.endswith("\n") else text)
        args = ", ".join(json.dumps(a) for a in command[1:])
        text = (text.rstrip("\n") + "\n\n" if text.strip() else "") + \
            f"[mcp_servers.{SERVER}]\ncommand = {json.dumps(command[0])}\nargs = [{args}]\n"
        _write(client.path, text)
        return
    data = _read_json(client.path)
    servers = data.get(client.key)
    if not isinstance(servers, dict):
        servers = data[client.key] = {}
    servers[SERVER] = _entry(client, command)
    _write(client.path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def remove(client: Client) -> None:
    """Takes Pyzed's MCP server out of ``client``'s settings."""
    if client.format == "claude" and _claude_cli(["remove", "--scope", "user", SERVER]):
        return
    if client.format == "toml":
        if client.path.exists():
            _write(client.path, _TOML_TABLE.sub("", client.path.read_text(encoding="utf-8")))
        return
    data = _read_json(client.path)
    servers = data.get(client.key)
    if isinstance(servers, dict) and SERVER in servers:
        del servers[SERVER]
        _write(client.path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _claude_cli(args: List[str]) -> bool:
    """Runs ``claude mcp ...`` (Claude Code rewrites its own settings file, so it is the safe way); whether
    it worked."""
    claude = shutil.which("claude")
    if not claude:
        return False
    try:
        done = subprocess.run([claude, "mcp", *args], capture_output=True, timeout=60,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def install_missing(skip: List[str], home: Optional[Path] = None) -> "tuple[List[Client], Dict[str, str]]":
    """Adds the server to every installed agent that does not have it and is not in ``skip`` (agents already
    done, or that the user took it out of). Returns the agents it was added to, and why others failed."""
    added: List[Client] = []
    failed: Dict[str, str] = {}
    command = None
    for client in detected(home):
        if client.id in skip or status(client) != "missing":
            continue
        command = command or server_command()
        if not command:
            failed[client.id] = "uv is not installed"
            break
        try:
            install(client, command)
        except (OSError, ValueError) as err:
            failed[client.id] = str(err)
            continue
        added.append(client)
    return added, failed
