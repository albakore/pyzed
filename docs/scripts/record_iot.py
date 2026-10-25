"""Records the animated WebP clips of the IoT pages (docs/public/media/iot/).

    python docs/scripts/record_iot.py             # every clip
    python docs/scripts/record_iot.py serial      # only the clips whose name contains a word
    python docs/scripts/record_iot.py --list      # what there is to record

Frames are drawn off-screen like ``record_services.py`` (no window, display or GPU). The devices
are made up and their messages are handed to the apps between frames, so every run gives the
same clip and none needs a network, a broker or a board. Needs ffmpeg and Pillow.
"""

from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("PYZED_CONFIG_DIR", tempfile.mkdtemp(prefix="pyzed-record-config-"))

import record  # noqa: E402
from record import DESIGNER_SIZE, Clip, Frame, _designer, glide  # noqa: E402
from record_services import TOOL_ROW, _tray_chip  # noqa: E402

ROOT = HERE.parents[1]
OUT = ROOT / "docs" / "public" / "media" / "iot"
EXAMPLES = ROOT / "examples" / "iot"
WIDTH = 960
CLIPS: dict[str, Clip] = {}
sys.path.insert(0, str(EXAMPLES))


def clip(name: str, title: str, *, fps: int = 20):
    def register(fn):
        CLIPS[name] = Clip(name, title, title, fps, fn)
        return fn
    return register


@clip("tray", "Adding an MQTT client and a serial port from the IoT category, then the message handler")
def tray_clip(c: Clip):
    work = Path(tempfile.mkdtemp(prefix="pyzed-record-"))
    app = _designer(work / "form1.pzform")
    app.doc.add("label", 24, 20, 240, 24)
    app.doc.form["label1"].props["text"] = "Temperature: --"
    app.doc.select(None)
    size = DESIGNER_SIZE
    pointer = (640.0, 500.0)
    yield Frame(app, size, pointer, hold=8)
    for query, type_ in (("mqtt", "mqtt_client"), ("serial", "serial_port")):
        target = (110.0, 117.0)
        for p in glide(pointer, target, 10):
            pointer = p
            yield Frame(app, size, pointer)
        typed = ""
        for ch in query:
            typed += ch
            app.set_toolbox_query(typed)
            yield Frame(app, size, pointer, hold=2)
        for p in glide(pointer, (70.0, TOOL_ROW), 8):
            pointer = p
            yield Frame(app, size, pointer)
        yield Frame(app, size, pointer, pressed=True, hold=3)
        app.pick_tool(type_)()
        app.toasts.clear()
        yield Frame(app, size, pointer, hold=10)
        app.set_toolbox_query("")
    chip = _tray_chip(app, 0)
    for p in glide(pointer, chip, 14):
        pointer = p
        yield Frame(app, size, pointer)
    app.press_tray("mqtt_client1")
    yield Frame(app, size, pointer, pressed=True, hold=3)
    yield Frame(app, size, pointer, hold=16)
    app.open_default_event("mqtt_client1")
    app.toasts.clear()
    yield Frame(app, size, pointer, pressed=True, hold=3)
    yield Frame(app, size, pointer, hold=c.fps * 2)


@clip("dashboard", "The MQTT dashboard example: sensor tiles updating as messages arrive")
def dashboard_clip(c: Clip):
    import mqtt_dashboard
    from pyzed.iot import MqttMessage

    app = mqtt_dashboard.Dashboard.__new__(mqtt_dashboard.Dashboard)
    app.readings, app.lamp = {}, False
    app.status = "Connected to broker.local:1883"

    class Online:  # stands in for the client: the clip hands the messages over itself
        connected = True

        def publish(self, *args, **kwargs):
            return True

    app.mqtt = Online()
    size = (860, 540)
    yield Frame(app, size, None, hold=6)
    for step in range(46):
        wave = math.sin(step / 6)
        for topic, value in (("home/living/temperature", f"{21.5 + wave:.1f}"),
                             ("home/living/humidity", f"{45 + 4 * wave:.0f}"),
                             ("home/office/co2", f"{620 + 180 * (1 + math.sin(step / 5)):.0f}"),
                             ("home/office/temperature", f"{23.0 - wave / 2:.1f}"),
                             ("home/kitchen/power", f"{140 + 900 * max(0.0, math.sin(step / 4)):.0f}")):
            app.received(MqttMessage(topic, value.encode()))
        if step == 30:
            app.lamp = True
        yield Frame(app, size, (790.0, 491.0) if 26 <= step <= 31 else None, pressed=step == 30, hold=3)
    yield Frame(app, size, None, hold=c.fps)


@clip("serial", "The serial monitor example reading a board and sending it a command")
def serial_clip(c: Clip):
    import serial_monitor

    app = serial_monitor.Monitor.__new__(serial_monitor.Monitor)
    app.extra, app.lines, app.command, app.speed, app.choice = "/dev/ttyACM0", [], "", "115200", "/dev/ttyACM0"

    class Port:  # an open port, as the clip tells it
        running = connected = True
        path, baud_rate = "/dev/ttyACM0", 115200

        def send_line(self, text):
            return True

    class Watcher:
        ports = []

    app.port, app.watcher = Port(), Watcher()
    app.note("— connected to /dev/ttyACM0 at 115200 baud")
    app.note("Booting sensor board v1.2")
    size = (820, 520)
    led = 0
    for step in range(36):
        app.note(f"t={22 + math.sin(step / 6):.2f} h={48 + 3 * math.cos(step / 9):.1f} led={led}")
        if step == 14:
            for ch in "LED ON":
                app.command += ch
                yield Frame(app, size, None, hold=2)
            app.send()
            app.note("OK LED ON")
            led = 1
        yield Frame(app, size, None, hold=6)
    yield Frame(app, size, None, hold=c.fps)


@clip("meter", "The Modbus energy meter example: polled values and a relay switched from the app")
def meter_clip(c: Clip):
    import modbus_meter

    app = modbus_meter.Meter.__new__(modbus_meter.Meter)
    app.values, app.history, app.status = {}, [], "Connected"
    size = (760, 420)
    energy, relay = 1520.0, True
    for step in range(60):
        if step == 40:
            relay = False
        volts = 230 + 2 * math.sin(step / 9)
        amps = (4.2 + 2.5 * math.sin(step / 6) + 0.3 * math.sin(step / 2)) if relay else 0.0
        energy += volts * amps / 1000 / 600
        app.updated({"voltage": volts, "current": amps, "power": volts * amps, "energy": energy, "relay": relay})
        yield Frame(app, size, (703.0, 326.0) if 36 <= step <= 41 else None, pressed=step == 40, hold=3)
    yield Frame(app, size, None, hold=c.fps)


@clip("scanner", "The network scanner example finding devices with mDNS and UPnP")
def scanner_clip(c: Clip):
    import network_scanner

    app = network_scanner.Scanner.__new__(network_scanner.Scanner)
    app.devices, app.log = [], "Scanning…"

    class Finder:
        scanning = True

    app.finder = Finder()
    size = (880, 520)
    yield Frame(app, size, None, hold=10)
    for device in network_scanner.DEMO:
        app.devices = sorted(app.devices + [device], key=lambda d: (d.name.lower(), d.host))
        app.log = f"found {device.name}"
        yield Frame(app, size, None, hold=8)
    app.finder.scanning = False
    app.log = f"{len(app.devices)} devices · scanning again every 15 s"
    yield Frame(app, size, None, hold=c.fps * 2)


def encode(c: Clip, folder: Path, frames: int) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{c.name}.webp"
    from PIL import Image

    with Image.open(folder / "00001.png") as im:
        width = min(WIDTH, im.width)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(c.fps), "-i", str(folder / "%05d.png"),
                    "-vf", f"scale={width - width % 2}:-2:flags=lanczos", "-c:v", "libwebp_anim", "-q:v", "70",
                    "-compression_level", "6", "-loop", "0", "-an", str(out)], check=True)
    print(f"  {out.relative_to(ROOT)}: {frames} frames, {out.stat().st_size / 1000:.0f} KB")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("names", nargs="*")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    for c in CLIPS.values():
        if args.list:
            print(f"{c.name:10} {c.title}")
            continue
        if args.names and not any(n in c.name for n in args.names):
            continue
        print(f"recording {c.name}")
        folder = Path(tempfile.mkdtemp(prefix=f"pyzed-{c.name}-"))
        try:
            encode(c, folder, record.render_offscreen(c, folder))
        finally:
            shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    main()
