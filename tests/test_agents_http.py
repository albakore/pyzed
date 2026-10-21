"""Pyzed's local HTTP servers do not print a traceback when a client drops its connection (on Windows,
agents reset idle keep-alive connections: WinError 10054)."""

import json
import socket
import struct
import time
import urllib.request

from pyzed import agents
from pyzed.agents import _localhttp, mcp_host


def _reset(host):
    """Connects and closes with a reset (SO_LINGER 0), as Windows does with idle connections."""
    address, port = host.split(":")
    sock = socket.create_connection((address, int(port)))
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    sock.close()


def test_a_dropped_connection_is_not_printed(capsys, caplog):
    server = mcp_host.ToolServer(agents.Agent(tools=[]), name="pyzed_editor")
    try:
        request = urllib.request.Request(server.url, data=json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": "ping"}).encode(), headers={
            "Authorization": f"Bearer {server.token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=10) as answer:
            assert json.loads(answer.read())["result"] == {}
        for _ in range(3):
            _reset(server.host)
        time.sleep(0.3)
        with urllib.request.urlopen(request, timeout=10) as answer:  # still answering
            assert json.loads(answer.read())["id"] == 1
    finally:
        server.close()
    assert "Traceback" not in capsys.readouterr().err
    assert not [r for r in caplog.records if r.name == "pyzed.agents.http"]


def test_other_errors_go_to_the_log(caplog):
    server = _localhttp.HTTPServer(("127.0.0.1", 0), object)  # type: ignore[arg-type]
    try:
        try:
            raise ValueError("boom")
        except ValueError:
            server.handle_error(None, ("127.0.0.1", 1))
        try:
            raise ConnectionResetError(10054, "reset")
        except ConnectionResetError:
            server.handle_error(None, ("127.0.0.1", 1))
    finally:
        server.server_close()
    logged = [r for r in caplog.records if r.name == "pyzed.agents.http"]
    assert len(logged) == 1 and "boom" in str(logged[0].exc_info[1])
