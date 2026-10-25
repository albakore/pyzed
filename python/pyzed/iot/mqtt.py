"""MQTT: the messaging protocol of home automation, sensors and industrial devices (MQTT 3.1.1, no dependencies)."""

from __future__ import annotations

import json as _json
import os
import socket
import struct
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from ..services import Handler, deliver
from ._base import Connection, bytes_of, text_of

__all__ = ["MqttClient", "MqttError", "MqttMessage", "topic_matches"]

CONNECT, CONNACK, PUBLISH, PUBACK, PUBREC, PUBREL, PUBCOMP = 1, 2, 3, 4, 5, 6, 7
SUBSCRIBE, SUBACK, UNSUBSCRIBE, UNSUBACK, PINGREQ, PINGRESP, DISCONNECT = 8, 9, 10, 11, 12, 13, 14

#: Why a broker refused the connection (CONNACK return codes).
REFUSED = {1: "the broker does not speak MQTT 3.1.1", 2: "the client id was rejected", 3: "the broker is unavailable",
           4: "wrong user name or password", 5: "not authorized"}


class MqttError(OSError):
    """The broker refused the connection or broke the protocol."""


def topic_matches(pattern: str, topic: str) -> bool:
    """Whether ``topic`` matches the subscription ``pattern``, with MQTT's wildcards: ``+`` is one level and ``#``
    every level below (``"home/+/temperature"``, ``"sensors/#"``)."""
    if pattern == topic:
        return True
    parts, levels = pattern.split("/"), topic.split("/")
    if topic.startswith("$") and parts[0] in ("+", "#"):
        return False  # $SYS topics never match wildcards at the first level
    for i, part in enumerate(parts):
        if part == "#":
            return True
        if i >= len(levels) or (part != "+" and part != levels[i]):
            return False
    return len(parts) == len(levels)


@dataclass(frozen=True)
class MqttMessage:
    """A message received on a topic."""

    topic: str
    payload: bytes
    qos: int = 0
    retain: bool = False

    @property
    def text(self) -> str:
        """The payload as UTF-8 text."""
        return text_of(self.payload)

    def json(self) -> Any:
        """The payload parsed as JSON (raises ``ValueError`` when it is not)."""
        return _json.loads(self.payload)

    @property
    def value(self) -> Any:
        """The payload as what it looks like: a number (``"21.5"``), JSON (``{"t": 21}``, ``true``) or text."""
        text = self.text.strip()
        try:
            return _json.loads(text)
        except ValueError:
            return self.text

    def matches(self, pattern: str) -> bool:
        return topic_matches(pattern, self.topic)


def _string(text: Union[str, bytes]) -> bytes:
    data = text if isinstance(text, bytes) else str(text).encode("utf-8")
    return struct.pack("!H", len(data)) + data


def _packet(kind: int, flags: int, body: bytes) -> bytes:
    length, out = len(body), bytearray([kind << 4 | flags])
    while True:
        byte, length = length % 128, length // 128
        out.append(byte | (128 if length else 0))
        if not length:
            return bytes(out) + body


def _topics(value: Union[str, Sequence[Any], None]) -> List[Tuple[str, int]]:
    """Topics given as text (one per line or separated by commas, ``"topic 1"`` for QoS 1) or a list."""
    if not value:
        return []
    items = value.replace(",", "\n").splitlines() if isinstance(value, str) else list(value)
    out = []
    for item in items:
        if isinstance(item, (tuple, list)):
            out.append((str(item[0]), int(item[1]) if len(item) > 1 else 0))
            continue
        topic, _, qos = str(item).strip().partition(" ")
        if topic:
            out.append((topic, int(qos) if qos.strip().isdigit() else 0))
    return out


class MqttClient(Connection):
    """A client of an MQTT broker (Mosquitto, EMQX, HiveMQ, Home Assistant's...): publishes and subscribes.

    ``host`` and ``port`` (1883, or 8883 with ``tls``) name the broker; ``username`` and
    ``password`` log in. ``subscribe`` lists the topics to follow (wildcards ``+`` and ``#``
    work), kept again after every reconnection. Each message raises ``message`` with an
    ``MqttMessage`` (``topic``, ``text``, ``value``, ``json()``); ``on_topic(pattern, handler)``
    sends the ones of a topic to a handler of their own::

        mqtt = pz.MqttClient("broker.local", subscribe="home/#", on_message=self.received)
        mqtt.on_topic("home/+/temperature", self.temperature)
        mqtt.connect()
        mqtt.publish("home/lamp/set", "on")

    ``qos`` 0 sends once, 1 at least once (resent until the broker acknowledges it) and 2
    exactly once. A message of QoS 1 or 2 published while disconnected waits for the
    connection. ``will_topic``/``will_message`` is what the broker publishes if the app
    disappears without disconnecting.

    Events:
        ``on_connected()``: The broker accepted the connection.
        ``on_disconnected()``: The connection ended.
        ``on_failed(value)``: Callable that receives why the connection could not be made or broke.
        ``on_message(value)``: Callable that receives each ``MqttMessage``.
        ``on_published(value)``: Callable that receives the topic of a QoS 1 or 2 message the broker acknowledged.
        ``on_subscribed(value)``: Callable that receives the topics the broker confirmed.
    """

    events = ("connected", "disconnected", "failed", "message", "published", "subscribed")
    _thread_name = "pyzed-mqtt"

    def __init__(self, host: str = "localhost", port: int = 0, *, client_id: str = "", username: str = "",
                 password: str = "", tls: bool = False, ca_file: str = "", insecure: bool = False,
                 keepalive: float = 60, clean_session: bool = True, subscribe: Union[str, Sequence[Any], None] = None,
                 will_topic: str = "", will_message: Union[str, bytes] = "", will_qos: int = 0,
                 will_retain: bool = False, timeout: float = 10, reconnect: float = 2000,
                 on_connected: Optional[Handler] = None, on_disconnected: Optional[Handler] = None,
                 on_failed: Optional[Handler] = None, on_message: Optional[Handler] = None,
                 on_published: Optional[Handler] = None, on_subscribed: Optional[Handler] = None) -> None:
        super().__init__(reconnect=reconnect, on_connected=on_connected, on_disconnected=on_disconnected,
                         on_failed=on_failed, on_message=on_message, on_published=on_published,
                         on_subscribed=on_subscribed)
        self.host = host
        self.port = port
        self.client_id = client_id or f"pyzed-{os.urandom(4).hex()}"
        self.username = username
        self.password = password
        self.tls = tls
        self.ca_file = ca_file
        #: With ``tls``, accept any certificate (a broker with a self-signed one on your own network).
        self.insecure = insecure
        self.keepalive = keepalive
        self.clean_session = clean_session
        self.subscribe_to = subscribe
        self.will_topic = will_topic
        self.will_message = will_message
        self.will_qos = will_qos
        self.will_retain = will_retain
        self.timeout = timeout
        #: The last message received on each topic.
        self.last: Dict[str, MqttMessage] = {}
        self._sock: Optional[socket.socket] = None
        self._send_lock = threading.Lock()
        self._ids = 0
        self._inflight: Dict[int, Tuple[str, bytes, int]] = {}  # packet id -> (topic, packet, kind awaited)
        self._waiting: List[Tuple[int, Tuple[str, bytes, int]]] = []  # QoS 1/2 published while disconnected
        self._incoming: Dict[int, MqttMessage] = {}  # QoS 2 messages waiting for PUBREL
        self._pending_subs: Dict[int, List[str]] = {}
        self._routes: List[Tuple[str, Callable[..., Any]]] = []
        self._subscribed: Dict[str, int] = {}
        self._last_sent = 0.0

    # -- the subscribe property (``subscribe`` is also a method) -------------------------------------------------
    @property
    def topics(self) -> List[str]:
        """The topics this client follows."""
        return list(dict.fromkeys([t for t, _ in _topics(self.subscribe_to)] + list(self._subscribed)))

    @property
    def broker_port(self) -> int:
        return int(self.port) or (8883 if self.tls else 1883)

    # -- connection --------------------------------------------------------------------------------------------
    def _open(self) -> None:
        sock = socket.create_connection((self.host, self.broker_port), timeout=float(self.timeout))
        if self.tls:
            import ssl

            context = ssl.create_default_context(cafile=self.ca_file or None)
            if self.insecure:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            sock = context.wrap_socket(sock, server_hostname=self.host)
        self._sock = sock
        flags = 0x02 if self.clean_session else 0
        payload = _string(self.client_id)
        if self.will_topic:
            flags |= 0x04 | (int(self.will_qos) & 3) << 3 | (0x20 if self.will_retain else 0)
            payload += _string(self.will_topic) + _string(bytes_of(self.will_message))
        if self.username:
            flags |= 0x80
            payload += _string(self.username)
            if self.password:
                flags |= 0x40
                payload += _string(self.password)
        body = _string("MQTT") + bytes([4, flags]) + struct.pack("!H", int(self.keepalive) & 0xFFFF) + payload
        self._raw(_packet(CONNECT, 0, body))
        kind, _, data = self._read_packet()
        if kind != CONNACK or len(data) < 2:
            raise MqttError("the broker did not answer like an MQTT broker")
        if data[1]:
            raise MqttError(f"the broker refused the connection: {REFUSED.get(data[1], f'code {data[1]}')}")
        sock.settimeout(0.5)

    def _on_open(self) -> None:
        wanted = {**{t: q for t, q in _topics(self.subscribe_to)}, **self._subscribed}
        if wanted:
            self._send_subscribe(list(wanted.items()))
        for _, packet, _ in list(self._inflight.values()):  # unacknowledged: again, marked as a duplicate
            self._raw(bytes([packet[0] | 0x08]) + packet[1:] if packet[0] >> 4 == PUBLISH else packet)
        waiting, self._waiting = self._waiting, []
        for packet_id, entry in waiting:
            self._inflight[packet_id] = entry
            self._raw(entry[1])

    def _close(self) -> None:
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                if self._stop.is_set():  # a clean goodbye: the broker does not publish the will
                    sock.sendall(_packet(DISCONNECT, 0, b""))
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass

    def _raw(self, packet: bytes) -> None:
        sock = self._sock
        if sock is None:
            raise MqttError("not connected")
        with self._send_lock:
            sock.sendall(packet)
            self._last_sent = time.monotonic()

    def _recv(self, size: int) -> bytes:
        sock, out = self._sock, b""
        while len(out) < size:
            if sock is None or self._stop.is_set():
                raise MqttError("closed")
            try:
                chunk = sock.recv(size - len(out))
            except socket.timeout:
                if not out:
                    raise
                continue
            if not chunk:
                raise MqttError("the broker closed the connection")
            out += chunk
        return out

    def _read_packet(self) -> Tuple[int, int, bytes]:
        first = self._recv(1)[0]
        length, shift = 0, 0
        while True:
            byte = self._recv(1)[0]
            length |= (byte & 127) << shift
            shift += 7
            if not byte & 128:
                break
            if shift > 21:
                raise MqttError("a malformed packet")
        return first >> 4, first & 15, self._recv(length) if length else b""

    def _serve(self) -> None:
        last_heard = time.monotonic()
        while not self._stop.is_set():
            keepalive = float(self.keepalive or 0)
            try:
                kind, flags, data = self._read_packet()
            except socket.timeout:
                now = time.monotonic()
                if keepalive > 0 and now - last_heard > keepalive * 1.5:
                    raise MqttError("the broker stopped answering") from None
                if keepalive > 0 and now - self._last_sent > keepalive * 0.75:
                    self._raw(_packet(PINGREQ, 0, b""))
                continue
            last_heard = time.monotonic()
            self._handle(kind, flags, data)

    def _handle(self, kind: int, flags: int, data: bytes) -> None:
        if kind == PUBLISH:
            qos, retain = (flags >> 1) & 3, bool(flags & 1)
            size = struct.unpack("!H", data[:2])[0]
            topic, rest = data[2:2 + size].decode("utf-8", "replace"), data[2 + size:]
            packet_id = None
            if qos:
                packet_id, rest = struct.unpack("!H", rest[:2])[0], rest[2:]
            message = MqttMessage(topic, bytes(rest), qos, retain)
            if qos == 1:
                self._raw(_packet(PUBACK, 0, struct.pack("!H", packet_id)))
            elif qos == 2:
                self._incoming[packet_id] = message
                self._raw(_packet(PUBREC, 0, struct.pack("!H", packet_id)))
                return  # delivered once the broker releases it
            self._deliver(message)
        elif kind == PUBREL:
            packet_id = struct.unpack("!H", data[:2])[0]
            self._raw(_packet(PUBCOMP, 0, data[:2]))
            message = self._incoming.pop(packet_id, None)
            if message is not None:
                self._deliver(message)
        elif kind in (PUBACK, PUBCOMP):
            entry = self._inflight.pop(struct.unpack("!H", data[:2])[0], None)
            if entry is not None:
                self.emit("published", entry[0])
        elif kind == PUBREC:
            packet_id = struct.unpack("!H", data[:2])[0]
            entry = self._inflight.get(packet_id)
            release = _packet(PUBREL, 2, data[:2])
            if entry is not None:
                self._inflight[packet_id] = (entry[0], release, PUBCOMP)
            self._raw(release)
        elif kind == SUBACK:
            packet_id = struct.unpack("!H", data[:2])[0]
            topics = self._pending_subs.pop(packet_id, [])
            granted = [t for t, code in zip(topics, data[2:]) if code != 0x80]
            if granted:
                self.emit("subscribed", granted)
            refused = [t for t, code in zip(topics, data[2:]) if code == 0x80]
            if refused:
                self.emit("failed", f"the broker refused the subscription to {', '.join(refused)}")
        # PINGRESP and UNSUBACK need nothing

    def _deliver(self, message: MqttMessage) -> None:
        self.last[message.topic] = message
        self.emit("message", message)
        if not self.enabled:
            return
        from ..events import accepts_argument

        for pattern, handler in list(self._routes):
            if topic_matches(pattern, message.topic):
                if accepts_argument(handler):
                    deliver(lambda h=handler: h(message))
                else:
                    deliver(handler)

    def _next_id(self) -> int:
        with self._send_lock:
            self._ids = self._ids % 65535 + 1
            while self._ids in self._inflight or self._ids in self._pending_subs or any(
                    self._ids == waiting for waiting, _ in self._waiting):
                self._ids = self._ids % 65535 + 1
            return self._ids

    # -- publishing and subscribing ----------------------------------------------------------------------------
    def publish(self, topic: str, payload: Any = b"", qos: int = 0, retain: bool = False) -> bool:
        """Publishes ``payload`` (text, bytes, a number, or a dict or list sent as JSON) on ``topic``.

        Returns ``False`` when a QoS 0 message could not go out because the client is not connected.
        """
        if not self.enabled or not topic:
            return False
        qos = max(0, min(int(qos), 2))
        body = _string(topic)
        packet_id = 0
        if qos:
            packet_id = self._next_id()
            body += struct.pack("!H", packet_id)
        packet = _packet(PUBLISH, qos << 1 | (1 if retain else 0), body + bytes_of(payload))
        entry = (topic, packet, PUBACK if qos == 1 else PUBREC)
        if not self.connected:
            if qos:
                self._waiting.append((packet_id, entry))
                return True
            return False
        if qos:
            self._inflight[packet_id] = entry
        try:
            self._raw(packet)
        except OSError:
            return bool(qos)  # resent when the connection comes back
        return True

    def _send_subscribe(self, topics: List[Tuple[str, int]]) -> None:
        packet_id = self._next_id()
        self._pending_subs[packet_id] = [t for t, _ in topics]
        body = struct.pack("!H", packet_id) + b"".join(_string(t) + bytes([max(0, min(q, 2))]) for t, q in topics)
        self._raw(_packet(SUBSCRIBE, 2, body))

    def subscribe(self, topic: Union[str, Sequence[str]], qos: int = 0) -> None:
        """Follows ``topic`` (or several), now if connected and after every reconnection."""
        topics = [(t, q if q else int(qos)) for t, q in _topics(topic if not isinstance(topic, str) else [topic])]
        for t, q in topics:
            self._subscribed[t] = q
        if self.connected and topics:
            try:
                self._send_subscribe(topics)
            except OSError:
                pass

    def unsubscribe(self, topic: str) -> None:
        """Stops following ``topic``."""
        self._subscribed.pop(topic, None)
        self.subscribe_to = [(t, q) for t, q in _topics(self.subscribe_to) if t != topic]
        if self.connected:
            try:
                self._raw(_packet(UNSUBSCRIBE, 2, struct.pack("!H", self._next_id()) + _string(topic)))
            except OSError:
                pass

    def on_topic(self, pattern: str, handler: Optional[Callable[..., Any]]) -> "MqttClient":
        """Sends the messages of the topics ``pattern`` matches to ``handler`` (``None`` removes it) and follows
        them. Returns the client."""
        self._routes = [(p, h) for p, h in self._routes if p != pattern]
        if handler is not None:
            self._routes.append((pattern, handler))
            if pattern not in self.topics:
                self.subscribe(pattern)
        return self
