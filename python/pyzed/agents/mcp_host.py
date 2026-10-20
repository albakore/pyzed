"""Pyzed's own tools served to other agents over MCP: the designer hands its tools (the open form, its
code, the project, Pyzed's knowledge) to an external agent such as Claude Code, so it controls the editor
like the built-in agent does.

    from pyzed import agents
    from pyzed.agents import mcp_host

    server = mcp_host.ToolServer(agents.Agent(tools=[...]), name="pyzed_editor")
    server.acp_entry()   # the ``mcpServers`` entry of an ACP session (Streamable HTTP)
    ...
    server.close()

The server listens on ``127.0.0.1`` at a random port and path and wants a bearer token, so only the
agent it was handed to can call it. Agents that only start local servers get ``bridge_entry()``: a small
program (``python -m pyzed.agents.mcp_host URL``) that relays stdin/stdout to it.
"""

from __future__ import annotations

import http.server
import json
import os
import secrets as _random
import sys
import threading
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .agent import Agent

#: The MCP versions this server answers with (the client's when it is one of these).
VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")


def mcp_content(result: Dict[str, Any]) -> Dict[str, Any]:
    """An agent's ``tool_result`` block as the result of MCP's ``tools/call``."""
    content = result.get("content")
    blocks: List[Dict[str, Any]] = []
    for part in content if isinstance(content, list) else [{"type": "text", "text": str(content or "")}]:
        if part.get("type") == "text":
            blocks.append({"type": "text", "text": str(part.get("text") or "")})
        elif part.get("type") == "image":
            source = part.get("source") or {}
            blocks.append({"type": "image", "data": source.get("data", ""),
                           "mimeType": source.get("media_type", "image/png")})
    return {"content": blocks, "isError": bool(result.get("is_error"))}


class ToolServer:
    """An agent's tools served over MCP's Streamable HTTP on ``127.0.0.1`` (answers as plain JSON)."""

    def __init__(self, agent: Agent, *, name: str = "pyzed_editor", instructions: str = "") -> None:
        self.agent = agent
        self.name = name
        self.instructions = instructions
        self.token = _random.token_urlsafe(24)
        self.path = f"/mcp/{_random.token_urlsafe(12)}"
        server = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            timeout = 30

            def _reply(self, status: int, body: Optional[Dict[str, Any]] = None) -> None:
                data = json.dumps(body).encode() if body is not None else b""
                self.send_response(status)
                if body is not None:
                    self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _allowed(self) -> bool:
                # its own address only (no DNS rebinding, no web page), with the token it was handed
                origin = self.headers.get("Origin")
                return (self.path == server.path and self.headers.get("Host") == server.host
                        and self.headers.get("Authorization") == f"Bearer {server.token}"
                        and (origin is None or origin == f"http://{server.host}"))

            def do_POST(self) -> None:  # noqa: N802 - http.server API
                if not self._allowed():
                    return self._reply(404)
                length = int(self.headers.get("Content-Length") or 0)
                try:
                    message = json.loads(self.rfile.read(length) or b"null")
                except ValueError:
                    return self._reply(400, {"jsonrpc": "2.0", "id": None,
                                             "error": {"code": -32700, "message": "Parse error"}})
                if isinstance(message, list):
                    answers = [a for a in (server.handle(m) for m in message) if a is not None]
                    return self._reply(200, answers) if answers else self._reply(202)  # type: ignore[arg-type]
                answer = server.handle(message)
                self._reply(202) if answer is None else self._reply(200, answer)

            def do_GET(self) -> None:  # noqa: N802 - no server-to-client stream
                self._reply(405 if self._allowed() else 404)

            def do_DELETE(self) -> None:  # noqa: N802
                self._reply(405 if self._allowed() else 404)

            def log_message(self, *args: Any) -> None:
                pass

        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._httpd.daemon_threads = True
        self.host = f"127.0.0.1:{self._httpd.server_address[1]}"
        self.url = f"http://{self.host}{self.path}"
        threading.Thread(target=self._httpd.serve_forever, daemon=True, name=f"pyzed-mcp-{name}").start()

    # -- MCP --------------------------------------------------------------------------------------
    def handle(self, message: Any) -> Optional[Dict[str, Any]]:
        """Answers one JSON-RPC message (``None`` for a notification)."""
        if not isinstance(message, dict) or "method" not in message:
            return None
        ident, method, params = message.get("id"), message["method"], message.get("params") or {}
        if ident is None:
            return None
        try:
            result = self._result(method, params if isinstance(params, dict) else {})
        except LookupError as err:
            return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": str(err)}}
        except Exception as err:  # noqa: BLE001 - reported to the agent
            return {"jsonrpc": "2.0", "id": ident, "error": {"code": -32603, "message": str(err)}}
        return {"jsonrpc": "2.0", "id": ident, "result": result}

    def _result(self, method: str, params: Dict[str, Any]) -> Any:
        if method == "initialize":
            from .mcp_client import _version

            asked = params.get("protocolVersion")
            info = {"protocolVersion": asked if asked in VERSIONS else VERSIONS[0],
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": self.name, "version": _version()}}
            if self.instructions:
                info["instructions"] = self.instructions
            return info
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": [{"name": t.name, "description": t.description, "inputSchema": t.schema,
                               **({"title": t.title} if t.title else {}),
                               "annotations": {"readOnlyHint": not t.writes}}
                              for t in self.agent.active_tools()]}
        if method == "tools/call":
            name, args = str(params.get("name") or ""), params.get("arguments") or {}
            return mcp_content(self.agent.call_tool(name, args if isinstance(args, dict) else {}))
        raise LookupError(f"Unknown method {method}")

    # -- handing it to an agent -------------------------------------------------------------------
    def acp_entry(self) -> Dict[str, Any]:
        """The server as an ACP ``mcpServers`` entry (Streamable HTTP, with its token)."""
        return {"type": "http", "name": self.name, "url": self.url,
                "headers": [{"name": "Authorization", "value": f"Bearer {self.token}"}]}

    def bridge_entry(self) -> Optional[Dict[str, Any]]:
        """The server as a local (stdio) ACP entry, for agents without HTTP servers (``None`` in a frozen app)."""
        if getattr(sys, "frozen", False):
            return None
        return {"name": self.name, "command": sys.executable, "args": ["-m", "pyzed.agents.mcp_host", self.url],
                "env": [{"name": "PYZED_MCP_TOKEN", "value": self.token}]}

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


def bridge(url: str, token: str, stdin: Any = None, stdout: Any = None) -> None:
    """Relays newline-delimited JSON-RPC from ``stdin`` to the server at ``url`` and its answers to ``stdout``."""
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for line in stdin:
        if not line.strip():
            continue
        request = urllib.request.Request(url, data=line.encode(), method="POST", headers={
            "Content-Type": "application/json", "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {token}"})
        try:
            with opener.open(request, timeout=3600) as response:
                body = response.read()
        except (urllib.error.URLError, OSError) as err:
            try:
                ident = json.loads(line).get("id")
            except (ValueError, AttributeError):
                ident = None
            if ident is None:
                continue
            body = json.dumps({"jsonrpc": "2.0", "id": ident,
                               "error": {"code": -32603, "message": f"Pyzed Design is not reachable: {err}"}}).encode()
        if body.strip():
            stdout.write(body.decode() + "\n")
            stdout.flush()


if __name__ == "__main__":
    bridge(sys.argv[1], os.environ.get("PYZED_MCP_TOKEN", ""))
