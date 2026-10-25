"""Stand-ins for devices and servers, to try an IoT app without hardware: tests, demos and screenshots.

They run on this computer in threads of their own and are small on purpose: they speak just
enough of each protocol for Pyzed's clients and for trying an app. Use a real broker or
server (Mosquitto, a PLC...) in production::

    from pyzed.iot.testing import MqttBroker

    with MqttBroker() as broker:                    # localhost, a free port
        client = pz.MqttClient("127.0.0.1", broker.port, subscribe="sensors/#")
        ...
        broker.publish("sensors/temperature", "21.5")

==========================  ================================================================
``MqttBroker``              An MQTT 3.1.1 broker: QoS 0, 1 and 2, retained messages, logins.
``WebSocketServer``         A WebSocket server that answers each message (echo by default).
``ModbusServer``            A Modbus TCP server with coils and registers you set.
``FakeNetwork``             Devices that answer mDNS and SSDP, for ``DeviceDiscovery``.
``serial_pair()``           Two ends of a virtual serial cable (Linux and macOS).
==========================  ================================================================
"""

from __future__ import annotations

import base64
import hashlib
import os
import select
import socket
import struct
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from .discovery import Device, _encode_name, _read_name
from .modbus import crc16
from .mqtt import (CONNACK, CONNECT, DISCONNECT, PINGREQ, PINGRESP, PUBACK, PUBCOMP, PUBLISH, PUBREC, PUBREL,
                   SUBACK, SUBSCRIBE, UNSUBACK, UNSUBSCRIBE, _packet, _string, topic_matches)
from .websocket import BINARY, CLOSE, PING, PONG, TEXT, frame

__all__ = ["FakeNetwork", "ModbusServer", "MqttBroker", "WebSocketServer", "modbus_rtu_device", "serial_pair"]


class _Server:
    """A TCP server on ``host``:``port`` (0: a free one) that runs ``_client(sock)`` per connection."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind((host, port))
        self._listener.listen(16)
        self.host, self.port = self._listener.getsockname()[:2]
        self._clients: List[socket.socket] = []
        self._running = True
        threading.Thread(target=self._accept, name=f"pyzed-{type(self).__name__}", daemon=True).start()

    def _accept(self) -> None:
        while self._running:
            try:
                sock, _ = self._listener.accept()
            except OSError:
                return
            self._clients.append(sock)
            threading.Thread(target=self._guard, args=(sock,), daemon=True).start()

    def _guard(self, sock: socket.socket) -> None:
        try:
            self._client(sock)
        except (OSError, ValueError, struct.error, IndexError):
            pass
        finally:
            self._drop(sock)

    def _drop(self, sock: socket.socket) -> None:
        if sock in self._clients:
            self._clients.remove(sock)
        try:
            sock.close()
        except OSError:
            pass

    def _client(self, sock: socket.socket) -> None:
        raise NotImplementedError

    def kick(self) -> None:
        """Drops every connection (as a server that restarts would)."""
        for sock in list(self._clients):
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._drop(sock)

    def close(self) -> None:
        self._running = False
        self._listener.close()
        self.kick()

    def __enter__(self) -> Any:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _recv(sock: socket.socket, size: int) -> bytes:
    out = b""
    while len(out) < size:
        chunk = sock.recv(size - len(out))
        if not chunk:
            raise OSError("closed")
        out += chunk
    return out


# -- MQTT -----------------------------------------------------------------------------------------------------------
class MqttBroker(_Server):
    """A small MQTT 3.1.1 broker. ``users`` (``{"name": "password"}``) makes it ask for a login.

    ``received`` lists every ``(topic, payload)`` published to it; ``publish()`` sends a
    message to the subscribers as if a device had published it.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 0, *, users: Optional[Dict[str, str]] = None) -> None:
        self.users = users
        self.received: List[Tuple[str, bytes]] = []
        self.retained: Dict[str, Tuple[bytes, int]] = {}
        self.clients: Dict[str, socket.socket] = {}
        self._subs: Dict[socket.socket, Dict[str, int]] = {}
        self._wills: Dict[socket.socket, Tuple[str, bytes, int, bool]] = {}
        self._locks: Dict[socket.socket, threading.Lock] = {}
        self._ids = 0
        super().__init__(host, port)

    def _send(self, sock: socket.socket, packet: bytes) -> None:
        with self._locks.setdefault(sock, threading.Lock()):
            sock.sendall(packet)

    def _read(self, sock: socket.socket) -> Tuple[int, int, bytes]:
        first = _recv(sock, 1)[0]
        length, shift = 0, 0
        while True:
            byte = _recv(sock, 1)[0]
            length |= (byte & 127) << shift
            shift += 7
            if not byte & 128:
                break
        return first >> 4, first & 15, _recv(sock, length) if length else b""

    def _client(self, sock: socket.socket) -> None:
        kind, _, data = self._read(sock)
        if kind != CONNECT:
            return
        flags, offset = data[7], 10
        size = struct.unpack("!H", data[offset:offset + 2])[0]
        client_id = data[offset + 2:offset + 2 + size].decode()
        offset += 2 + size
        if flags & 0x04:
            size = struct.unpack("!H", data[offset:offset + 2])[0]
            will_topic = data[offset + 2:offset + 2 + size].decode()
            offset += 2 + size
            size = struct.unpack("!H", data[offset:offset + 2])[0]
            self._wills[sock] = (will_topic, data[offset + 2:offset + 2 + size], (flags >> 3) & 3, bool(flags & 0x20))
            offset += 2 + size
        user = password = ""
        if flags & 0x80:
            size = struct.unpack("!H", data[offset:offset + 2])[0]
            user = data[offset + 2:offset + 2 + size].decode()
            offset += 2 + size
        if flags & 0x40:
            size = struct.unpack("!H", data[offset:offset + 2])[0]
            password = data[offset + 2:offset + 2 + size].decode()
        if self.users is not None and self.users.get(user) != password:
            self._send(sock, _packet(CONNACK, 0, b"\0\x04"))
            return
        self._send(sock, _packet(CONNACK, 0, b"\0\0"))
        self.clients[client_id] = sock
        self._subs[sock] = {}
        clean = False
        incoming: Dict[int, Tuple[str, bytes, bool]] = {}
        try:
            while True:
                kind, flags, data = self._read(sock)
                if kind == PUBLISH:
                    qos, retain = (flags >> 1) & 3, bool(flags & 1)
                    size = struct.unpack("!H", data[:2])[0]
                    topic, rest = data[2:2 + size].decode(), data[2 + size:]
                    if qos:
                        packet_id, rest = struct.unpack("!H", rest[:2])[0], rest[2:]
                        if qos == 1:
                            self._send(sock, _packet(PUBACK, 0, struct.pack("!H", packet_id)))
                        else:
                            incoming[packet_id] = (topic, rest, retain)
                            self._send(sock, _packet(PUBREC, 0, struct.pack("!H", packet_id)))
                            continue
                    self.publish(topic, rest, qos, retain)
                elif kind == PUBREL:
                    packet_id = struct.unpack("!H", data[:2])[0]
                    self._send(sock, _packet(PUBCOMP, 0, data[:2]))
                    if packet_id in incoming:
                        topic, payload, retain = incoming.pop(packet_id)
                        self.publish(topic, payload, 2, retain)
                elif kind == PUBREC:
                    self._send(sock, _packet(PUBREL, 2, data[:2]))
                elif kind == SUBSCRIBE:
                    packet_id, offset, codes, topics = data[:2], 2, b"", []
                    while offset < len(data):
                        size = struct.unpack("!H", data[offset:offset + 2])[0]
                        topic = data[offset + 2:offset + 2 + size].decode()
                        qos = data[offset + 2 + size]
                        offset += 3 + size
                        self._subs[sock][topic] = qos
                        topics.append(topic)
                        codes += bytes([min(qos, 2)])
                    self._send(sock, _packet(SUBACK, 0, packet_id + codes))
                    for pattern in topics:
                        for topic, (payload, qos) in list(self.retained.items()):
                            if topic_matches(pattern, topic):
                                self._deliver(sock, topic, payload, min(qos, self._subs[sock][pattern]), True)
                elif kind == UNSUBSCRIBE:
                    size = struct.unpack("!H", data[2:4])[0]
                    self._subs[sock].pop(data[4:4 + size].decode(), None)
                    self._send(sock, _packet(UNSUBACK, 0, data[:2]))
                elif kind == PINGREQ:
                    self._send(sock, _packet(PINGRESP, 0, b""))
                elif kind == DISCONNECT:
                    clean = True
                    return
        finally:
            self._subs.pop(sock, None)
            will = self._wills.pop(sock, None)
            if self.clients.get(client_id) is sock:
                del self.clients[client_id]
            if will is not None and not clean:
                self.publish(*will)

    def _deliver(self, sock: socket.socket, topic: str, payload: bytes, qos: int, retain: bool = False) -> None:
        body = _string(topic)
        if qos:
            self._ids = self._ids % 65535 + 1
            body += struct.pack("!H", self._ids)
        try:
            self._send(sock, _packet(PUBLISH, qos << 1 | (1 if retain else 0), body + payload))
        except OSError:
            pass

    def publish(self, topic: str, payload: Any = b"", qos: int = 0, retain: bool = False) -> None:
        """Sends ``payload`` on ``topic`` to every subscriber (and keeps it with ``retain``)."""
        from ._base import bytes_of

        data = bytes_of(payload)
        self.received.append((topic, data))
        if retain:
            if data:
                self.retained[topic] = (data, qos)
            else:
                self.retained.pop(topic, None)
        for sock, subs in list(self._subs.items()):
            granted = [q for pattern, q in subs.items() if topic_matches(pattern, topic)]
            if granted:
                self._deliver(sock, topic, data, min(qos, max(granted)))


# -- WebSocket ------------------------------------------------------------------------------------------------------
class WebSocketServer(_Server):
    """A WebSocket server: ``answer(message)`` returns the reply to each message (``None``: no reply; by default
    the same message back). ``send(message)`` pushes a message to every client; ``received`` lists what came."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0, *,
                 answer: Optional[Callable[[Any], Any]] = lambda message: message) -> None:
        self.answer = answer
        self.received: List[Any] = []
        self.requests: List[Dict[str, str]] = []
        self._socks: List[socket.socket] = []
        super().__init__(host, port)

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}/"

    def _client(self, sock: socket.socket) -> None:
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = sock.recv(4096)
            if not chunk:
                return
            head += chunk
        lines = head.split(b"\r\n\r\n")[0].decode("latin-1").split("\r\n")
        headers = {k.strip().lower(): v.strip() for k, _, v in (line.partition(":") for line in lines[1:])}
        headers["path"] = lines[0].split(" ")[1] if " " in lines[0] else "/"
        self.requests.append(headers)
        accept = base64.b64encode(hashlib.sha1((headers.get("sec-websocket-key", "") +
                                                "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        extra = ""
        if headers.get("sec-websocket-protocol"):
            extra = f"Sec-WebSocket-Protocol: {headers['sec-websocket-protocol'].split(',')[0].strip()}\r\n"
        sock.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {accept}\r\n{extra}\r\n").encode())
        self._socks.append(sock)
        try:
            while True:
                first, second = _recv(sock, 2)
                size = second & 0x7F
                if size == 126:
                    size = struct.unpack("!H", _recv(sock, 2))[0]
                elif size == 127:
                    size = struct.unpack("!Q", _recv(sock, 8))[0]
                key = _recv(sock, 4) if second & 0x80 else b"\0\0\0\0"
                data = bytes(b ^ key[i % 4] for i, b in enumerate(_recv(sock, size)))
                opcode = first & 0x0F
                if opcode == CLOSE:
                    sock.sendall(frame(CLOSE, data[:2], mask=False))
                    return
                if opcode == PING:
                    sock.sendall(frame(PONG, data, mask=False))
                    continue
                if opcode not in (TEXT, BINARY):
                    continue
                message: Any = data.decode() if opcode == TEXT else data
                self.received.append(message)
                reply = self.answer(message) if self.answer else None
                if reply is not None:
                    self._push(sock, reply)
        finally:
            if sock in self._socks:
                self._socks.remove(sock)

    def _push(self, sock: socket.socket, message: Any) -> None:
        if isinstance(message, (bytes, bytearray)):
            sock.sendall(frame(BINARY, bytes(message), mask=False))
        else:
            sock.sendall(frame(TEXT, str(message).encode(), mask=False))

    def send(self, message: Any) -> None:
        """Sends ``message`` (text or bytes) to every connected client."""
        for sock in list(self._socks):
            try:
                self._push(sock, message)
            except OSError:
                pass


# -- Modbus ---------------------------------------------------------------------------------------------------------
class _ModbusMemory:
    def __init__(self) -> None:
        self.coils: Dict[int, bool] = {}
        self.discrete: Dict[int, bool] = {}
        self.holding: Dict[int, int] = {}
        self.input: Dict[int, int] = {}

    def answer(self, pdu: bytes) -> bytes:
        function = pdu[0]
        try:
            if function in (1, 2):
                address, count = struct.unpack(">HH", pdu[1:5])
                table = self.coils if function == 1 else self.discrete
                packed = bytearray((count + 7) // 8)
                for i in range(count):
                    if table.get(address + i):
                        packed[i // 8] |= 1 << (i % 8)
                return bytes([function, len(packed)]) + bytes(packed)
            if function in (3, 4):
                address, count = struct.unpack(">HH", pdu[1:5])
                table = self.holding if function == 3 else self.input
                if any(address + i not in table for i in range(count)):
                    return bytes([function | 0x80, 2])
                return bytes([function, count * 2]) + struct.pack(f">{count}H", *(table[address + i]
                                                                                  for i in range(count)))
            if function == 5:
                address, value = struct.unpack(">HH", pdu[1:5])
                self.coils[address] = value == 0xFF00
                return pdu[:5]
            if function == 6:
                address, value = struct.unpack(">HH", pdu[1:5])
                self.holding[address] = value
                return pdu[:5]
            if function == 15:
                address, count = struct.unpack(">HH", pdu[1:5])
                for i in range(count):
                    self.coils[address + i] = bool(pdu[6 + i // 8] >> (i % 8) & 1)
                return pdu[:5]
            if function == 16:
                address, count = struct.unpack(">HH", pdu[1:5])
                for i, value in enumerate(struct.unpack(f">{count}H", pdu[6:6 + count * 2])):
                    self.holding[address + i] = value
                return pdu[:5]
        except (struct.error, IndexError):
            return bytes([function | 0x80, 3])
        return bytes([function | 0x80, 1])

    def set_registers(self, address: int, values: List[int], table: str = "holding") -> None:
        target = self.holding if table == "holding" else self.input
        for i, value in enumerate(values):
            target[address + i] = int(value) & 0xFFFF


class ModbusServer(_Server, _ModbusMemory):
    """A Modbus TCP server (a PLC or meter stand-in): fill ``coils``, ``discrete``, ``holding`` and ``input``
    (address -> value) and read them back after the app writes. Reading an unset register answers
    "illegal data address", like a real device."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0, *, unit: int = 1) -> None:
        _ModbusMemory.__init__(self)
        self.unit = unit
        _Server.__init__(self, host, port)

    def _client(self, sock: socket.socket) -> None:
        while True:
            transaction, _, length, unit = struct.unpack(">HHHB", _recv(sock, 7))
            pdu = _recv(sock, length - 1)
            if unit not in (self.unit, 0, 255):
                continue  # another device's request: no answer, the client times out
            answer = self.answer(pdu)
            sock.sendall(struct.pack(">HHHB", transaction, 0, len(answer) + 1, unit) + answer)


def serial_pair() -> Tuple[int, str]:
    """A virtual serial cable: ``(fd, path)``. Open ``path`` with ``pz.SerialPort(path)`` and talk to it with
    ``os.read(fd, n)``/``os.write(fd, data)`` as the device would. Linux and macOS only."""
    if not hasattr(os, "openpty"):
        raise OSError("virtual serial ports need a pseudo-terminal (Linux or macOS)")
    device, port = os.openpty()
    import termios
    import tty

    tty.setraw(device)
    tty.setraw(port)
    attrs = termios.tcgetattr(device)
    attrs[3] &= ~termios.ECHO
    termios.tcsetattr(device, termios.TCSANOW, attrs)
    return device, os.ttyname(port)


def modbus_rtu_device(fd: int, memory: Optional[_ModbusMemory] = None, unit: int = 1) -> _ModbusMemory:
    """Answers Modbus RTU requests that arrive on ``fd`` (the device end of ``serial_pair()``) from ``memory``,
    in a thread of its own. Returns the memory to fill."""
    memory = memory or _ModbusMemory()

    def run() -> None:
        buffer = b""
        while True:
            # Waits with select, never in a blocking read: on macOS, closing a pseudo-terminal that a
            # thread is reading blocks until that read ends.
            try:
                if not select.select([fd], [], [], 0.05)[0]:
                    continue
                chunk = os.read(fd, 256)
            except (OSError, ValueError):
                return
            if not chunk:
                return
            buffer += chunk
            while len(buffer) >= 8:
                function = buffer[1]
                size = 9 + buffer[6] if function in (15, 16) and len(buffer) > 6 else 8
                if len(buffer) < size:
                    break
                request, buffer = buffer[:size], buffer[size:]
                if struct.unpack("<H", request[-2:])[0] != crc16(request[:-2]) or request[0] != unit:
                    continue
                answer = bytes([unit]) + memory.answer(request[1:-2])
                os.write(fd, answer + struct.pack("<H", crc16(answer)))

    threading.Thread(target=run, name="pyzed-modbus-rtu", daemon=True).start()
    return memory


# -- the local network ----------------------------------------------------------------------------------------------
class FakeNetwork:
    """Devices that answer ``DeviceDiscovery`` on this computer: ``attach(discovery)`` points it here.

    ``devices`` are ``Device``s: the ``mdns`` ones answer for their ``service`` (with their
    ``hostname``, ``port`` and ``properties`` as TXT), the ``ssdp`` ones answer M-SEARCH with
    their ``url`` and their ``name`` as the server.
    """

    def __init__(self, devices: Optional[List[Device]] = None) -> None:
        self.devices: List[Device] = list(devices or [])
        self._mdns = self._listen(self._answer_mdns)
        self._ssdp = self._listen(self._answer_ssdp)

    @property
    def mdns_address(self) -> Tuple[str, int]:
        return self._mdns.getsockname()[:2]

    @property
    def ssdp_address(self) -> Tuple[str, int]:
        return self._ssdp.getsockname()[:2]

    def attach(self, discovery: Any) -> Any:
        discovery.mdns_address = self.mdns_address
        discovery.ssdp_address = self.ssdp_address
        return discovery

    def _listen(self, answer: Callable[[bytes], List[bytes]]) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))

        def run() -> None:
            while True:
                try:
                    data, sender = sock.recvfrom(9000)
                    for reply in answer(data):
                        sock.sendto(reply, sender)
                except (OSError, ValueError, struct.error, IndexError):
                    if sock.fileno() < 0:
                        return

        threading.Thread(target=run, name="pyzed-fake-network", daemon=True).start()
        return sock

    def _answer_mdns(self, data: bytes) -> List[bytes]:
        asked = _read_name(data, 12)[0].lower()
        services = [d for d in self.devices if d.kind == "mdns"]
        records: List[Tuple[str, int, bytes]] = []
        if asked == "_services._dns-sd._udp.local":
            for kind in dict.fromkeys(f"{d.service}.local" for d in services):
                records.append((asked, 12, _encode_name(kind)))
        for d in services:
            kind = f"{d.service}.local"
            if kind.lower() != asked:
                continue
            instance = f"{d.name}.{kind}"
            host = d.hostname or f"{d.name.lower().replace(' ', '-')}.local"
            txt = b"".join(bytes([len(f"{k}={v}".encode())]) + f"{k}={v}".encode() for k, v in d.properties.items())
            records += [(kind, 12, _encode_name(instance)),
                        (instance, 33, struct.pack("!3H", 0, 0, d.port) + _encode_name(host)),
                        (instance, 16, txt or b"\0"), (host, 1, socket.inet_aton(d.host))]
        if not records:
            return []
        out = struct.pack("!6H", 0, 0x8400, 0, len(records), 0, 0)
        for name, kind, rdata in records:
            out += _encode_name(name) + struct.pack("!HHIH", kind, 1, 120, len(rdata)) + rdata
        return [out]

    def _answer_ssdp(self, data: bytes) -> List[bytes]:
        if not data.startswith(b"M-SEARCH"):
            return []
        out = []
        for i, d in enumerate(x for x in self.devices if x.kind == "ssdp"):
            url = d.url or f"http://{d.host}:{d.port or 80}/description.xml"
            out.append((f"HTTP/1.1 200 OK\r\nLOCATION: {url}\r\nSERVER: {d.name}\r\n"
                        f"ST: {d.service or 'upnp:rootdevice'}\r\nUSN: uuid:pyzed-fake-{i}::upnp:rootdevice\r\n\r\n")
                       .encode())
        return out

    def close(self) -> None:
        self._mdns.close()
        self._ssdp.close()

    def __enter__(self) -> "FakeNetwork":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
