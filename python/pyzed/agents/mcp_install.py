"""Pyzed's MCP server in the AI agents of this computer: Claude Code, Claude Desktop, Cursor, Windsurf, Gemini
CLI, Codex, VS Code and Zed. Pyzed Design finds the ones installed and adds the server to their settings
(once each, Settings → AI agents lists them), so they know Pyzed's components, docs and checks; each agent
reads it the next time it starts.

    from pyzed.agents import mcp_install

    for client in mcp_install.detected():
        if mcp_install.status(client) == "missing":
            mcp_install.install(client)

Only the ``pyzed`` entry is touched: the rest of each settings file is kept as it was (comments included,
as Zed's and VS Code's settings have them), and a copy of the file is left next to it (``.pyzed-backup``)
before the first change.
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

from .. import _platform

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
    return [c for c in clients(home) if c.marker.is_dir() or (c.program and _platform.which(c.program))]


def server_command() -> Optional[List[str]]:
    """How an agent starts Pyzed's MCP server: ``uvx`` with the published package (always there, whatever
    project is open), Pyzed Design's own ``uv``, else this Python when it has the MCP SDK; ``None`` when none
    of them can."""
    uvx = _platform.which("uvx")
    if uvx:
        return [uvx, "--no-build-package", "pyzed-ui", "--from", PACKAGE, "pyzed", "mcp"]
    from ..project import find_uv

    uv = find_uv()
    if uv:
        return [uv, "tool", "run", "--no-build-package", "pyzed-ui", "--from", PACKAGE, "pyzed", "mcp"]
    if not getattr(sys, "frozen", False):
        try:
            import mcp  # noqa: F401
        except ImportError:
            return None
        return [sys.executable, "-m", "pyzed", "mcp"]
    return None


def _entry(client: Client, command: List[str]) -> Dict[str, Any]:
    entry: Dict[str, Any] = {"command": command[0], "args": command[1:]}
    if client.key == "servers":
        return {"type": "stdio", **entry}
    if client.key == "context_servers":  # Zed
        return {"source": "custom", **entry, "env": {}}
    return entry


# -- JSON with comments (Zed's and VS Code's settings) ---------------------------------------------------

def _skip(text: str, i: int) -> int:
    """The index of the next character that is not white space or a comment."""
    while i < len(text):
        if text[i].isspace():
            i += 1
        elif text.startswith("//", i):
            end = text.find("\n", i)
            i = len(text) if end < 0 else end + 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = len(text) if end < 0 else end + 2
        else:
            break
    return i


def _string_end(text: str, i: int) -> int:
    i += 1
    while i < len(text) and text[i] != '"':
        i += 2 if text[i] == "\\" else 1
    if i >= len(text):
        raise ValueError("a string is not closed")
    return i + 1


def _value_end(text: str, i: int) -> int:
    """The index just past the JSON value that starts at ``i``."""
    if text[i] == '"':
        return _string_end(text, i)
    if text[i] in "{[":
        depth = 0
        while i < len(text):
            i = _skip(text, i)
            if i >= len(text):
                break
            ch = text[i]
            if ch == '"':
                i = _string_end(text, i)
                continue
            if ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        raise ValueError("an object or list is not closed")
    end = i
    while end < len(text) and text[end] not in ",}] \t\r\n/":
        end += 1
    return end


def _members(text: str, start: int) -> "tuple[List[tuple[str, int, int, int]], int]":
    """The members of the object whose ``{`` is at ``start``: ``(key, key start, value start, value end)``, and
    the index of its ``}``."""
    out = []
    i = _skip(text, start + 1)
    while i < len(text) and text[i] != "}":
        if text[i] == ",":
            i = _skip(text, i + 1)
            continue
        if text[i] != '"':
            raise ValueError(f"unexpected {text[i]!r} in an object")
        key_end = _string_end(text, i)
        key = json.loads(text[i:key_end])
        colon = _skip(text, key_end)
        if colon >= len(text) or text[colon] != ":":
            raise ValueError("expected ':'")
        value = _skip(text, colon + 1)
        end = _value_end(text, value)
        out.append((key, i, value, end))
        i = _skip(text, end)
    if i >= len(text):
        raise ValueError("an object is not closed")
    return out, i


def _loads(text: str) -> Any:
    """JSON that may have comments and trailing commas."""
    out, i = [], 0
    while i < len(text):
        nxt = _skip(text, i)
        if nxt != i:
            out.append(" ")
            i = nxt
            continue
        if text[i] == '"':
            end = _string_end(text, i)
            out.append(text[i:end])
            i = end
            continue
        if text[i] == ",":
            after = _skip(text, i + 1)
            if after < len(text) and text[after] in "}]":  # a trailing comma
                i += 1
                continue
        out.append(text[i])
        i += 1
    return json.loads("".join(out))


def _indent_at(text: str, i: int) -> str:
    line = text.rfind("\n", 0, i) + 1
    head = text[line:i]
    return head if not head.strip() else ""


def _set_member(text: str, path: List[str], value: Any) -> str:
    """``text`` (a JSON object, comments allowed) with ``value`` at ``path``, keeping everything else as it was."""
    start = _skip(text, 0)
    if start >= len(text) or text[start] != "{":
        raise ValueError("the settings do not hold a JSON object")
    for depth, key in enumerate(path):
        members, close = _members(text, start)
        found = next((m for m in members if m[0] == key), None)
        rest = path[depth + 1:]
        if found is not None and (not rest or text[found[2]] != "{"):
            nested: Any = value
            for name in reversed(rest):
                nested = {name: nested}
            indent = _indent_at(text, found[1])
            dumped = json.dumps(nested, indent=2, ensure_ascii=False).replace("\n", "\n" + indent)
            return text[:found[2]] + dumped + text[found[3]:]
        if found is not None:
            start = found[2]
            continue
        nested = value
        for name in reversed(rest):
            nested = {name: nested}
        outer = _indent_at(text, start) if depth else ""
        indent = _indent_at(text, members[0][1]) if members else outer + "  "
        dumped = json.dumps(nested, indent=2, ensure_ascii=False).replace("\n", "\n" + indent)
        member = f"{json.dumps(key)}: {dumped}"
        if members:
            return text[:start + 1] + f"\n{indent}{member}," + text[start + 1:]
        return text[:start] + f"{{\n{indent}{member}\n{outer}}}" + text[close + 1:]
    return text


def _remove_member(text: str, path: List[str]) -> str:
    """``text`` without the member at ``path`` (unchanged when it is not there)."""
    start = _skip(text, 0)
    for depth, key in enumerate(path):
        if start >= len(text) or text[start] != "{":
            return text
        members, close = _members(text, start)
        index = next((n for n, m in enumerate(members) if m[0] == key), None)
        if index is None:
            return text
        _, key_start, value_start, value_end = members[index]
        if depth < len(path) - 1:
            start = value_start
            continue
        after = _skip(text, value_end)
        if after < len(text) and text[after] == ",":  # "key": value, -> gone with its comma and line
            begin = key_start - len(_indent_at(text, key_start))
            end = after + 1
            if text.startswith("\n", end):
                end += 1
            elif text.startswith("\r\n", end):
                end += 2
            return text[:begin] + text[end:]
        if index:  # the last member: the comma after the one before goes too
            return text[:members[index - 1][3]] + text[value_end:]
        return text[:start] + "{}" + text[close + 1:]  # the only member
    return text


def _read_json(path: Path) -> Dict[str, Any]:
    """A settings file as a dict (``{}`` when it does not exist); comments and trailing commas are allowed.
    Raises ``ValueError`` when it does not hold a JSON object."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    if not text.strip():
        return {}
    data = _loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not hold a JSON object")
    return data


def _plain_json(path: Path) -> bool:
    """Whether the settings file is missing, empty or plain JSON (rewritten as a whole when changed)."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return True
    if not text.strip():
        return True
    try:
        json.loads(text)
    except ValueError:
        return False
    return True


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
    """``"installed"`` (the agent has a ``pyzed`` server), ``"missing"`` or ``"unreadable"`` (its settings
    file is broken, so Pyzed does not change it)."""
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
    if not _plain_json(client.path):  # with comments: only the server's lines change
        text = client.path.read_text(encoding="utf-8")
        _read_json(client.path)  # raises when it is not a JSON object
        _write(client.path, _set_member(text, [client.key, SERVER], _entry(client, command)))
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
    if not _plain_json(client.path):
        _write(client.path, _remove_member(client.path.read_text(encoding="utf-8"), [client.key, SERVER]))
        return
    data = _read_json(client.path)
    servers = data.get(client.key)
    if isinstance(servers, dict) and SERVER in servers:
        del servers[SERVER]
        _write(client.path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _claude_cli(args: List[str]) -> bool:
    """Runs ``claude mcp ...`` (Claude Code rewrites its own settings file, so it is the safe way); whether
    it worked."""
    claude = _platform.which("claude")
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
