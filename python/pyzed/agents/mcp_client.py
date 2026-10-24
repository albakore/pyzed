"""MCP servers as tools for agents: local servers (a program spoken to over stdin/stdout) and remote ones
(Streamable HTTP), with no MCP SDK needed.

    from pyzed import agents
    from pyzed.agents import mcp_client

    servers = mcp_client.Servers([agents.providers.MCPServerConfig("files", "npx",
                                  ["-y", "@modelcontextprotocol/server-filesystem", "."])])
    agent = agents.Agent(tools=servers.tools())
    ...
    servers.close()

Each MCP tool becomes an agent ``Tool`` named ``mcp_<server>_<tool>``. Tools the server does not mark
read-only (``readOnlyHint``) are ``writes=True``, so the agent asks before running them. Secret
environment variables (or HTTP headers, for remote servers) are kept in the system keychain with
``set_secrets`` and passed to the server when it starts; they never go in ``agents.json``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Sequence

from . import secrets as _secrets
from .agent import Image, Tool
from .providers import MCPServerConfig

#: The MCP version Pyzed speaks (servers answer with the one they use).
PROTOCOL_VERSION = "2025-06-18"
#: Seconds to wait for a server's answer.
TIMEOUT = 120.0


class MCPError(RuntimeError):
    """A server could not start, or refused a request."""


def secrets_name(server: str) -> str:
    """The keychain entry with a server's secret environment variables or headers."""
    return f"agents.mcp.{server}"


def get_secrets(server: str, store: Optional[_secrets.SecretStore] = None) -> Dict[str, str]:
    raw = (store or _secrets.store()).get(secrets_name(server))
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def set_secrets(server: str, values: Dict[str, str], store: Optional[_secrets.SecretStore] = None) -> bool:
    """Keeps ``values`` (environment variables of a local server, headers of a remote one) in the keychain."""
    store = store or _secrets.store()
    if not values:
        store.delete(secrets_name(server))
        return store.secure
    return store.set(secrets_name(server), json.dumps(values))


def _version() -> str:
    try:
        from .. import __version__

        return str(__version__)
    except Exception:  # noqa: BLE001
        return "0"


class _Pending:
    def __init__(self) -> None:
        self.done = threading.Event()
        self.result: Any = None
        self.error: Optional[Dict[str, Any]] = None


class JsonRpcProcess:
    """JSON-RPC 2.0 with a program over its stdin and stdout, one message per line (MCP's stdio
    transport, and ACP's). Requests the program sends are answered by ``on_request(method, params)``;
    notifications go to ``on_notify(method, params)``."""

    def __init__(self, command: str, args: Sequence[str] = (), *, env: Optional[Dict[str, str]] = None,
                 cwd: Optional[str] = None, on_request: Optional[Callable[[str, Any], Any]] = None,
                 on_notify: Optional[Callable[[str, Any], None]] = None) -> None:
        self.on_request = on_request
        self.on_notify = on_notify
        self._next = 0
        self._pending: Dict[int, _Pending] = {}
        self._lock = threading.Lock()
        self.stderr: List[str] = []
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        from .. import _platform

        # the user's shell PATH: npx and the like (and the node they run) are often only there
        environ = {**os.environ, "PATH": _platform.user_path(), **(env or {})}
        program = command if os.path.dirname(command) else (_platform.which(command) or command)
        try:
            self.process = subprocess.Popen(
                [program, *args], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=cwd or None, env=environ, creationflags=flags)
        except (OSError, ValueError) as err:
            raise MCPError(f"Could not start {command}: {err}") from err
        threading.Thread(target=self._read, daemon=True, name=f"pyzed-rpc-{command}").start()
        threading.Thread(target=self._read_stderr, daemon=True, name=f"pyzed-rpc-err-{command}").start()

    @property
    def alive(self) -> bool:
        return self.process.poll() is None

    def _write(self, message: Dict[str, Any]) -> None:
        data = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
        with self._lock:
            try:
                assert self.process.stdin is not None
                self.process.stdin.write(data)
                self.process.stdin.flush()
            except (OSError, ValueError) as err:
                raise MCPError(f"The program closed the connection{self._detail()}") from err

    def _detail(self) -> str:
        tail = " ".join(line.strip() for line in self.stderr[-3:] if line.strip())
        return f": {tail[:300]}" if tail else ""

    def request(self, method: str, params: Any = None, *, timeout: float = TIMEOUT) -> Any:
        with self._lock:
            self._next += 1
            ident = self._next
        pending = self._pending[ident] = _Pending()
        message: Dict[str, Any] = {"jsonrpc": "2.0", "id": ident, "method": method}
        if params is not None:
            message["params"] = params
        self._write(message)
        if not pending.done.wait(timeout):
            self._pending.pop(ident, None)
            raise MCPError(f"No answer to {method} after {timeout:.0f} s")
        if pending.error is not None:
            raise MCPError(str(pending.error.get("message") or pending.error))
        return pending.result

    def notify(self, method: str, params: Any = None) -> None:
        message: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self._write(message)

    def _read(self) -> None:
        assert self.process.stdout is not None
        for raw in self.process.stdout:
            try:
                message = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue  # a server that logs to stdout
            if isinstance(message, dict):
                self._handle(message)
        for pending in list(self._pending.values()):  # the program ended: fail what still waits
            pending.error = {"message": f"The program stopped{self._detail()}"}
            pending.done.set()

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        for raw in self.process.stderr:
            self.stderr.append(raw.decode("utf-8", "replace"))
            del self.stderr[:-50]

    def _handle(self, message: Dict[str, Any]) -> None:
        if "method" not in message:
            pending = self._pending.pop(message.get("id"), None) if isinstance(message.get("id"), int) else None
            if pending is not None:
                pending.result, pending.error = message.get("result"), message.get("error")
                pending.done.set()
            return
        method, params = str(message["method"]), message.get("params")
        if "id" not in message:
            if self.on_notify is not None:
                self.on_notify(method, params)
            return
        # a request from the program: answered in its own thread (it may wait on the user)
        threading.Thread(target=self._answer, args=(message["id"], method, params), daemon=True).start()

    def _answer(self, ident: Any, method: str, params: Any) -> None:
        try:
            if method == "ping":
                result: Any = {}
            elif self.on_request is None:
                raise LookupError(method)
            else:
                result = self.on_request(method, params)
            reply: Dict[str, Any] = {"jsonrpc": "2.0", "id": ident, "result": result}
        except LookupError:
            reply = {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": f"Unknown method {method}"}}
        except Exception as err:  # noqa: BLE001 - reported to the program
            reply = {"jsonrpc": "2.0", "id": ident, "error": {"code": -32000, "message": str(err)}}
        try:
            self._write(reply)
        except MCPError:
            pass

    def close(self) -> None:
        """Closes the program's input (it should exit), kills it if it does not, and on Windows ends what it started
        too: ``npx`` there is a ``cmd`` behind ``node`` and the agent's own MCP servers, which outlive it otherwise
        (and one running from Pyzed Design's folder keeps an update from replacing it)."""
        if self.alive:
            from .. import _platform

            started = _platform.descendants(self.process.pid)
            try:
                assert self.process.stdin is not None
                self.process.stdin.close()
                self.process.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired, ValueError):
                self.process.kill()
            _platform.stop(started)


class HttpTransport:
    """MCP's Streamable HTTP transport: each request is a POST answered with JSON or an event stream."""

    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None) -> None:
        self.url = url
        self.headers = dict(headers or {})
        self.session: Optional[str] = None
        self._next = 0

    def _post(self, message: Dict[str, Any], timeout: float) -> Any:
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                   "MCP-Protocol-Version": PROTOCOL_VERSION, **self.headers}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        request = urllib.request.Request(self.url, data=json.dumps(message).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                self.session = response.headers.get("Mcp-Session-Id") or self.session
                if "id" not in message:
                    return None
                if "text/event-stream" in (response.headers.get("Content-Type") or ""):
                    for raw in response:
                        line = raw.decode("utf-8", "replace").strip()
                        if not line.startswith("data:"):
                            continue
                        try:
                            data = json.loads(line[5:].strip())
                        except ValueError:
                            continue
                        if isinstance(data, dict) and data.get("id") == message["id"]:
                            return data
                    raise MCPError("The server closed the stream without an answer")
                return json.loads(response.read().decode() or "{}")
        except urllib.error.HTTPError as err:
            if err.code in (401, 403):
                raise MCPError(f"The server refused the credentials ({err.code}); check its headers") from err
            raise MCPError(f"The server answered {err.code}") from err
        except OSError as err:
            raise MCPError(f"Could not reach {self.url}: {getattr(err, 'reason', err)}") from err

    def request(self, method: str, params: Any = None, *, timeout: float = TIMEOUT) -> Any:
        self._next += 1
        message: Dict[str, Any] = {"jsonrpc": "2.0", "id": self._next, "method": method}
        if params is not None:
            message["params"] = params
        data = self._post(message, timeout)
        if isinstance(data, dict) and data.get("error"):
            raise MCPError(str(data["error"].get("message") or data["error"]))
        return (data or {}).get("result")

    def notify(self, method: str, params: Any = None) -> None:
        message: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self._post(message, 30)

    @property
    def alive(self) -> bool:
        return True

    def close(self) -> None:
        pass


class MCPClient:
    """One connected MCP server."""

    def __init__(self, config: MCPServerConfig, *, cwd: Optional[str] = None,
                 store: Optional[_secrets.SecretStore] = None) -> None:
        self.config = config
        hidden = get_secrets(config.name, store)
        if config.url:
            self.transport: Any = HttpTransport(config.url, hidden)
        elif config.command:
            self.transport = JsonRpcProcess(config.command, config.args, env=hidden, cwd=cwd)
        else:
            raise MCPError(f"{config.name} has no command or URL")
        try:
            info = self.transport.request("initialize", {
                "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                "clientInfo": {"name": "Pyzed", "version": _version()}}, timeout=60)
            self.transport.notify("notifications/initialized")
        except MCPError:
            self.transport.close()
            raise
        self.server_info: Dict[str, Any] = (info or {}).get("serverInfo") or {}
        self.instructions: str = str((info or {}).get("instructions") or "")

    def list_tools(self) -> List[Dict[str, Any]]:
        tools: List[Dict[str, Any]] = []
        cursor = None
        for _ in range(20):
            result = self.transport.request("tools/list", {"cursor": cursor} if cursor else {}) or {}
            tools += [t for t in result.get("tools") or [] if isinstance(t, dict) and t.get("name")]
            cursor = result.get("nextCursor")
            if not cursor:
                break
        return tools

    def call(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Runs a tool; returns its text, or text and images (``Image``). Raises when the tool failed."""
        result = self.transport.request("tools/call", {"name": name, "arguments": arguments}) or {}
        parts: List[Any] = []
        for item in result.get("content") or []:
            kind = item.get("type")
            if kind == "text":
                parts.append(str(item.get("text") or ""))
            elif kind == "image" and item.get("data"):
                import base64

                parts.append(Image(base64.b64decode(item["data"]), str(item.get("mimeType") or "")))
            elif kind == "resource":
                resource = item.get("resource") or {}
                parts.append(str(resource.get("text") or f"[resource {resource.get('uri', '')}]"))
            elif kind == "resource_link":
                parts.append(f"[{item.get('name') or 'resource'}: {item.get('uri', '')}]")
        if not parts and result.get("structuredContent") is not None:
            parts.append(json.dumps(result["structuredContent"], ensure_ascii=False))
        text = "\n".join(p for p in parts if isinstance(p, str))
        if result.get("isError"):
            raise RuntimeError(text or "the tool failed")
        images = [p for p in parts if isinstance(p, Image)]
        return [text, *images] if images else text

    def close(self) -> None:
        self.transport.close()


_UNSAFE = re.compile(r"[^A-Za-z0-9_-]+")


def tool_name(server: str, name: str) -> str:
    """The agent tool name of an MCP tool (letters, digits, ``_`` and ``-``, at most 64 characters)."""
    return _UNSAFE.sub("_", f"mcp_{server}_{name}")[:64]


def _schema(raw: Any) -> Dict[str, Any]:
    schema = dict(raw) if isinstance(raw, dict) else {}
    schema.setdefault("type", "object")
    schema.setdefault("properties", {})
    return schema


class Servers:
    """The MCP servers of the settings, started when their tools are first needed and kept running."""

    def __init__(self, configs: Sequence[MCPServerConfig] = (), *, cwd: Optional[str] = None,
                 store: Optional[_secrets.SecretStore] = None) -> None:
        self.configs = list(configs)
        self.cwd = cwd
        self.store = store
        self.clients: Dict[str, MCPClient] = {}
        #: server name -> why it did not start (shown in the settings)
        self.errors: Dict[str, str] = {}
        self._tools: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def update(self, configs: Sequence[MCPServerConfig]) -> None:
        """Uses ``configs`` from now on; servers that changed or were removed are stopped."""
        new = {c.name: c for c in configs}
        with self._lock:
            for name, client in list(self.clients.items()):
                if new.get(name) != client.config:
                    client.close()
                    del self.clients[name]
                    self._tools.pop(name, None)
            self.errors = {k: v for k, v in self.errors.items() if k in new}
            self.configs = list(configs)

    def start(self, name: str) -> MCPClient:
        with self._lock:
            client = self.clients.get(name)
            if client is not None and client.transport.alive:
                return client
            config = next((c for c in self.configs if c.name == name), None)
            if config is None:
                raise MCPError(f"No MCP server named {name}")
            try:
                client = MCPClient(config, cwd=self.cwd, store=self.store)
                self._tools[name] = client.list_tools()
            except MCPError as err:
                self.errors[name] = str(err)
                raise
            self.errors.pop(name, None)
            self.clients[name] = client
            return client

    def tool_specs(self, name: str) -> List[Dict[str, Any]]:
        """The tools of server ``name`` as it lists them (starting it if needed)."""
        self.start(name)
        return self._tools.get(name, [])

    def tools(self, on_error: Optional[Callable[[str, str], None]] = None) -> List[Tool]:
        """Agent tools for every enabled server; a server that fails is reported to ``on_error(name, why)``
        and skipped."""
        out: List[Tool] = []
        for config in self.configs:
            if not config.enabled:
                continue
            try:
                specs = self.tool_specs(config.name)
            except MCPError as err:
                if on_error is not None:
                    on_error(config.name, str(err))
                continue
            for spec in specs:
                out.append(self._tool(config.name, spec))
        return out

    def _tool(self, server: str, spec: Dict[str, Any]) -> Tool:
        name = str(spec["name"])
        hints = spec.get("annotations") or {}

        def run(**arguments: Any) -> Any:
            return self.start(server).call(name, arguments)

        title = str(hints.get("title") or spec.get("title") or name)
        return Tool(tool_name(server, name), f"[{server}] {spec.get('description') or name}",
                    _schema(spec.get("inputSchema")), run, writes=not hints.get("readOnlyHint", False),
                    title=f"{server}: {title}")

    def close(self) -> None:
        with self._lock:
            for client in self.clients.values():
                client.close()
            self.clients.clear()
            self._tools.clear()
