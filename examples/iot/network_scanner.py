"""A network scanner: the printers, boards, TVs and speakers that answer on your local network.

    python examples/iot/network_scanner.py          # your network (mDNS/Bonjour and SSDP/UPnP)
    python examples/iot/network_scanner.py --demo   # made-up devices, for a computer alone

``DeviceDiscovery`` asks every few seconds and raises ``found`` and ``lost`` as devices come and
go; a click on a row opens its web page when it has one.
"""

import argparse

import pyzed as pz
from pyzed import ui
from pyzed.iot import Device

DEMO = [
    Device("Greenhouse sensors", "192.168.1.77", 80, "mdns", "_esphomelib._tcp", "greenhouse.local",
           {"board": "esp32dev", "version": "2026.10.1"}),
    Device("Office printer", "192.168.1.20", 631, "mdns", "_ipp._tcp", "", {"ty": "LaserJet Pro"}),
    Device("Kitchen speaker", "192.168.1.31", 8009, "mdns", "_googlecast._tcp", "", {"md": "Nest Audio"}),
    Device("Workbench Pi", "192.168.1.50", 22, "mdns", "_ssh._tcp", "raspberrypi.local"),
    Device("Status page", "192.168.1.77", 8080, "mdns", "_http._tcp", "greenhouse.local"),
    Device("Living room TV", "192.168.1.9", 49000, "ssdp", "urn:schemas-upnp-org:device:MediaRenderer:1"),
    Device("Router", "192.168.1.1", 1900, "ssdp", "urn:schemas-upnp-org:device:InternetGatewayDevice:1"),
]


class Scanner(pz.App):
    title = "Network scanner"
    size = (880, 520)

    def __init__(self, network=None):
        self.devices = []
        self.log = "Scanning…"
        self.finder = pz.DeviceDiscovery(interval=15000, on_change=self.changed, on_done=self.done,
                                         on_found=lambda d: self.note(f"found {d.name}"),
                                         on_lost=lambda d: self.note(f"lost {d.name}"))
        if network is not None:  # the demo: made-up devices, whose description pages do not exist
            network.attach(self.finder)
            self.finder.describe = False
        self.finder.start()

    def note(self, text):
        self.log = text

    def changed(self, devices):
        self.devices = devices

    def done(self, devices):
        self.devices = devices
        self.log = f"{len(devices)} devices · scanning again every 15 s"

    def open(self, device):
        if device.kind == "ssdp" and device.url:
            pz.Launcher().open(device.url)
        elif device.service in ("_http._tcp", "_esphomelib._tcp"):
            pz.Launcher().open(f"http://{device.address}/")

    def on_close(self):
        self.finder.stop()

    def view(self):
        t = self.resolved_theme()
        rows = [{"name": d.name, "kind": "UPnP" if d.kind == "ssdp" else "Bonjour", "address": d.address,
                 "service": d.service.removeprefix("urn:schemas-upnp-org:device:"), "device": d}
                for d in self.devices]
        table = ui.table(["name", "kind", "address", "service"], rows, striped=True, height="fill",
                         on_row_double_press=lambda row: self.open(row["device"]),
                         empty=ui.empty_state("Nothing yet", "Devices show up as they answer.", icon="radar",
                                              theme=t), theme=t)
        return pz.container(pz.column([
            pz.row([ui.heading("Network", level=2, theme=t), pz.hspace(),
                    ui.button("Scan now", lambda: self.finder.scan(), icon="refresh-cw", variant="outline",
                              loading=self.finder.scanning, theme=t)], align="center"),
            table,
            ui.muted(self.log, size="sm"),
        ], spacing=12), padding=20, width="fill", height="fill", bg=t.background)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--demo", action="store_true", help="made-up devices instead of your network's")
    args = parser.parse_args()
    if args.demo:
        from pyzed.iot.testing import FakeNetwork

        with FakeNetwork(DEMO) as network:
            Scanner(network).run()
    else:
        Scanner().run()


if __name__ == "__main__":
    main()
