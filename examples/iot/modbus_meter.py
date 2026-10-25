"""An energy meter over Modbus: live voltage, current and power, and a relay you switch from the app.

    python examples/iot/modbus_meter.py                        # a simulated meter on this computer
    python examples/iot/modbus_meter.py --host 192.168.1.40    # a real Modbus TCP meter
    python examples/iot/modbus_meter.py --serial /dev/ttyUSB0  # a Modbus RTU meter on an RS-485 adapter

``ModbusClient.poll`` reads the registers below every half a second and raises ``update`` with
them; the relay is coil 0. The register map is the simulated meter's: change ``POLL`` for yours
(it is in the meter's manual).
"""

import argparse
import math
import threading

import pyzed as pz
from pyzed import ui
from pyzed.iot.modbus import encode

POLL = """
voltage  input 0  float32
current  input 2  float32
power    input 4  float32
energy   input 6  float32
relay    coils 0
"""


def simulate(meter, stop: threading.Event) -> None:
    """A meter whose load changes over time; the relay cuts it."""
    step, energy = 0, 1520.0
    while not stop.wait(0.25):
        step += 1
        on = meter.coils.get(0, True)
        volts = 230 + 2 * math.sin(step / 9)
        amps = (4.2 + 2.5 * math.sin(step / 15) + 0.3 * math.sin(step / 2)) if on else 0.0
        energy += volts * amps / 1000 / 14400
        meter.set_registers(0, encode([volts, amps, volts * amps, energy], "float32"), "input")


class Meter(pz.App):
    title = "Energy meter"
    size = (760, 420)

    def __init__(self, **connection):
        self.values = {}
        self.history = []
        self.status = "Connecting…"
        self.modbus = pz.ModbusClient(**connection, poll=POLL, interval=500, on_update=self.updated,
                                      on_connected=lambda: self.set_status("Connected"),
                                      on_failed=lambda reason: self.set_status(f"Meter error: {reason}"))
        self.modbus.connect()

    def set_status(self, text):
        self.status = text

    def updated(self, values):
        self.values = values
        self.history = (self.history + [values["power"]])[-60:]

    def switch_relay(self, on):
        try:
            self.modbus.write_coil(0, on)
        except OSError as error:
            self.status = f"Could not switch the relay: {error}"

    def on_close(self):
        self.modbus.disconnect()

    def view(self):
        t = self.resolved_theme()
        v = self.values
        if not v:
            body = ui.empty_state("Waiting for the meter", self.status, icon="factory", theme=t)
        else:
            body = pz.column([
                pz.row([ui.stat("Voltage", f"{v['voltage']:.1f} V", icon="zap", width="fill", theme=t),
                        ui.stat("Current", f"{v['current']:.2f} A", icon="activity", width="fill", theme=t),
                        ui.stat("Energy", f"{v['energy']:.2f} kWh", icon="gauge", width="fill", theme=t)],
                       spacing=12),
                ui.card(pz.column([
                    pz.row([ui.label("Power", color="text_muted", theme=t), pz.hspace(),
                            ui.label(f"{v['power']:.0f} W", size=22, weight="semibold", theme=t)], align="center"),
                    ui.sparkline(self.history, width=680, height=70, theme=t),
                ], spacing=8), theme=t),
                ui.card(pz.row([pz.icon("power", size=18, color=t.text), ui.label("Relay (coil 0)", theme=t),
                                pz.hspace(), ui.switch(bool(v.get("relay")), self.switch_relay, theme=t)],
                               spacing=8, align="center"), theme=t),
            ], spacing=12)
        return pz.container(pz.column([
            pz.row([ui.heading("Energy meter", level=2, theme=t), pz.hspace(), ui.muted(self.status, size="sm")],
                   align="center"),
            body,
        ], spacing=14), padding=20, width="fill", height="fill", bg=t.background)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--host", help="a Modbus TCP meter")
    parser.add_argument("--serial", help="a Modbus RTU meter on this serial port")
    parser.add_argument("--unit", type=int, default=1)
    args = parser.parse_args()
    if args.host or args.serial:
        Meter(host=args.host or "", serial_port=args.serial or "", unit=args.unit).run()
        return
    from pyzed.iot.testing import ModbusServer

    stop = threading.Event()
    with ModbusServer() as meter:
        meter.coils[0] = True
        simulate_thread = threading.Thread(target=simulate, args=(meter, stop), daemon=True)
        simulate_thread.start()
        try:
            Meter(host="127.0.0.1", port=meter.port).run()
        finally:
            stop.set()


if __name__ == "__main__":
    main()
