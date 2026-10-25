"""A serial monitor, like Arduino's: pick a port, read what the board prints and send it commands.

    python examples/iot/serial_monitor.py           # your boards (Arduino, ESP32, Pico, USB adapters...)
    python examples/iot/serial_monitor.py --demo    # a simulated board (Linux and macOS)

A ``SerialWatcher`` keeps the list of ports up to date as boards are plugged in and out, and
the ``SerialPort`` reads line by line. With ``--demo`` a thread plays a board on a virtual
serial cable: it prints a reading every half a second and answers ``LED ON``/``LED OFF``.
"""

import argparse
import math
import os
import threading
import time

import pyzed as pz
from pyzed import ui

SPEEDS = ["9600", "19200", "38400", "57600", "115200"]


def fake_board(fd: int) -> None:
    """A board on the other end of the cable: it prints readings and answers commands."""
    led, step, buffer = False, 0, b""
    os.write(fd, b"Booting sensor board v1.2\r\n")
    while True:
        step += 1
        os.write(fd, f"t={22 + math.sin(step / 6):.2f} h={48 + 3 * math.cos(step / 9):.1f} led={int(led)}\r\n"
                 .encode())
        end = time.monotonic() + 0.5
        while time.monotonic() < end:
            import select

            if select.select([fd], [], [], 0.05)[0]:
                buffer += os.read(fd, 64)
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    command = line.strip().decode().upper()
                    if command in ("LED ON", "LED OFF"):
                        led = command == "LED ON"
                        os.write(fd, f"OK {command}\r\n".encode())
                    elif command:
                        os.write(fd, f"ERR unknown command: {command}\r\n".encode())


class Monitor(pz.App):
    title = "Serial monitor"
    size = (820, 520)

    def __init__(self, extra_port: str = ""):
        self.extra = extra_port  # the demo's virtual port, which no system lists
        self.lines = []
        self.command = ""
        self.speed = "115200"
        self.port = pz.SerialPort(reconnect=1000, on_line=self.received, on_connected=self.opened,
                                  on_disconnected=lambda: self.note("— port closed"),
                                  on_failed=lambda reason: self.note(f"— {reason}"))
        # a handler, so the window redraws with the new list when a board is plugged in or out
        self.watcher = pz.SerialWatcher(on_change=lambda ports: None)
        self.watcher.start()
        self.choice = self.extra or next((p.name for p in self.watcher.ports), "")

    def note(self, text):
        self.lines = (self.lines + [text])[-500:]

    def received(self, line):
        self.note(line)

    def opened(self):
        self.note(f"— connected to {self.port.path} at {self.port.baud_rate} baud")

    def ports(self):
        names = [p.name for p in self.watcher.ports]
        return ([self.extra] if self.extra else []) + names

    def toggle(self):
        if self.port.running:
            self.port.disconnect()
            return
        self.port.port = self.choice
        self.port.baud_rate = int(self.speed)
        self.port.connect()

    def send(self, *_):
        if self.command and self.port.send_line(self.command):
            self.note(f"> {self.command}")
            self.command = ""

    def on_close(self):
        self.port.disconnect()
        self.watcher.stop()

    def view(self):
        t = self.resolved_theme()
        running = self.port.running
        names = self.ports()
        toolbar = pz.row([
            ui.select(names, self.choice or None, lambda v: setattr(self, "choice", v),
                      placeholder="No serial ports", width=240, disabled=running, theme=t),
            ui.select(SPEEDS, self.speed, lambda v: setattr(self, "speed", v), width=110, disabled=running,
                      theme=t),
            ui.button("Disconnect" if running else "Connect", self.toggle, icon="unplug" if running else "plug",
                      variant="outline" if running else "filled", disabled=not self.choice, theme=t),
            pz.hspace(),
            ui.badge("connected" if self.port.connected else "closed",
                     tint="success" if self.port.connected else "neutral", icon="usb", theme=t),
        ], spacing=8, align="center")
        return pz.container(pz.column([
            toolbar,
            pz.container(ui.terminal(self.lines[-200:] or ["Pick a port and press Connect."], id="serial-log",
                                     theme=t), height="fill", width="fill"),
            pz.row([ui.input(self.command, lambda v: setattr(self, "command", v), placeholder="Send a line…",
                             on_submit=self.send, mono=True, disabled=not self.port.connected, theme=t),
                    ui.button("Send", self.send, icon="send", disabled=not self.port.connected, theme=t)],
                   spacing=8),
        ], spacing=12), padding=16, width="fill", height="fill", bg=t.background)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--demo", action="store_true", help="a simulated board on a virtual serial port")
    args = parser.parse_args()
    extra = ""
    if args.demo:
        from pyzed.iot.testing import serial_pair

        fd, extra = serial_pair()
        threading.Thread(target=fake_board, args=(fd,), daemon=True).start()
    Monitor(extra).run()


if __name__ == "__main__":
    main()
