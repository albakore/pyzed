"""What the IoT services share: a connection that runs in a thread of its own and comes back by itself."""

from __future__ import annotations

import threading
from typing import Any, Optional

from ..services import Handler, Service


def text_of(data: Any, encoding: str = "utf-8") -> str:
    """``data`` as text: bytes are decoded (bad bytes become ``\\ufffd``), anything else is ``str()``."""
    if isinstance(data, (bytes, bytearray, memoryview)):
        return bytes(data).decode(encoding or "utf-8", errors="replace")
    return "" if data is None else str(data)


def bytes_of(data: Any, encoding: str = "utf-8") -> bytes:
    """``data`` as bytes: text is encoded, numbers and other values go as their text, dicts and lists as JSON."""
    if isinstance(data, (bytes, bytearray, memoryview)):
        return bytes(data)
    if isinstance(data, (dict, list, tuple, bool)) or data is None:
        import json

        return json.dumps(data).encode("utf-8")
    return str(data).encode(encoding or "utf-8")


class Connection(Service):
    """A service connected to a device or a server: ``connect()``, ``disconnect()`` and the events around them.

    The connection is made and read in a thread of its own. ``connected`` is raised once it is
    up, ``disconnected`` when it ends and ``failed`` (with the reason) when it could not be
    made or broke. With ``reconnect`` above 0 it tries again every ``reconnect`` milliseconds
    until ``disconnect()``. ``running`` is whether it is connected or trying to.

    Subclasses define ``_open()`` (connects, or raises), ``_serve()`` (reads until the
    connection ends) and ``_close()``.
    """

    events: tuple = ("connected", "disconnected", "failed")
    #: The thread's name.
    _thread_name = "pyzed-iot"

    def __init__(self, *, reconnect: float = 0, **handlers: Optional[Handler]) -> None:
        super().__init__(**handlers)
        #: Milliseconds between attempts to connect again after the connection fails or ends (0: never).
        self.reconnect = reconnect
        #: Why the last attempt failed (``""`` when it did not).
        self.error = ""
        self._up = False
        self._stop = threading.Event()
        self._stop.set()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

    # -- state -------------------------------------------------------------------------------------------------
    @property
    def connected(self) -> bool:
        """Whether the connection is up."""
        return self._up

    @property
    def running(self) -> bool:
        """Whether it is connected or trying to connect."""
        return not self._stop.is_set()

    @running.setter
    def running(self, value: bool) -> None:
        if value and not self.running:
            self.connect()
        elif not value:
            self.disconnect()

    # -- connecting --------------------------------------------------------------------------------------------
    def connect(self) -> bool:
        """Connects in the background; returns ``False`` when it is already connected or connecting."""
        if self.running:
            return False
        self.error = ""
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=self._thread_name, daemon=True)
        self._thread.start()
        return True

    def disconnect(self) -> None:
        """Closes the connection and stops trying to connect again."""
        if self._stop.is_set():
            return
        self._stop.set()
        try:
            self._close()
        except Exception:  # noqa: BLE001 - already closing
            pass
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)

    def stop(self) -> None:
        self.disconnect()

    def wait_connected(self, timeout: float = 5.0) -> bool:
        """Blocks until the connection is up (for scripts and tests); returns whether it is."""
        import time

        end = time.monotonic() + timeout
        while not self._up and self.running and time.monotonic() < end:
            time.sleep(0.01)
        return self._up

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._open()
            except Exception as error:  # noqa: BLE001 - every failure is reported the same way
                self._failed(error)
            else:
                if self._stop.is_set():
                    self._safe_close()
                    break
                self._up = True
                try:
                    self._on_open()
                    self.emit("connected")
                    self._serve()
                except Exception as error:  # noqa: BLE001
                    if not self._stop.is_set():
                        self._failed(error)
                finally:
                    self._up = False
                    self._safe_close()
                    self.emit("disconnected")
            delay = float(self.reconnect or 0)
            if delay <= 0 or self._stop.wait(max(delay, 50) / 1000):
                break
        self._stop.set()

    def _failed(self, error: BaseException) -> None:
        self.error = str(error) or type(error).__name__
        self.emit("failed", self.error)

    def _safe_close(self) -> None:
        try:
            self._close()
        except Exception:  # noqa: BLE001
            pass

    # -- for subclasses ----------------------------------------------------------------------------------------
    def _open(self) -> None:
        raise NotImplementedError

    def _on_open(self) -> None:
        """Called once the connection is up, before ``connected`` is raised."""

    def _serve(self) -> None:
        raise NotImplementedError

    def _close(self) -> None:
        pass


class LineSplitter:
    """Cuts a stream of bytes into lines: ``feed(data)`` returns the lines it completed, without ``\\r``/``\\n``."""

    def __init__(self, newline: str = "\n", encoding: str = "utf-8", limit: int = 1 << 16) -> None:
        self.newline = newline
        self.encoding = encoding
        self.limit = limit
        self._buffer = b""

    def feed(self, data: bytes) -> list:
        sep = (self.newline or "\n").encode(self.encoding or "utf-8")
        self._buffer += data
        *lines, self._buffer = self._buffer.split(sep)
        if len(self._buffer) > self.limit:  # a device that never ends its lines
            lines.append(self._buffer)
            self._buffer = b""
        return [text_of(line, self.encoding).rstrip("\r\n") for line in lines]

    def clear(self) -> None:
        self._buffer = b""
