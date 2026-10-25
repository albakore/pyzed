"""Modbus: the protocol of PLCs, energy meters, inverters, VFDs and industrial sensors (TCP and RTU over serial)."""

from __future__ import annotations

import socket
import struct
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Union

from .. import _core
from ..services import Handler
from ._base import Connection

__all__ = ["ModbusClient", "ModbusError", "PollItem", "crc16", "decode", "encode"]

#: What the exception codes of a Modbus answer mean.
EXCEPTIONS = {1: "illegal function", 2: "illegal data address", 3: "illegal data value", 4: "server device failure",
              5: "acknowledge", 6: "server device busy", 8: "memory parity error",
              10: "gateway path unavailable", 11: "gateway target device failed to respond"}
#: Register tables: name -> read function code.
TABLES = {"coils": 1, "coil": 1, "discrete": 2, "discrete_inputs": 2, "inputs": 2, "holding": 3,
          "holding_registers": 3, "input": 4, "input_registers": 4}
#: Value formats: name -> (struct code, registers).
FORMATS = {"int16": ("h", 1), "uint16": ("H", 1), "int32": ("i", 2), "uint32": ("I", 2), "float32": ("f", 2),
           "int64": ("q", 4), "uint64": ("Q", 4), "float64": ("d", 4)}


class ModbusError(OSError):
    """The device answered with an exception, did not answer, or answered wrongly."""


def crc16(data: bytes) -> int:
    """The Modbus RTU checksum of ``data``."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def decode(registers: Sequence[int], format: str = "uint16", word_order: str = "big") -> List[Union[int, float]]:  # noqa: A002
    """The values in 16-bit ``registers``: ``"float32"`` takes two per value, ``"int64"`` four...

    ``word_order="little"`` reads the low word first (some meters and PLCs do).
    """
    code, size = FORMATS[format]
    out: List[Union[int, float]] = []
    for i in range(0, len(registers) - size + 1, size):
        words = list(registers[i:i + size])
        if word_order == "little":
            words.reverse()
        out.append(struct.unpack(f">{code}", struct.pack(f">{size}H", *(w & 0xFFFF for w in words)))[0])
    return out


def encode(values: Union[float, int, Sequence[Union[int, float]]], format: str = "uint16",  # noqa: A002
           word_order: str = "big") -> List[int]:
    """The 16-bit registers that hold ``values`` (the opposite of ``decode``)."""
    code, size = FORMATS[format]
    items = [values] if isinstance(values, (int, float)) else list(values)
    out: List[int] = []
    for value in items:
        value = float(value) if code in "fd" else int(value)
        words = list(struct.unpack(f">{size}H", struct.pack(f">{code}", value)))
        if word_order == "little":
            words.reverse()
        out += words
    return out


@dataclass(frozen=True)
class PollItem:
    """A value read on every poll: ``"temperature holding 100 float32"``."""

    name: str
    table: str
    address: int
    format: str = "uint16"  # noqa: A003
    count: int = 1

    @classmethod
    def parse(cls, line: str) -> "PollItem":
        """``name table address [format] [count]``: ``"power input 30 float32"``, ``"relays coils 0 8"``."""
        parts = line.replace(",", " ").split()
        if len(parts) < 3:
            raise ValueError(f"a poll line is 'name table address [format] [count]', not {line!r}")
        name, table, address, *rest = parts
        if table.lower() not in TABLES:
            raise ValueError(f"table must be one of coils, discrete, holding or input, not {table!r}")
        fmt, count = "bool" if TABLES[table.lower()] <= 2 else "uint16", 1
        for item in rest:
            if item.isdigit():
                count = int(item)
            elif item.lower() in FORMATS:
                fmt = item.lower()
        return cls(name, table.lower(), int(address, 0), fmt, count)


def _poll_items(value: Union[str, Sequence[Any], None]) -> List[PollItem]:
    if not value:
        return []
    lines = value.splitlines() if isinstance(value, str) else list(value)
    return [line if isinstance(line, PollItem) else PollItem.parse(str(line)) for line in lines
            if not isinstance(line, str) or (line.strip() and not line.strip().startswith("#"))]


class ModbusClient(Connection):
    """A Modbus client (master): reads and writes the coils and registers of a device.

    With ``host`` it speaks Modbus TCP (``port`` 502); with ``serial_port`` (``"COM4"``,
    ``"/dev/ttyUSB0"``) it speaks Modbus RTU over RS-485/RS-232 at ``baud_rate``. ``unit``
    is the device's address (slave id). ``read_holding_registers(address, count)`` and the
    other calls block for at most ``timeout`` milliseconds and raise ``ModbusError`` when the
    device does not answer or refuses.

    ``poll`` reads values every ``interval`` milliseconds in the background and raises
    ``update`` with a dict of them; each line is ``name table address [format] [count]``::

        meter = pz.ModbusClient("192.168.1.40", poll="voltage input 0 float32\\npower input 12 float32",
                                on_update=self.show)
        meter.connect()

        def show(self, values):
            self.power = values["power"]

    Events:
        ``on_connected()``: The connection opened.
        ``on_disconnected()``: The connection closed.
        ``on_failed(value)``: Callable that receives why it could not connect, or why a poll failed.
        ``on_update(value)``: Callable that receives a dict with the values of ``poll`` after each poll.
    """

    events = ("connected", "disconnected", "failed", "update")
    _thread_name = "pyzed-modbus"

    def __init__(self, host: str = "", port: int = 502, *, serial_port: str = "", baud_rate: int = 9600,
                 parity: str = "none", stop_bits: float = 1, unit: int = 1, timeout: float = 1000,
                 poll: Union[str, Sequence[Any], None] = None, interval: float = 1000, word_order: str = "big",
                 reconnect: float = 2000, on_connected: Optional[Handler] = None,
                 on_disconnected: Optional[Handler] = None, on_failed: Optional[Handler] = None,
                 on_update: Optional[Handler] = None) -> None:
        super().__init__(reconnect=reconnect, on_connected=on_connected, on_disconnected=on_disconnected,
                         on_failed=on_failed, on_update=on_update)
        self.host = host
        self.port = port
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.parity = parity
        self.stop_bits = stop_bits
        self.unit = unit
        self.timeout = timeout
        self.poll = poll
        self.interval = interval
        self.word_order = word_order
        #: The values of the last poll.
        self.values: Dict[str, Any] = {}
        self._sock: Optional[socket.socket] = None
        self._serial: Optional[Any] = None
        self._transaction = 0
        self._request_lock = threading.Lock()

    @property
    def rtu(self) -> bool:
        """Whether it speaks Modbus RTU (over a serial port)."""
        return bool(self.serial_port) and not self.host

    # -- connection --------------------------------------------------------------------------------------------
    def _open(self) -> None:
        if self.rtu:
            self._serial = _core.SerialConnection(str(self.serial_port), int(self.baud_rate), 8, str(self.parity),
                                                  float(self.stop_bits), "none", 0.02)
        elif self.host:
            sock = socket.create_connection((self.host, int(self.port or 502)), timeout=float(self.timeout) / 1000)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._sock = sock
        else:
            raise ModbusError("no address: set host (Modbus TCP) or serial_port (Modbus RTU)")

    def _serve(self) -> None:
        while not self._stop.is_set():
            items = _poll_items(self.poll)
            started = time.monotonic()
            if items and self.enabled:
                try:
                    self.values = self.read_poll(items)
                except ModbusError as error:
                    self._failed(error)
                except OSError as error:  # the connection broke: connect again
                    raise ModbusError(str(error)) from error
                else:
                    self.emit("update", dict(self.values))
            wait = max(float(self.interval or 0), 10) / 1000 - (time.monotonic() - started)
            if self._stop.wait(max(wait, 0.01)):
                return
            if self._sock is None and self._serial is None:
                return

    def _close(self) -> None:
        sock, self._sock = self._sock, None
        serial, self._serial = self._serial, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        if serial is not None:
            serial.close()

    # -- requests ----------------------------------------------------------------------------------------------
    def request(self, function: int, data: bytes, unit: Optional[int] = None) -> bytes:
        """Sends one request (function code and data) and returns the data of the answer."""
        unit = int(self.unit if unit is None else unit)
        with self._request_lock:
            if self._sock is not None:
                answer = self._tcp(unit, bytes([function]) + data)
            elif self._serial is not None:
                answer = self._rtu(unit, bytes([function]) + data)
            else:
                raise ModbusError("not connected")
        if answer[0] & 0x80:
            code = answer[1] if len(answer) > 1 else 0
            raise ModbusError(f"the device refused: {EXCEPTIONS.get(code, f'exception {code}')}")
        if answer[0] != function:
            raise ModbusError("the device answered another request")
        return answer[1:]

    def _tcp(self, unit: int, pdu: bytes) -> bytes:
        sock = self._sock
        assert sock is not None
        self._transaction = self._transaction % 65535 + 1
        sock.sendall(struct.pack(">HHHB", self._transaction, 0, len(pdu) + 1, unit) + pdu)
        deadline = time.monotonic() + float(self.timeout) / 1000
        while True:
            head = self._read_socket(sock, 7, deadline)
            transaction, _, length, _ = struct.unpack(">HHHB", head)
            body = self._read_socket(sock, length - 1, deadline)
            if transaction == self._transaction:
                return body
            # an answer to an older request that timed out: skip it

    def _read_socket(self, sock: socket.socket, size: int, deadline: float) -> bytes:
        out = b""
        while len(out) < size:
            left = deadline - time.monotonic()
            if left <= 0:
                raise ModbusError("the device did not answer in time")
            sock.settimeout(left)
            try:
                chunk = sock.recv(size - len(out))
            except socket.timeout:
                raise ModbusError("the device did not answer in time") from None
            if not chunk:
                raise OSError("the device closed the connection")
            out += chunk
        return out

    def _rtu(self, unit: int, pdu: bytes) -> bytes:
        serial = self._serial
        assert serial is not None
        frame = bytes([unit]) + pdu
        crc = crc16(frame)
        serial.clear()
        serial.write(frame + struct.pack("<H", crc))
        if unit == 0:
            return pdu[:1] + b"\0" * 4  # a broadcast gets no answer
        deadline = time.monotonic() + float(self.timeout) / 1000
        buffer = b""

        def need(size: int) -> None:
            nonlocal buffer
            while len(buffer) < size:
                if time.monotonic() > deadline:
                    raise ModbusError("the device did not answer in time")
                buffer += serial.read(size - len(buffer))

        need(3)
        function = buffer[1]
        if function & 0x80:
            size = 5
        elif function in (1, 2, 3, 4):
            size = 5 + buffer[2]
        else:
            size = 8
        need(size)
        answer = buffer[:size]
        if struct.unpack("<H", answer[-2:])[0] != crc16(answer[:-2]):
            raise ModbusError("the answer's checksum is wrong (check the speed and parity)")
        if answer[0] != unit:
            raise ModbusError("another device answered")
        return answer[1:-2]

    # -- reading -----------------------------------------------------------------------------------------------
    def _read_bits(self, function: int, address: int, count: int) -> List[bool]:
        data = self.request(function, struct.pack(">HH", address, count))
        bits = data[1:1 + data[0]]
        return [bool(bits[i // 8] >> (i % 8) & 1) for i in range(count)]

    def _read_registers(self, function: int, address: int, count: int) -> List[int]:
        data = self.request(function, struct.pack(">HH", address, count))
        return list(struct.unpack(f">{data[0] // 2}H", data[1:1 + data[0]]))

    def read_coils(self, address: int, count: int = 1) -> List[bool]:
        """The on/off outputs from ``address`` (function 1)."""
        return self._read_bits(1, address, count)

    def read_discrete_inputs(self, address: int, count: int = 1) -> List[bool]:
        """The on/off inputs from ``address`` (function 2)."""
        return self._read_bits(2, address, count)

    def read_holding_registers(self, address: int, count: int = 1) -> List[int]:
        """The 16-bit read/write registers from ``address`` (function 3)."""
        return self._read_registers(3, address, count)

    def read_input_registers(self, address: int, count: int = 1) -> List[int]:
        """The 16-bit read-only registers from ``address`` (function 4)."""
        return self._read_registers(4, address, count)

    def read(self, table: str, address: int, format: str = "uint16", count: int = 1) -> Any:  # noqa: A002
        """``count`` values of ``format`` from a ``table`` (``"holding"``, ``"input"``, ``"coils"``,
        ``"discrete"``); one value when ``count`` is 1."""
        function = TABLES[table.lower()]
        if function <= 2:
            bits = self._read_bits(function, address, count)
            return bits[0] if count == 1 else bits
        size = FORMATS[format][1] if format in FORMATS else 1
        values = decode(self._read_registers(function, address, size * count), format if format in FORMATS
                        else "uint16", self.word_order)
        return values[0] if count == 1 else values

    def read_poll(self, items: Optional[Sequence[PollItem]] = None) -> Dict[str, Any]:
        """Reads every value of ``poll`` (or ``items``) now."""
        return {item.name: self.read(item.table, item.address, item.format, item.count)
                for item in (items if items is not None else _poll_items(self.poll))}

    # -- writing -----------------------------------------------------------------------------------------------
    def write_coil(self, address: int, value: bool) -> None:
        """Turns one output on or off (function 5)."""
        self.request(5, struct.pack(">HH", address, 0xFF00 if value else 0))

    def write_register(self, address: int, value: int) -> None:
        """Writes one 16-bit register (function 6)."""
        self.request(6, struct.pack(">HH", address, int(value) & 0xFFFF))

    def write_coils(self, address: int, values: Sequence[bool]) -> None:
        """Sets several outputs from ``address`` (function 15)."""
        packed = bytearray((len(values) + 7) // 8)
        for i, value in enumerate(values):
            if value:
                packed[i // 8] |= 1 << (i % 8)
        self.request(15, struct.pack(">HHB", address, len(values), len(packed)) + bytes(packed))

    def write_registers(self, address: int, values: Sequence[int]) -> None:
        """Writes several 16-bit registers from ``address`` (function 16)."""
        self.request(16, struct.pack(f">HHB{len(values)}H", address, len(values), len(values) * 2,
                                     *(int(v) & 0xFFFF for v in values)))

    def write(self, address: int, value: Union[int, float, Sequence[Union[int, float]]],
              format: str = "uint16") -> None:  # noqa: A002
        """Writes ``value`` (or several) as ``format`` into holding registers from ``address``."""
        registers = encode(value, format, self.word_order)
        if len(registers) == 1:
            self.write_register(address, registers[0])
        else:
            self.write_registers(address, registers)
