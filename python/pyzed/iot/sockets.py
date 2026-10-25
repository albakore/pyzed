"""UDP and TCP: the plain network messages of sensors, microcontrollers, OSC controllers and lab equipment."""

from __future__ import annotations

import json as _json
import socket
import struct
import threading
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from ..services import Handler, Service
from ._base import Connection, LineSplitter, bytes_of, text_of

__all__ = ["TcpClient", "UdpMessage", "UdpSocket"]


@dataclass(frozen=True)
class UdpMessage:
    """A datagram received: its bytes and who sent it."""

    data: bytes
    host: str
    port: int

    @property
    def text(self) -> str:
        return text_of(self.data)

    def json(self) -> Any:
        return _json.loads(self.data)

    @property
    def sender(self) -> Tuple[str, int]:
        return self.host, self.port


class UdpSocket(Service):
    """Sends and receives UDP datagrams: sensor broadcasts, OSC, Art-Net, WLED, many ESP8266/ESP32 sketches...

    ``start()`` listens on ``port`` (0: any free one, then ``port`` says which) of ``host``
    (``"0.0.0.0"``: every network). Each datagram raises ``message`` with a ``UdpMessage``
    (``data``, ``text``, ``json()``, ``host``, ``port``). ``send(data, host, port)`` sends
    one; without ``host`` it goes to ``remote_host``/``remote_port``. ``broadcast`` allows
    sending to ``255.255.255.255`` and ``multicast_group`` joins a group (``239.x.x.x``)::

        udp = pz.UdpSocket(4210, on_message=lambda m: print(m.host, m.text))
        udp.start()
        udp.send("ping", "192.168.1.50", 4210)

    Events:
        ``on_message(value)``: Callable that receives each ``UdpMessage``.
        ``on_failed(value)``: Callable that receives why the socket could not listen or send.
    """

    events = ("message", "failed")

    def __init__(self, port: int = 0, *, host: str = "0.0.0.0", remote_host: str = "", remote_port: int = 0,
                 broadcast: bool = False, multicast_group: str = "", encoding: str = "utf-8",
                 on_message: Optional[Handler] = None, on_failed: Optional[Handler] = None) -> None:
        super().__init__(on_message=on_message, on_failed=on_failed)
        self.port = port
        self.host = host
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.broadcast = broadcast
        self.multicast_group = multicast_group
        self.encoding = encoding
        #: The last datagram received.
        self.last: Optional[UdpMessage] = None
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def running(self) -> bool:
        return self._sock is not None

    @running.setter
    def running(self, value: bool) -> None:
        if value and not self.running:
            self.start()
        elif not value:
            self.stop()

    def _socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if self.broadcast:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        return sock

    def start(self) -> bool:
        """Starts listening; returns ``False`` (and raises ``failed``) when the port is taken."""
        self.stop()
        sock = self._socket()
        try:
            sock.bind((self.host or "0.0.0.0", int(self.port or 0)))
            if self.multicast_group:
                request = struct.pack("4s4s", socket.inet_aton(self.multicast_group), socket.inet_aton("0.0.0.0"))
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, request)
        except OSError as error:
            sock.close()
            self.emit("failed", str(error))
            return False
        sock.settimeout(0.5)
        self.port = sock.getsockname()[1]
        self._sock = sock
        self._thread = threading.Thread(target=self._listen, args=(sock,), name="pyzed-udp", daemon=True)
        self._thread.start()
        return True

    def _listen(self, sock: socket.socket) -> None:
        while self._sock is sock:
            try:
                data, (host, port) = sock.recvfrom(65535)[:2]
            except socket.timeout:
                continue
            except OSError:
                break
            self.last = message = UdpMessage(data, host, port)
            self.emit("message", message)

    def stop(self) -> None:
        sock, self._sock = self._sock, None
        if sock is not None:
            sock.close()

    def send(self, data: Any, host: str = "", port: int = 0) -> bool:
        """Sends ``data`` (text, bytes, a number, or a dict or list as JSON) to ``host``:``port``."""
        host, port = host or self.remote_host, int(port or self.remote_port or self.port)
        if not host or not port or not self.enabled:
            self.emit("failed", "no address to send to")
            return False
        sock = self._sock
        own = sock is None
        try:
            if own:
                sock = self._socket()
            sock.sendto(bytes_of(data, self.encoding), (host, port))
        except OSError as error:
            self.emit("failed", str(error))
            return False
        finally:
            if own and sock is not None:
                sock.close()
        return True

    def reply(self, message: UdpMessage, data: Any) -> bool:
        """Answers whoever sent ``message``."""
        return self.send(data, message.host, message.port)


class TcpClient(Connection):
    """A TCP connection to a device or server: printers, PLCs, Telnet-style consoles, Tasmota, a raw socket...

    ``connect()`` opens ``host``:``port`` (with ``tls`` for an encrypted one). Every chunk
    received raises ``data`` and every complete line raises ``line``; ``write()`` sends and
    ``send_line()`` adds ``newline``. With ``reconnect`` (milliseconds) it connects again
    when the connection drops.

    Events:
        ``on_connected()``: The connection opened.
        ``on_disconnected()``: The connection closed.
        ``on_failed(value)``: Callable that receives why it could not connect or broke.
        ``on_data(value)``: Callable that receives each chunk of bytes received.
        ``on_line(value)``: Callable that receives each line received, as text.
    """

    events = ("connected", "disconnected", "failed", "data", "line")
    _thread_name = "pyzed-tcp"

    def __init__(self, host: str = "", port: int = 0, *, tls: bool = False, insecure: bool = False,
                 newline: str = "\n", encoding: str = "utf-8", timeout: float = 10, reconnect: float = 0,
                 on_connected: Optional[Handler] = None, on_disconnected: Optional[Handler] = None,
                 on_failed: Optional[Handler] = None, on_data: Optional[Handler] = None,
                 on_line: Optional[Handler] = None) -> None:
        super().__init__(reconnect=reconnect, on_connected=on_connected, on_disconnected=on_disconnected,
                         on_failed=on_failed, on_data=on_data, on_line=on_line)
        self.host = host
        self.port = port
        self.tls = tls
        self.insecure = insecure
        self.newline = newline
        self.encoding = encoding
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None
        self._lines = LineSplitter(newline, encoding)

    def _open(self) -> None:
        if not self.host or not self.port:
            raise OSError("no address to connect to")
        sock = socket.create_connection((self.host, int(self.port)), timeout=float(self.timeout))
        if self.tls:
            import ssl

            context = ssl.create_default_context()
            if self.insecure:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            sock = context.wrap_socket(sock, server_hostname=self.host)
        sock.settimeout(0.5)
        self._lines = LineSplitter(self.newline, self.encoding)
        self._sock = sock

    def _serve(self) -> None:
        while not self._stop.is_set():
            sock = self._sock
            if sock is None:
                return
            try:
                data = sock.recv(65536)
            except socket.timeout:
                continue
            if not data:
                return  # the other side closed it
            self.emit("data", data)
            if self.handles("line"):
                for line in self._lines.feed(data):
                    self.emit("line", line)

    def _close(self) -> None:
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def write(self, data: Any) -> bool:
        """Sends ``data`` (text, bytes, or a dict or list as JSON); returns ``False`` when it is not connected."""
        sock = self._sock
        if sock is None or not self.enabled:
            return False
        try:
            sock.sendall(bytes_of(data, self.encoding))
        except OSError as error:
            self._failed(error)
            return False
        return True

    def send_line(self, text: str = "") -> bool:
        return self.write(str(text) + (self.newline or "\n"))
