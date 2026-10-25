"""Bluetooth Low Energy: heart-rate straps, sensor tags, smart bulbs, BLE boards (ESP32, nRF, micro:bit...).

It works through `bleak <https://github.com/hbldh/bleak>`_, which speaks to each system's own
Bluetooth (WinRT on Windows, CoreBluetooth on macOS, BlueZ on Linux). Install it with
``pip install "pyzed-ui[bluetooth]"`` (or ``uv add "pyzed-ui[bluetooth]"``); without it the
services raise ``failed`` saying so.
"""

from __future__ import annotations

import json as _json
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union

from .. import _async
from ..services import Handler, Service
from ._base import Connection, bytes_of, text_of

__all__ = ["BleDevice", "BleNotification", "BluetoothDevice", "BluetoothScanner", "uuid"]

INSTALL = 'Bluetooth needs the bleak package: pip install "pyzed-ui[bluetooth]"'

#: Names for common standard characteristics and services (Bluetooth SIG assigned numbers).
KNOWN = {"battery_level": "2a19", "heart_rate_measurement": "2a37", "temperature": "2a6e", "humidity": "2a6f",
         "device_name": "2a00", "manufacturer_name": "2a29", "model_number": "2a24", "firmware_revision": "2a26",
         "battery_service": "180f", "heart_rate": "180d", "environmental_sensing": "181a",
         "device_information": "180a", "nordic_uart": "6e400001-b5a3-f393-e0a9-e50e24dcca9e",
         "nordic_uart_rx": "6e400002-b5a3-f393-e0a9-e50e24dcca9e",
         "nordic_uart_tx": "6e400003-b5a3-f393-e0a9-e50e24dcca9e"}


def uuid(value: str) -> str:
    """A full 128-bit UUID from a short one (``"2a37"``, ``"0x180D"``), a name from ``KNOWN`` or a full one."""
    text = KNOWN.get(str(value).strip().lower().replace(" ", "_"), str(value).strip().lower())
    text = text[2:] if text.startswith("0x") else text
    if re.fullmatch(r"[0-9a-f]{4}", text):
        return f"0000{text}-0000-1000-8000-00805f9b34fb"
    if re.fullmatch(r"[0-9a-f]{8}", text):
        return f"{text}-0000-1000-8000-00805f9b34fb"
    return text


def _bleak() -> Any:
    try:
        import bleak
    except ImportError:
        raise OSError(INSTALL) from None
    return bleak


def _uuids(value: Union[str, Sequence[str], None]) -> List[str]:
    if not value:
        return []
    items = re.split(r"[,\s]+", value) if isinstance(value, str) else list(value)
    return [uuid(i) for i in items if str(i).strip()]


@dataclass(frozen=True)
class BleDevice:
    """A Bluetooth LE device seen while scanning."""

    address: str
    name: str = ""
    #: Signal strength in dBm (closer to 0 is nearer).
    rssi: int = 0
    #: The services it advertises.
    uuids: tuple = ()
    manufacturer_data: Dict[int, bytes] = field(default_factory=dict, compare=False, hash=False)
    service_data: Dict[str, bytes] = field(default_factory=dict, compare=False, hash=False)

    @property
    def label(self) -> str:
        return self.name or self.address


@dataclass(frozen=True)
class BleNotification:
    """A value a device sent on a characteristic it notifies."""

    uuid: str
    data: bytes

    @property
    def text(self) -> str:
        return text_of(self.data)

    @property
    def value(self) -> Any:
        """What the data looks like: one byte is a number (a battery level...), readable text is parsed as JSON or
        kept as text, and other data of up to eight bytes is a little-endian number (how BLE sends them)."""
        text = self.text
        if len(self.data) == 1 or (not (text and text.isprintable()) and len(self.data) <= 8):
            return int.from_bytes(self.data, "little")
        try:
            return _json.loads(text)
        except ValueError:
            return text


class BluetoothScanner(Service):
    """Looks for Bluetooth LE devices nearby for ``timeout`` milliseconds.

    ``match`` keeps the devices whose name or address contains it, ``services`` the ones
    that advertise those UUIDs (``"heart_rate"``, ``"180d"``...). ``scan()`` looks once and
    ``start()`` again every ``interval`` milliseconds. ``devices`` holds what was found,
    nearest first.

    Events:
        ``on_found(value)``: Callable that receives each new ``BleDevice``.
        ``on_change(value)``: Callable that receives the list of devices when it changes.
        ``on_done(value)``: Callable that receives the list of devices when a scan ends.
        ``on_failed(value)``: Callable that receives why it could not scan (no adapter, no ``bleak``...).
    """

    events = ("found", "change", "done", "failed")

    def __init__(self, *, match: str = "", services: Union[str, Sequence[str], None] = None, timeout: float = 5000,
                 interval: float = 0, on_found: Optional[Handler] = None, on_change: Optional[Handler] = None,
                 on_done: Optional[Handler] = None, on_failed: Optional[Handler] = None) -> None:
        super().__init__(on_found=on_found, on_change=on_change, on_done=on_done, on_failed=on_failed)
        self.match = match
        self.services = services
        self.timeout = timeout
        self.interval = interval
        self._found: Dict[str, BleDevice] = {}
        self._busy = threading.Lock()
        self._stop = threading.Event()
        self._stop.set()

    @property
    def devices(self) -> List[BleDevice]:
        return sorted(self._found.values(), key=lambda d: -d.rssi)

    @property
    def scanning(self) -> bool:
        return self._busy.locked()

    def _wanted(self, device: BleDevice) -> bool:
        match = (self.match or "").lower()
        if match and match not in device.name.lower() and match not in device.address.lower():
            return False
        services = _uuids(self.services)
        return not services or bool(set(services) & {u.lower() for u in device.uuids})

    def _seen(self, device: Any, advertisement: Any) -> None:
        found = BleDevice(str(device.address), getattr(advertisement, "local_name", None) or device.name or "",
                          int(getattr(advertisement, "rssi", 0) or 0),
                          tuple(getattr(advertisement, "service_uuids", ()) or ()),
                          dict(getattr(advertisement, "manufacturer_data", {}) or {}),
                          dict(getattr(advertisement, "service_data", {}) or {}))
        if not self._wanted(found):
            return
        new = found.address not in self._found
        self._found[found.address] = found
        if new:
            self.emit("found", found)
            self.emit("change", self.devices)

    async def _scan_async(self) -> None:
        import asyncio

        bleak = _bleak()
        scanner = bleak.BleakScanner(detection_callback=self._seen)
        await scanner.start()
        try:
            await asyncio.sleep(max(float(self.timeout or 0), 500) / 1000)
        finally:
            await scanner.stop()

    def _scan(self) -> None:
        if not self._busy.acquire(blocking=False):
            return
        try:
            _async.run(self._scan_async())
        except Exception as error:  # noqa: BLE001 - no adapter, Bluetooth off, no permission...
            self.emit("failed", str(error) or type(error).__name__)
        else:
            self.emit("done", self.devices)
        finally:
            self._busy.release()

    def scan(self, wait: bool = False) -> List[BleDevice]:
        """Scans once (in the background unless ``wait``); returns the devices found so far."""
        if wait:
            self._scan()
        elif not self.scanning:
            threading.Thread(target=self._scan, name="pyzed-ble-scan", daemon=True).start()
        return self.devices

    @property
    def running(self) -> bool:
        return not self._stop.is_set()

    @running.setter
    def running(self, value: bool) -> None:
        if value and not self.running:
            self.start()
        elif not value:
            self.stop()

    def start(self) -> None:
        """Scans now and, with ``interval`` above 0, again every ``interval`` milliseconds."""
        self.stop()
        self._stop.clear()

        def loop() -> None:
            while not self._stop.is_set():
                self._scan()
                if float(self.interval or 0) <= 0 or self._stop.wait(float(self.interval) / 1000):
                    break
            self._stop.set()

        threading.Thread(target=loop, name="pyzed-ble-scan", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def clear(self) -> None:
        self._found.clear()


class BluetoothDevice(Connection):
    """A connection to one Bluetooth LE device: read, write and get notified of its characteristics.

    ``address`` names it (``"AA:BB:CC:DD:EE:FF"``, or a UUID on macOS); without one, the
    first device whose name contains ``name`` is used. ``notify`` lists the characteristics
    to follow once connected; every value they send raises ``notification`` with a
    ``BleNotification`` (``uuid``, ``data``, ``text``, ``value``). UUIDs can be short
    (``"2a37"``) or names from ``KNOWN`` (``"heart_rate_measurement"``)::

        strap = pz.BluetoothDevice(name="Polar", notify="heart_rate_measurement",
                                   on_notification=lambda n: print(n.data[1], "bpm"))
        strap.connect()

    ``read(uuid)`` and ``write(uuid, data)`` block until the device answers; call them from
    a handler or a ``pz.Worker``.

    Events:
        ``on_connected()``: The device is connected.
        ``on_disconnected()``: The device disconnected (or went out of range).
        ``on_failed(value)``: Callable that receives why it could not connect.
        ``on_notification(value)``: Callable that receives each ``BleNotification``.
    """

    events = ("connected", "disconnected", "failed", "notification")
    _thread_name = "pyzed-ble"

    def __init__(self, address: str = "", *, name: str = "", notify: Union[str, Sequence[str], None] = None,
                 timeout: float = 10000, reconnect: float = 0, on_connected: Optional[Handler] = None,
                 on_disconnected: Optional[Handler] = None, on_failed: Optional[Handler] = None,
                 on_notification: Optional[Handler] = None) -> None:
        super().__init__(reconnect=reconnect, on_connected=on_connected, on_disconnected=on_disconnected,
                         on_failed=on_failed, on_notification=on_notification)
        self.address = address
        self.name = name
        self.notify = notify
        self.timeout = timeout
        #: The last value of each characteristic that notified.
        self.last: Dict[str, BleNotification] = {}
        self._client: Optional[Any] = None
        self._gone = threading.Event()
        self._following: List[str] = []

    # -- connection --------------------------------------------------------------------------------------------
    async def _connect_async(self) -> Any:
        bleak = _bleak()
        seconds = max(float(self.timeout or 0), 1000) / 1000
        target: Any = self.address
        if not target:
            if not self.name:
                raise OSError("no device: set address or name")
            wanted = self.name.lower()
            target = await bleak.BleakScanner.find_device_by_filter(
                lambda d, adv: wanted in ((getattr(adv, "local_name", None) or d.name or "").lower()), timeout=seconds)
            if target is None:
                raise OSError(f"no Bluetooth device named {self.name!r} is nearby")
        client = bleak.BleakClient(target, disconnected_callback=lambda _: self._gone.set(), timeout=seconds)
        await client.connect()
        return client

    def _open(self) -> None:
        self._gone.clear()
        self._client = _async.run(self._connect_async())

    def _on_open(self) -> None:
        for characteristic in list(dict.fromkeys(_uuids(self.notify) + self._following)):
            self._start_notify(characteristic)

    def _serve(self) -> None:
        while not self._stop.is_set() and not self._gone.wait(0.2):
            pass

    def _close(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            try:
                _async.run(client.disconnect())
            except Exception:  # noqa: BLE001 - it is gone already
                pass

    # -- characteristics ---------------------------------------------------------------------------------------
    def _need(self) -> Any:
        if self._client is None:
            raise OSError("the device is not connected")
        return self._client

    def _start_notify(self, characteristic: str) -> None:
        def received(_: Any, data: bytearray, key: str = characteristic) -> None:
            note = BleNotification(key, bytes(data))
            self.last[key] = note
            self.emit("notification", note)

        _async.run(self._need().start_notify(characteristic, received))

    def subscribe(self, characteristic: str) -> None:
        """Follows ``characteristic`` (now if connected, and after every reconnection)."""
        key = uuid(characteristic)
        if key not in self._following:
            self._following.append(key)
        if self.connected:
            self._start_notify(key)

    def unsubscribe(self, characteristic: str) -> None:
        key = uuid(characteristic)
        if key in self._following:
            self._following.remove(key)
        if self.connected:
            _async.run(self._need().stop_notify(key))

    def read(self, characteristic: str) -> bytes:
        """The value of ``characteristic`` (blocks until the device answers)."""
        return bytes(_async.run(self._need().read_gatt_char(uuid(characteristic))))

    def write(self, characteristic: str, data: Any, response: bool = False) -> None:
        """Writes ``data`` (bytes, text, a number as one byte, or JSON) to ``characteristic``; ``response`` waits
        for the device to confirm."""
        payload = bytes([data & 0xFF]) if isinstance(data, int) and not isinstance(data, bool) else bytes_of(data)
        _async.run(self._need().write_gatt_char(uuid(characteristic), payload, response=response))

    def services(self) -> List[Dict[str, Any]]:
        """The device's services and their characteristics: ``[{"uuid", "description", "characteristics":
        [{"uuid", "description", "properties"}]}]``."""
        client = self._need()
        return [{"uuid": s.uuid, "description": getattr(s, "description", ""),
                 "characteristics": [{"uuid": c.uuid, "description": getattr(c, "description", ""),
                                      "properties": list(getattr(c, "properties", []))} for c in s.characteristics]}
                for s in client.services]
