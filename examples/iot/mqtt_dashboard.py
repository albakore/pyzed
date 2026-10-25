"""A home dashboard over MQTT: sensor tiles that update live and a lamp switch that publishes.

    python examples/iot/mqtt_dashboard.py                      # a local broker and simulated sensors
    python examples/iot/mqtt_dashboard.py --broker 192.168.1.5 # your own broker (Mosquitto, Home Assistant...)

The app subscribes to ``home/#``: every ``home/<room>/<sensor>`` message updates a tile with the
value and its history. Turning the lamp on publishes ``home/lamp/set``. Without ``--broker`` it
starts the small test broker of ``pyzed.iot.testing`` and a thread that publishes like sensors
would, so it runs on any computer.
"""

import argparse
import math
import random
import threading
import time

import pyzed as pz
from pyzed import ui

UNITS = {"temperature": "°C", "humidity": "%", "co2": "ppm", "power": "W"}
ICONS = {"temperature": "thermometer", "humidity": "droplets", "co2": "wind", "power": "zap"}


def simulate(broker, stop: threading.Event) -> None:
    """Sensors in three rooms, publishing every half a second like an ESP32 with a DHT22 would."""
    step = 0
    while not stop.wait(0.5):
        step += 1
        wave = math.sin(step / 12)
        broker.publish("home/living/temperature", f"{21.5 + wave + random.uniform(-0.1, 0.1):.1f}")
        broker.publish("home/living/humidity", f"{45 + 4 * wave:.0f}")
        broker.publish("home/office/co2", f"{620 + 180 * (1 + wave) + random.uniform(-15, 15):.0f}")
        broker.publish("home/office/temperature", f"{23.0 - wave / 2:.1f}")
        broker.publish("home/kitchen/power", f"{140 + 900 * max(0.0, math.sin(step / 7)):.0f}")


class Dashboard(pz.App):
    title = "Home over MQTT"
    size = (860, 540)

    def __init__(self, host: str, port: int = 0):
        self.readings = {}  # (room, sensor) -> list of values
        self.lamp = False
        self.status = "Connecting…"
        self.mqtt = pz.MqttClient(host, port, subscribe="home/#", will_topic="home/dashboard", will_message="offline",
                                  on_message=self.received, on_connected=self.connected,
                                  on_disconnected=lambda: self.set_status("Disconnected, retrying…"),
                                  on_failed=lambda reason: self.set_status(f"No broker: {reason}"))
        self.mqtt.connect()

    def set_status(self, text):
        self.status = text

    def connected(self):
        self.status = f"Connected to {self.mqtt.host}:{self.mqtt.broker_port}"
        self.mqtt.publish("home/dashboard", "online", retain=True)

    def received(self, message):
        parts = message.topic.split("/")
        if len(parts) != 3 or not isinstance(message.value, (int, float)):
            return
        key = (parts[1], parts[2])
        self.readings[key] = (self.readings.get(key, []) + [float(message.value)])[-40:]

    def toggle_lamp(self, on):
        self.lamp = on
        self.mqtt.publish("home/lamp/set", "on" if on else "off", qos=1)

    def on_close(self):
        self.mqtt.disconnect()

    def tile(self, room, sensor, values, t):
        unit = UNITS.get(sensor, "")
        delta = values[-1] - values[0] if len(values) > 1 else None
        return ui.card(pz.column([
            pz.row([pz.icon(ICONS.get(sensor, "activity"), size=16, color=t.text_muted),
                    ui.label(f"{room.title()} · {sensor}", size="sm", color="text_muted", theme=t), pz.hspace(),
                    ui.badge(f"{delta:+.1f}" if delta is not None else "new", size="sm",
                             tint="success" if (delta or 0) <= 0 else "warning", theme=t)],
                   spacing=6, align="center"),
            ui.label(f"{values[-1]:g} {unit}", size=26, weight="semibold", theme=t),
            ui.sparkline(values, width=220, height=36, theme=t),
        ], spacing=8), width="fill", theme=t)

    def view(self):
        t = self.resolved_theme()
        tiles = [self.tile(room, sensor, values, t) for (room, sensor), values in sorted(self.readings.items())]
        rows = [pz.row(tiles[i:i + 3], spacing=12) for i in range(0, len(tiles), 3)]
        online = self.mqtt.connected
        body = pz.column(rows, spacing=12) if rows else ui.empty_state(
            "Waiting for sensors", "Messages on home/<room>/<sensor> show up here.", icon="radio-tower", theme=t)
        return pz.container(pz.column([
            pz.row([ui.heading("Home", level=2, theme=t), pz.hspace(),
                    ui.badge("online" if online else "offline", tint="success" if online else "error",
                             icon="radio-tower", theme=t)], align="center"),
            ui.muted(self.status, size="sm"),
            body,
            pz.vspace(),
            ui.card(pz.row([pz.icon("lamp", size=18, color=t.text), ui.label("Lamp", weight="medium", theme=t), pz.hspace(),
                            ui.switch(self.lamp, self.toggle_lamp, theme=t)], spacing=8, align="center"),
                    theme=t),
        ], spacing=14), padding=24, width="fill", height="fill", bg=t.background)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--broker", help="the broker's address (default: a local test broker with fake sensors)")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    if args.broker:
        Dashboard(args.broker, args.port).run()
        return
    from pyzed.iot.testing import MqttBroker

    stop = threading.Event()
    with MqttBroker() as broker:
        threading.Thread(target=simulate, args=(broker, stop), daemon=True).start()
        time.sleep(0.05)
        try:
            Dashboard("127.0.0.1", broker.port).run()
        finally:
            stop.set()


if __name__ == "__main__":
    main()
