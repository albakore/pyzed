"""WebSocket: a two-way connection to a server or a device (ESP32, OctoPrint, Home Assistant...), RFC 6455."""

from __future__ import annotations

import base64
import hashlib
import json as _json
import os
import socket
import struct
import threading
import time
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple, Union
from urllib.parse import urlsplit

from ..services import Handler
from ._base import Connection, bytes_of

__all__ = ["WebSocket", "WebSocketError"]

_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
CONT, TEXT, BINARY, CLOSE, PING, PONG = 0x0, 0x1, 0x2, 0x8, 0x9, 0xA


class WebSocketError(OSError):
    """The server refused the connection or broke the protocol."""


def accept_key(key: str) -> str:
    """The ``Sec-WebSocket-Accept`` a server answers to ``key``."""
    return base64.b64encode(hashlib.sha1((key + _GUID).encode()).digest()).decode()


def frame(opcode: int, payload: bytes = b"", *, mask: bool = True, fin: bool = True) -> bytes:
    """One WebSocket frame (clients mask theirs)."""
    head = bytearray([(0x80 if fin else 0) | opcode])
    size = len(payload)
    bit = 0x80 if mask else 0
    if size < 126:
        head.append(bit | size)
    elif size < 1 << 16:
        head += bytes([bit | 126]) + struct.pack("!H", size)
    else:
        head += bytes([bit | 127]) + struct.pack("!Q", size)
    if not mask:
        return bytes(head) + payload
    key = os.urandom(4)
    return bytes(head) + key + bytes(b ^ key[i % 4] for i, b in enumerate(payload))


class WebSocket(Connection):
    """A WebSocket client: ``send()`` text, bytes or JSON, and every message received raises ``message``.

    ``url`` is a ``ws://`` or ``wss://`` address. Text messages arrive as ``str`` and binary
    ones as ``bytes``; with ``json=True`` text messages are parsed as JSON first (falling
    back to the text). ``headers`` go with the handshake (a token...), ``protocols`` names
    the subprotocols to offer. A ping goes every ``ping_interval`` milliseconds to keep the
    connection open through routers::

        socket = pz.WebSocket("ws://esp32.local/ws", json=True, on_message=self.reading)
        socket.connect()
        socket.send({"led": True})

    Events:
        ``on_connected()``: The server accepted the connection.
        ``on_disconnected()``: The connection closed.
        ``on_failed(value)``: Callable that receives why the connection could not be made or broke.
        ``on_message(value)``: Callable that receives each message (``str``, ``bytes`` or, with ``json``, the data).
    """

    events = ("connected", "disconnected", "failed", "message")
    _thread_name = "pyzed-websocket"

    def __init__(self, url: str = "", *, headers: Union[str, Mapping[str, str], None] = None,
                 protocols: Union[str, Sequence[str], None] = None, json: bool = False, ping_interval: float = 20000,
                 timeout: float = 10, insecure: bool = False, reconnect: float = 0,
                 on_connected: Optional[Handler] = None, on_disconnected: Optional[Handler] = None,
                 on_failed: Optional[Handler] = None, on_message: Optional[Handler] = None) -> None:
        super().__init__(reconnect=reconnect, on_connected=on_connected, on_disconnected=on_disconnected,
                         on_failed=on_failed, on_message=on_message)
        self.url = url
        self.headers = headers
        self.protocols = protocols
        self.json = json
        self.ping_interval = ping_interval
        self.timeout = timeout
        #: With ``wss://``, accept any certificate (a device with a self-signed one).
        self.insecure = insecure
        #: The subprotocol the server chose (``""`` when none).
        self.protocol = ""
        #: The last message received.
        self.last: Any = None
        self._sock: Optional[socket.socket] = None
        self._send_lock = threading.Lock()
        self._buffer = b""

    # -- the handshake -----------------------------------------------------------------------------------------
    def _open(self) -> None:
        from ..services import _headers

        parts = urlsplit(self.url)
        if parts.scheme not in ("ws", "wss", "http", "https"):
            raise WebSocketError(f"a WebSocket address starts with ws:// or wss://, not {self.url!r}")
        secure = parts.scheme in ("wss", "https")
        host = parts.hostname or "localhost"
        port = parts.port or (443 if secure else 80)
        sock = socket.create_connection((host, port), timeout=float(self.timeout))
        if secure:
            import ssl

            context = ssl.create_default_context()
            if self.insecure:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            sock = context.wrap_socket(sock, server_hostname=host)
        self._sock, self._buffer = sock, b""
        key = base64.b64encode(os.urandom(16)).decode()
        path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
        lines = [f"GET {path} HTTP/1.1", f"Host: {parts.netloc.rsplit('@', 1)[-1]}", "Upgrade: websocket",
                 "Connection: Upgrade", f"Sec-WebSocket-Key: {key}", "Sec-WebSocket-Version: 13",
                 "User-Agent: Pyzed"]
        if parts.username:
            auth = f"{parts.username}:{parts.password or ''}".encode()
            lines.append(f"Authorization: Basic {base64.b64encode(auth).decode()}")
        protocols = self.protocols.split(",") if isinstance(self.protocols, str) else list(self.protocols or ())
        protocols = [p.strip() for p in protocols if p.strip()]
        if protocols:
            lines.append(f"Sec-WebSocket-Protocol: {', '.join(protocols)}")
        lines += [f"{k}: {v}" for k, v in _headers(self.headers).items()]
        sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
        while b"\r\n\r\n" not in self._buffer:
            chunk = sock.recv(4096)
            if not chunk:
                raise WebSocketError("the server closed the connection during the handshake")
            self._buffer += chunk
            if len(self._buffer) > 65536:
                raise WebSocketError("the server's answer is too long")
        head, self._buffer = self._buffer.split(b"\r\n\r\n", 1)
        status, *fields = head.decode("latin-1").split("\r\n")
        answer: Dict[str, str] = {}
        for field in fields:
            name, _, value = field.partition(":")
            answer[name.strip().lower()] = value.strip()
        if " 101" not in status:
            raise WebSocketError(f"the server did not accept the WebSocket: {status.partition(' ')[2] or status}")
        if answer.get("sec-websocket-accept") != accept_key(key):
            raise WebSocketError("the server answered the handshake wrongly")
        self.protocol = answer.get("sec-websocket-protocol", "")
        sock.settimeout(0.5)

    def _close(self) -> None:
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                if self._stop.is_set():
                    with self._send_lock:
                        sock.sendall(frame(CLOSE, struct.pack("!H", 1000)))
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    # -- reading -----------------------------------------------------------------------------------------------
    def _recv(self, size: int, idle: bool = False) -> bytes:
        while len(self._buffer) < size:
            sock = self._sock
            if sock is None or self._stop.is_set():
                raise WebSocketError("closed")
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                if idle and not self._buffer:
                    raise
                continue
            if not chunk:
                raise WebSocketError("the server closed the connection")
            self._buffer += chunk
        out, self._buffer = self._buffer[:size], self._buffer[size:]
        return out

    def _read_frame(self) -> Tuple[bool, int, bytes]:
        first, second = self._recv(2, idle=True)
        size = second & 0x7F
        if size == 126:
            size = struct.unpack("!H", self._recv(2))[0]
        elif size == 127:
            size = struct.unpack("!Q", self._recv(8))[0]
        key = self._recv(4) if second & 0x80 else b""
        data = self._recv(size) if size else b""
        if key:
            data = bytes(b ^ key[i % 4] for i, b in enumerate(data))
        return bool(first & 0x80), first & 0x0F, data

    def _serve(self) -> None:
        pieces, kind, last_ping = [], TEXT, time.monotonic()
        while not self._stop.is_set():
            try:
                fin, opcode, data = self._read_frame()
            except socket.timeout:
                interval = float(self.ping_interval or 0) / 1000
                if interval > 0 and time.monotonic() - last_ping > interval:
                    last_ping = time.monotonic()
                    self._send_frame(PING, b"pyzed")
                continue
            if opcode == PING:
                self._send_frame(PONG, data)
            elif opcode == CLOSE:
                code = struct.unpack("!H", data[:2])[0] if len(data) >= 2 else 1005
                try:
                    self._send_frame(CLOSE, data[:2])
                except OSError:
                    pass
                if code not in (1000, 1001, 1005):
                    reason = data[2:].decode("utf-8", "replace")
                    raise WebSocketError(f"the server closed the connection ({code}{': ' + reason if reason else ''})")
                return
            elif opcode in (TEXT, BINARY, CONT):
                if opcode != CONT:
                    pieces, kind = [], opcode
                pieces.append(data)
                if fin:
                    self._message(kind, b"".join(pieces))
                    pieces = []

    def _message(self, kind: int, data: bytes) -> None:
        value: Any = data
        if kind == TEXT:
            value = data.decode("utf-8", "replace")
            if self.json:
                try:
                    value = _json.loads(value)
                except ValueError:
                    pass
        self.last = value
        self.emit("message", value)

    # -- sending -----------------------------------------------------------------------------------------------
    def _send_frame(self, opcode: int, payload: bytes) -> None:
        sock = self._sock
        if sock is None:
            raise WebSocketError("not connected")
        with self._send_lock:
            sock.sendall(frame(opcode, payload))

    def send(self, data: Any) -> bool:
        """Sends text, bytes, or a dict or list as JSON; returns ``False`` when it is not connected."""
        if not self.connected or not self.enabled:
            return False
        if isinstance(data, (bytes, bytearray, memoryview)):
            opcode, payload = BINARY, bytes(data)
        else:  # text; numbers as their text, dicts and lists as JSON
            opcode, payload = TEXT, bytes_of(data)
        try:
            self._send_frame(opcode, payload)
        except OSError as error:
            self._failed(error)
            return False
        return True
