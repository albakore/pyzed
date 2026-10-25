"""Finding devices on the local network: mDNS/Bonjour (DNS-SD) and SSDP/UPnP, with no dependencies."""

from __future__ import annotations

import re
import socket
import struct
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..services import Handler, Service

__all__ = ["Device", "DeviceDiscovery", "resolve_local"]

MDNS = ("224.0.0.251", 5353)
SSDP = ("239.255.255.250", 1900)
_PTR, _A, _TXT, _AAAA, _SRV = 12, 1, 16, 28, 33
_ALL_SERVICES = "_services._dns-sd._udp.local"


@dataclass(frozen=True)
class Device:
    """A device found on the network."""

    #: Its name: the Bonjour instance (``"Living room"``) or the UPnP friendly name.
    name: str
    #: Its IP address.
    host: str
    port: int = 0
    #: ``"mdns"`` or ``"ssdp"``.
    kind: str = "mdns"
    #: The service type (``"_http._tcp"``, ``"_googlecast._tcp"``...) or the UPnP device type.
    service: str = ""
    #: Its network name (``"esp32-4f2a.local"``), when it has one.
    hostname: str = ""
    #: The TXT record of an mDNS service, or the maker and model of a UPnP device.
    properties: Dict[str, str] = field(default_factory=dict, compare=False, hash=False)
    #: A UPnP device's description address (``LOCATION``).
    url: str = ""
    #: What identifies it between scans.
    id: str = ""  # noqa: A003

    @property
    def address(self) -> str:
        """``host:port`` (just ``host`` without a port)."""
        return f"{self.host}:{self.port}" if self.port else self.host


# -- DNS messages -------------------------------------------------------------------------------------------------
def _encode_name(name: str) -> bytes:
    out = b""
    for label in name.strip(".").split("."):
        data = label.encode("utf-8")
        out += bytes([len(data)]) + data
    return out + b"\0"


def query(name: str, kind: int = _PTR) -> bytes:
    """An mDNS question for ``name`` (a one-shot query, answered straight to the asking port)."""
    return struct.pack("!6H", 0, 0, 1, 0, 0, 0) + _encode_name(name) + struct.pack("!2H", kind, 1)


def _read_name(data: bytes, offset: int) -> Tuple[str, int]:
    labels, end, jumps = [], None, 0
    while True:
        if offset >= len(data):
            raise ValueError("truncated name")
        size = data[offset]
        if size & 0xC0 == 0xC0:
            if end is None:
                end = offset + 2
            offset = ((size & 0x3F) << 8) | data[offset + 1]
            jumps += 1
            if jumps > 32:
                raise ValueError("a loop in a name")
            continue
        if size == 0:
            return ".".join(labels), (end if end is not None else offset + 1)
        labels.append(data[offset + 1:offset + 1 + size].decode("utf-8", "replace"))
        offset += 1 + size


def parse(data: bytes) -> List[Tuple[str, int, Any]]:
    """The records of a DNS message: ``(name, type, value)``; values are a name (PTR), ``(port, target)``
    (SRV), a dict (TXT) or an address (A, AAAA)."""
    _, _, questions, answers, authority, additional = struct.unpack("!6H", data[:12])
    offset, out = 12, []
    for _ in range(questions):
        _, offset = _read_name(data, offset)
        offset += 4
    for _ in range(answers + authority + additional):
        name, offset = _read_name(data, offset)
        kind, _, _, size = struct.unpack("!HHIH", data[offset:offset + 10])
        offset += 10
        rdata, start = data[offset:offset + size], offset
        offset += size
        if kind == _PTR:
            out.append((name, kind, _read_name(data, start)[0]))
        elif kind == _SRV:
            port = struct.unpack("!H", rdata[4:6])[0]
            out.append((name, kind, (port, _read_name(data, start + 6)[0])))
        elif kind == _TXT:
            props, i = {}, 0
            while i < len(rdata):
                item = rdata[i + 1:i + 1 + rdata[i]].decode("utf-8", "replace")
                i += 1 + rdata[i]
                if item:
                    key, _, value = item.partition("=")
                    props[key] = value
            out.append((name, kind, props))
        elif kind == _A and size == 4:
            out.append((name, kind, socket.inet_ntoa(rdata)))
        elif kind == _AAAA and size == 16:
            out.append((name, kind, socket.inet_ntop(socket.AF_INET6, rdata)))
    return out


def _local(name: str) -> str:
    return name if name.endswith(".local") else f"{name.strip('.')}.local"


def _udp(ttl: int = 255) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
    sock.bind(("", 0))
    return sock


def _collect(sock: socket.socket, seconds: float) -> List[Tuple[bytes, str]]:
    end, out = time.monotonic() + seconds, []
    while True:
        left = end - time.monotonic()
        if left <= 0:
            return out
        sock.settimeout(left)
        try:
            data, sender = sock.recvfrom(9000)
        except (socket.timeout, OSError):
            return out
        out.append((data, sender[0]))


def resolve_local(name: str, timeout: float = 1.5, address: Tuple[str, int] = MDNS) -> Optional[str]:
    """The IP address of a ``.local`` name (``"raspberrypi.local"``, ``"esp32"``) asked over mDNS, or ``None``."""
    target = _local(name).lower()
    sock = _udp()
    try:
        sock.sendto(query(target, _A), address)
        for data, _ in _collect(sock, timeout):
            try:
                records = parse(data)
            except (ValueError, struct.error, IndexError):
                continue
            for record_name, kind, value in records:
                if kind == _A and record_name.lower() == target:
                    return value
    finally:
        sock.close()
    return None


# -- the service ----------------------------------------------------------------------------------------------
class DeviceDiscovery(Service):
    """Finds the devices of the local network: printers, Chromecasts, ESPHome boards, routers, smart TVs...

    It asks with mDNS/Bonjour for ``service`` (``"_http._tcp"``, ``"_esphomelib._tcp"``,
    ``"_ipp._tcp"``...; empty: every service) and, with ``ssdp``, with UPnP for
    ``search_target`` (``"ssdp:all"``). Answers are collected for ``timeout`` milliseconds;
    ``scan()`` asks once, ``start()`` again every ``interval`` milliseconds. ``devices``
    holds what was found; a device that stops answering for two scans raises ``lost``::

        finder = pz.DeviceDiscovery("_http._tcp", on_found=lambda d: print(d.name, d.address))
        finder.scan()

    Events:
        ``on_found(value)``: Callable that receives each new ``Device``.
        ``on_lost(value)``: Callable that receives a ``Device`` that stopped answering.
        ``on_change(value)``: Callable that receives the list of devices after a scan that changed it.
        ``on_done(value)``: Callable that receives the list of devices at the end of every scan.
    """

    events = ("found", "lost", "change", "done")

    def __init__(self, service: str = "", *, mdns: bool = True, ssdp: bool = True, search_target: str = "ssdp:all",
                 describe: bool = True, timeout: float = 2000, interval: float = 30000,
                 on_found: Optional[Handler] = None, on_lost: Optional[Handler] = None,
                 on_change: Optional[Handler] = None, on_done: Optional[Handler] = None) -> None:
        super().__init__(on_found=on_found, on_lost=on_lost, on_change=on_change, on_done=on_done)
        self.service = service
        self.mdns = mdns
        self.ssdp = ssdp
        self.search_target = search_target
        #: Read each UPnP device's description for its name, maker and model.
        self.describe = describe
        self.timeout = timeout
        self.interval = interval
        self.mdns_address = MDNS
        self.ssdp_address = SSDP
        self._found: Dict[str, Device] = {}
        self._missed: Dict[str, int] = {}
        self._descriptions: Dict[str, Dict[str, str]] = {}
        self._scanning = threading.Lock()
        self._stop = threading.Event()
        self._stop.set()
        self._thread: Optional[threading.Thread] = None

    @property
    def devices(self) -> List[Device]:
        """The devices found, by name."""
        return sorted(self._found.values(), key=lambda d: (d.name.lower(), d.host))

    @property
    def scanning(self) -> bool:
        return self._scanning.locked()

    # -- scanning ----------------------------------------------------------------------------------------------
    def scan(self, wait: bool = False) -> List[Device]:
        """Asks the network once (in the background, unless ``wait``); returns the devices known so far."""
        if wait:
            self._scan()
        elif not self.scanning:
            threading.Thread(target=self._scan, name="pyzed-discovery", daemon=True).start()
        return self.devices

    def _scan(self) -> None:
        if not self._scanning.acquire(blocking=False):
            return
        try:
            seconds = max(float(self.timeout or 0), 100) / 1000
            seen: Dict[str, Device] = {}
            threads = []
            if self.mdns:
                threads.append(threading.Thread(target=lambda: seen.update(self._mdns(seconds)), daemon=True))
            if self.ssdp:
                threads.append(threading.Thread(target=lambda: seen.update(self._ssdp(seconds)), daemon=True))
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self._merge(seen)
        finally:
            self._scanning.release()

    def _merge(self, seen: Dict[str, Device]) -> None:
        changed = False
        for key, device in seen.items():
            self._missed[key] = 0
            if key not in self._found:
                self._found[key] = device
                changed = True
                self.emit("found", device)
            elif self._found[key] != device:
                self._found[key] = device
                changed = True
        for key in list(self._found):
            if key not in seen:
                self._missed[key] = self._missed.get(key, 0) + 1
                if self._missed[key] >= 2:
                    device = self._found.pop(key)
                    self._missed.pop(key, None)
                    changed = True
                    self.emit("lost", device)
        devices = self.devices
        if changed:
            self.emit("change", devices)
        self.emit("done", devices)

    def _mdns(self, seconds: float) -> Dict[str, Device]:
        sock = _udp()
        try:
            types = [_local(t.strip()) for t in re.split(r"[,\s]+", self.service or "") if t.strip()]
            if not types:
                sock.sendto(query(_ALL_SERVICES), self.mdns_address)
                answers = _collect(sock, min(seconds / 2, 1.0))
                for data, _ in answers:
                    try:
                        types += [v for n, k, v in parse(data) if k == _PTR and n.lower() == _ALL_SERVICES]
                    except (ValueError, struct.error, IndexError):
                        continue
                types = list(dict.fromkeys(types))
                seconds = max(seconds - min(seconds / 2, 1.0), 0.3)
            for kind in types:
                sock.sendto(query(kind), self.mdns_address)
            records: List[Tuple[str, int, Any, str]] = []
            for data, sender in _collect(sock, seconds):
                try:
                    records += [(n, k, v, sender) for n, k, v in parse(data)]
                except (ValueError, struct.error, IndexError):
                    continue
        finally:
            sock.close()
        wanted = {t.lower() for t in types}
        instances = {(v, n) for n, k, v, _ in records if k == _PTR and n.lower() in wanted}
        srv = {n.lower(): v for n, k, v, _ in records if k == _SRV}
        txt = {n.lower(): v for n, k, v, _ in records if k == _TXT}
        addresses: Dict[str, str] = {}
        for n, k, v, _ in records:
            if k == _A or (k == _AAAA and n.lower() not in addresses):
                addresses[n.lower()] = v
        senders = {n.lower(): s for n, _, _, s in records}
        out: Dict[str, Device] = {}
        for instance, kind in instances:
            port, target = srv.get(instance.lower(), (0, ""))
            host = addresses.get(target.lower()) or senders.get(instance.lower(), "")
            label = instance[:-len(kind) - 1] if instance.lower().endswith("." + kind.lower()) else instance
            service = kind[:-len(".local")] if kind.endswith(".local") else kind
            key = f"mdns:{instance.lower()}"
            out[key] = Device(label, host, port, "mdns", service, target.rstrip("."),
                              dict(txt.get(instance.lower(), {})), "", key)
        return out

    def _ssdp(self, seconds: float) -> Dict[str, Device]:
        sock = _udp(2)
        try:
            mx = max(1, min(int(seconds), 5))
            message = ("M-SEARCH * HTTP/1.1\r\n"
                       f"HOST: {self.ssdp_address[0]}:{self.ssdp_address[1]}\r\n"
                       'MAN: "ssdp:discover"\r\n'
                       f"MX: {mx}\r\nST: {self.search_target or 'ssdp:all'}\r\n\r\n")
            sock.sendto(message.encode(), self.ssdp_address)
            answers = _collect(sock, seconds)
        finally:
            sock.close()
        locations = set()
        for data, _ in answers:
            match = re.search(rb"(?im)^location:\s*(\S+)", data)
            if match:
                locations.add(match.group(1).decode("utf-8", "replace"))
        if self.describe and locations:  # every description at once: a slow device does not hold up the rest
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=min(8, len(locations))) as pool:
                list(pool.map(self._description, locations))
        out: Dict[str, Device] = {}
        for data, sender in answers:
            headers: Dict[str, str] = {}
            for line in data.decode("utf-8", "replace").split("\r\n")[1:]:
                name, _, value = line.partition(":")
                if value:
                    headers[name.strip().lower()] = value.strip()
            usn = headers.get("usn", "")
            uuid = usn.split("::")[0] or headers.get("location", sender)
            key = f"ssdp:{uuid.lower()}"
            location = headers.get("location", "")
            previous = out.get(key)
            target = headers.get("st", "")
            # Several answers per device (one per service): keep the one naming the device itself.
            if previous is not None and not target.startswith("urn:schemas-upnp-org:device:"):
                continue
            info = self._description(location) if self.describe and location else {}
            match = re.match(r"https?://([^/:]+)(?::(\d+))?", location)
            host = match.group(1) if match else sender
            port = int(match.group(2)) if match and match.group(2) else 0
            properties = {k: v for k, v in info.items() if k != "friendlyName"}
            if headers.get("server"):
                properties.setdefault("server", headers["server"])
            out[key] = Device(info.get("friendlyName") or headers.get("server") or host, host, port, "ssdp",
                              info.get("deviceType", target), "", properties, location, key)
        return out

    def _description(self, url: str) -> Dict[str, str]:
        if url in self._descriptions:
            return self._descriptions[url]
        import urllib.request

        info: Dict[str, str] = {}
        try:
            with urllib.request.urlopen(url, timeout=2) as answer:  # noqa: S310 - a device's own address
                xml = answer.read(65536).decode("utf-8", "replace")
            for tag in ("friendlyName", "manufacturer", "modelName", "modelNumber", "deviceType", "presentationURL"):
                match = re.search(rf"<{tag}>([^<]*)</{tag}>", xml)
                if match:
                    info[tag] = match.group(1).strip()
        except (OSError, ValueError):
            pass
        self._descriptions[url] = info
        return info

    # -- running -----------------------------------------------------------------------------------------------
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
        """Scans now and then every ``interval`` milliseconds."""
        self.stop()
        self._stop.clear()

        def loop() -> None:
            while not self._stop.is_set():
                self._scan()
                if self._stop.wait(max(float(self.interval or 0), 1000) / 1000):
                    break

        self._thread = threading.Thread(target=loop, name="pyzed-discovery", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def clear(self) -> None:
        """Forgets the devices found."""
        self._found.clear()
        self._missed.clear()
