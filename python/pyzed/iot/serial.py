"""Serial ports: Arduino, ESP32, Raspberry Pi Pico, GPS receivers, barcode scanners, lab instruments..."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, List, Optional, Union

from .. import _core
from ..services import Handler, Service, _Loop
from ._base import Connection, LineSplitter, bytes_of


@dataclass(frozen=True)
class PortInfo:
    """A serial port of this computer: its ``name`` and, for USB devices, who made them."""

    #: ``COM3`` on Windows, ``/dev/ttyUSB0`` or ``/dev/ttyACM0`` on Linux, ``/dev/cu.usbserial-…`` on macOS.
    name: str
    #: ``"usb"``, ``"pci"``, ``"bluetooth"`` or ``"unknown"``.
    kind: str = "unknown"
    #: USB vendor and product ids (``None`` for other ports).
    vid: Optional[int] = None
    pid: Optional[int] = None
    serial_number: Optional[str] = None
    manufacturer: Optional[str] = None
    product: Optional[str] = None

    @property
    def usb_id(self) -> str:
        """``"2341:0043"`` (vendor:product in hex) for USB devices, else ``""``."""
        return f"{self.vid:04x}:{self.pid:04x}" if self.vid is not None and self.pid is not None else ""

    @property
    def description(self) -> str:
        """A readable name: ``"Arduino Uno (COM3)"``, or the port's name."""
        label = " ".join(dict.fromkeys(p for p in (self.manufacturer, self.product) if p))
        return f"{label} ({self.name})" if label else self.name

    def matches(self, query: str) -> bool:
        """Whether ``query`` names this port: its name, ``vid:pid`` in hex, or part of its maker, product or serial
        number (case does not matter)."""
        query = (query or "").strip().lower()
        if not query:
            return True
        if query == self.name.lower() or (self.usb_id and query in (self.usb_id, self.usb_id.split(":")[0])):
            return True
        return any(query in (value or "").lower() for value in (self.manufacturer, self.product, self.serial_number,
                                                                self.name))


def serial_ports(match: str = "") -> List[PortInfo]:
    """The serial ports of this computer (USB adapters, boards, Bluetooth and built-in ports), sorted by name.

    ``match`` keeps the ones it names (see ``PortInfo.matches``): ``"arduino"``, ``"2341:0043"``, ``"COM3"``...
    """
    found = [PortInfo(**{k: v for k, v in info.items()}) for info in _core.serial_ports()]
    found = [p for p in found if p.matches(match)]
    # USB devices first (what people plug in), then the rest.
    return sorted(found, key=lambda p: (p.kind != "usb", p.name))


class SerialPort(Connection):
    """A serial port, line by line or byte by byte: what an Arduino prints with ``Serial.println``.

    ``port`` is the port's name (``"COM3"``, ``"/dev/ttyUSB0"``) or, left empty, the first
    one ``match`` names (``"arduino"``, ``"esp32"``, ``"2341:0043"``...; empty: the first
    USB port). ``baud_rate`` must be the speed the device uses. Every chunk received raises
    ``data`` (bytes) and every complete line raises ``line`` (text without the line break).
    ``write()`` sends bytes or text; ``send_line()`` adds ``newline``.

    With ``reconnect`` (milliseconds, 1000 by default) a device that is unplugged is opened
    again when it comes back::

        board = pz.SerialPort(match="arduino", baud_rate=115200, on_line=self.reading)
        board.connect()

        def reading(self, line):
            self.temperature = float(line)

    Events:
        ``on_connected()``: The port opened.
        ``on_disconnected()``: The port closed (or the device was unplugged).
        ``on_failed(value)``: Callable that receives why the port could not be opened or broke.
        ``on_data(value)``: Callable that receives each chunk of bytes received.
        ``on_line(value)``: Callable that receives each line received, as text.
    """

    events = ("connected", "disconnected", "failed", "data", "line")
    _thread_name = "pyzed-serial"

    def __init__(self, port: str = "", baud_rate: int = 9600, *, match: str = "", data_bits: int = 8,
                 parity: str = "none", stop_bits: float = 1, flow_control: str = "none", newline: str = "\n",
                 encoding: str = "utf-8", dtr: bool = True, reconnect: float = 1000,
                 on_connected: Optional[Handler] = None, on_disconnected: Optional[Handler] = None,
                 on_failed: Optional[Handler] = None, on_data: Optional[Handler] = None,
                 on_line: Optional[Handler] = None) -> None:
        super().__init__(reconnect=reconnect, on_connected=on_connected, on_disconnected=on_disconnected,
                         on_failed=on_failed, on_data=on_data, on_line=on_line)
        self.port = port
        self.match = match
        self.baud_rate = baud_rate
        self.data_bits = data_bits
        self.parity = parity
        self.stop_bits = stop_bits
        self.flow_control = flow_control
        self.newline = newline
        self.encoding = encoding
        #: Whether the DTR line is raised on opening (many boards reset when it changes).
        self.dtr = dtr
        #: The port opened last (its name).
        self.path = ""
        self._conn: Optional[Any] = None
        self._lines = LineSplitter(newline, encoding)

    @staticmethod
    def ports(match: str = "") -> List[PortInfo]:
        """The serial ports of this computer (see ``serial_ports``)."""
        return serial_ports(match)

    def _target(self) -> str:
        if self.port:
            return str(self.port)
        found = serial_ports(self.match)
        if not self.match:
            found = [p for p in found if p.kind == "usb"] or found
        if not found:
            raise OSError(f"no serial port matches {self.match!r}" if self.match else "no serial port is connected")
        return found[0].name

    def _open(self) -> None:
        path = self._target()
        conn = _core.SerialConnection(path, int(self.baud_rate), int(self.data_bits), str(self.parity),
                                      float(self.stop_bits), str(self.flow_control), 0.05)
        try:
            conn.set_dtr(bool(self.dtr))
        except OSError:  # pseudo-terminals and some adapters have no modem lines
            pass
        self.path = path
        self._lines = LineSplitter(self.newline, self.encoding)
        self._conn = conn

    def _serve(self) -> None:
        conn = self._conn
        while conn is not None and not self._stop.is_set() and conn.is_open:
            data = conn.read(4096)
            if not data:
                continue
            self.emit("data", data)
            if self.handles("line"):
                for line in self._lines.feed(data):
                    self.emit("line", line)

    def _close(self) -> None:
        conn, self._conn = self._conn, None
        if conn is not None:
            conn.close()

    # -- sending -----------------------------------------------------------------------------------------------
    def write(self, data: Union[str, bytes]) -> bool:
        """Sends ``data`` (text is encoded with ``encoding``); returns ``False`` when the port is not open."""
        conn = self._conn
        if conn is None or not self.enabled:
            return False
        try:
            conn.write(bytes_of(data, self.encoding))
        except OSError as error:
            self._failed(error)
            return False
        return True

    def send_line(self, text: str = "") -> bool:
        """Sends ``text`` followed by ``newline``."""
        return self.write(str(text) + (self.newline or "\n"))

    def reset(self) -> bool:
        """Drops and raises DTR, which restarts most Arduino-style boards."""
        conn = self._conn
        if conn is None:
            return False
        import time

        try:
            conn.set_dtr(False)
            time.sleep(0.1)
            conn.set_dtr(True)
        except OSError:
            return False
        return True

    def set_baud_rate(self, baud_rate: int) -> None:
        """Changes the speed, also of an open port."""
        self.baud_rate = int(baud_rate)
        if self._conn is not None:
            self._conn.set_baud_rate(self.baud_rate)


class SerialWatcher(Service):
    """Notices serial devices being plugged in and unplugged: a board, a USB adapter, a GPS...

    It looks at the ports every ``interval`` milliseconds while it runs. ``ports`` is the
    last list; ``match`` keeps only the devices it names (see ``PortInfo.matches``).

    Events:
        ``on_plugged(value)``: Callable that receives the ``PortInfo`` of a device plugged in.
        ``on_unplugged(value)``: Callable that receives the ``PortInfo`` of a device unplugged.
        ``on_change(value)``: Callable that receives the list of ports after a change.
    """

    events = ("plugged", "unplugged", "change")

    def __init__(self, *, match: str = "", interval: float = 1000, on_plugged: Optional[Handler] = None,
                 on_unplugged: Optional[Handler] = None, on_change: Optional[Handler] = None) -> None:
        super().__init__(on_plugged=on_plugged, on_unplugged=on_unplugged, on_change=on_change)
        self.match = match
        self.interval = interval
        self.ports: List[PortInfo] = []
        self._loop: Optional[_Loop] = None
        self._lock = threading.Lock()

    def check(self) -> List[PortInfo]:
        """Looks at the ports now and raises the events of what changed."""
        with self._lock:
            now = serial_ports(self.match)
            before = {p.name: p for p in self.ports}
            after = {p.name: p for p in now}
            self.ports = now
        for name in before.keys() - after.keys():
            self.emit("unplugged", before[name])
        for name in sorted(after.keys() - before.keys()):
            self.emit("plugged", after[name])
        if before.keys() != after.keys():
            self.emit("change", now)
        return now

    @property
    def running(self) -> bool:
        return self._loop is not None and self._loop.alive

    @running.setter
    def running(self, value: bool) -> None:
        if value and not self.running:
            self.start()
        elif not value:
            self.stop()

    def start(self) -> None:
        """Starts watching; the ports present now are in ``ports`` without raising ``plugged``."""
        self.stop()
        with self._lock:
            self.ports = serial_ports(self.match)
        self._loop = _Loop("pyzed-serial-watch", self.check, lambda: float(self.interval) / 1000)

    def stop(self) -> None:
        if self._loop is not None:
            self._loop.stop()
            self._loop = None
