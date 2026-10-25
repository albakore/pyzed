"""IoT services: serial ports, MQTT, WebSocket, UDP/TCP, Modbus, network discovery and Bluetooth LE."""

import os
import socket
import struct
import sys
import threading
import time
import types

import pytest

import pyzed as pz
from pyzed import iot
from pyzed.iot import bluetooth, discovery, modbus, mqtt
from pyzed.iot.testing import ModbusServer, MqttBroker, WebSocketServer, modbus_rtu_device, serial_pair

posix_only = pytest.mark.skipif(not hasattr(os, "openpty"), reason="virtual serial ports need a pseudo-terminal")


def until(check, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if check():
            return True
        time.sleep(0.01)
    return check()


def test_iot_services_are_in_pz():
    for name in ("SerialPort", "SerialWatcher", "MqttClient", "WebSocket", "UdpSocket", "TcpClient", "ModbusClient",
                 "DeviceDiscovery", "BluetoothScanner", "BluetoothDevice"):
        assert getattr(pz, name) is getattr(iot, name)
        assert name in pz.__all__


# -- serial ---------------------------------------------------------------------------------------------------------
def test_port_info_matches_and_describes():
    port = iot.PortInfo("COM3", "usb", 0x2341, 0x0043, "123", "Arduino LLC", "Arduino Uno")
    assert port.usb_id == "2341:0043" and port.description == "Arduino LLC Arduino Uno (COM3)"
    for query in ("", "com3", "2341:0043", "2341", "arduino", "uno", "123"):
        assert port.matches(query), query
    assert not port.matches("esp32") and iot.PortInfo("/dev/ttyS0").description == "/dev/ttyS0"


def test_serial_ports_lists_and_filters(monkeypatch):
    fake = [{"name": "/dev/ttyS0", "kind": "unknown"},
            {"name": "/dev/ttyACM0", "kind": "usb", "vid": 0x2E8A, "pid": 0x0005, "serial_number": "E66",
             "manufacturer": "Raspberry Pi", "product": "Pico"}]
    monkeypatch.setattr(iot.serial._core, "serial_ports", lambda: fake)
    assert [p.name for p in iot.serial_ports()] == ["/dev/ttyACM0", "/dev/ttyS0"]  # USB first
    assert [p.name for p in pz.SerialPort.ports("pico")] == ["/dev/ttyACM0"]
    assert pz.SerialPort(match="pico")._target() == "/dev/ttyACM0"
    assert pz.SerialPort()._target() == "/dev/ttyACM0"  # without a match: the first USB port
    with pytest.raises(OSError, match="esp32"):
        pz.SerialPort(match="esp32")._target()


@posix_only
def test_serial_port_reads_lines_and_writes():
    device, path = serial_pair()
    lines, chunks, events = [], [], []
    port = pz.SerialPort(path, 115200, on_line=lines.append, on_data=chunks.append,
                         on_connected=lambda: events.append("connected"),
                         on_disconnected=lambda: events.append("disconnected"))
    assert port.connect() and port.wait_connected() and port.path == path
    os.write(device, b"temp=21.5\r\nhum")
    os.write(device, b"=40\n")
    assert until(lambda: lines == ["temp=21.5", "hum=40"])
    assert b"".join(chunks) == b"temp=21.5\r\nhum=40\n"
    assert port.send_line("LED ON")
    assert until(lambda: os.read(device, 100) == b"LED ON\n")
    port.disconnect()
    assert events == ["connected", "disconnected"] and not port.connected and not port.write("x")
    os.close(device)


def test_serial_port_fails_without_a_device():
    seen = []
    port = pz.SerialPort("/dev/pyzed-no-such-port", reconnect=0, on_failed=seen.append)
    port.connect()
    assert until(lambda: seen) and not port.connected and port.error == seen[0]
    assert until(lambda: not port.running)


def test_serial_watcher_reports_plugged_and_unplugged(monkeypatch):
    now = [{"name": "COM1", "kind": "pci"}]
    monkeypatch.setattr(iot.serial._core, "serial_ports", lambda: list(now))
    seen = []
    watcher = pz.SerialWatcher(on_plugged=lambda p: seen.append(("+", p.name)),
                               on_unplugged=lambda p: seen.append(("-", p.name)),
                               on_change=lambda ports: seen.append(("=", [p.name for p in ports])))
    watcher.start()
    try:
        assert [p.name for p in watcher.ports] == ["COM1"] and not seen
        now.append({"name": "COM7", "kind": "usb", "vid": 0x10C4, "pid": 0xEA60})
        watcher.check()
        now.pop(0)
        watcher.check()
    finally:
        watcher.stop()
    assert seen == [("+", "COM7"), ("=", ["COM7", "COM1"]), ("-", "COM1"), ("=", ["COM7"])]


# -- MQTT -----------------------------------------------------------------------------------------------------------
def test_topic_wildcards():
    assert mqtt.topic_matches("home/+/temperature", "home/kitchen/temperature")
    assert not mqtt.topic_matches("home/+/temperature", "home/kitchen/oven/temperature")
    assert mqtt.topic_matches("home/#", "home") and mqtt.topic_matches("home/#", "home/a/b")
    assert mqtt.topic_matches("#", "anything/at/all") and not mqtt.topic_matches("#", "$SYS/uptime")
    assert not mqtt.topic_matches("home/kitchen", "home/kitchen/light")


def test_mqtt_message_values():
    assert mqtt.MqttMessage("t", b"21.5").value == 21.5
    assert mqtt.MqttMessage("t", b'{"on": true}').value == {"on": True}
    assert mqtt.MqttMessage("t", b"on").value == "on" and mqtt.MqttMessage("t", b"x").text == "x"


def test_mqtt_publishes_subscribes_and_routes():
    with MqttBroker() as broker:
        messages, routed, events = [], [], []
        client = pz.MqttClient("127.0.0.1", broker.port, subscribe="sensors/#", on_message=messages.append,
                               on_connected=lambda: events.append("connected"),
                               on_subscribed=lambda topics: events.append(("subscribed", topics)),
                               on_published=lambda topic: events.append(("published", topic)))
        client.on_topic("sensors/+/temperature", lambda m: routed.append(m.value))
        assert client.connect() and client.wait_connected()
        assert until(lambda: any(e[0] == "subscribed" for e in events if isinstance(e, tuple)))
        broker.publish("sensors/kitchen/temperature", "21.5")
        broker.publish("sensors/kitchen/humidity", b"40")
        broker.publish("other/topic", "ignored")
        assert until(lambda: len(messages) == 2)
        assert [m.topic for m in messages] == ["sensors/kitchen/temperature", "sensors/kitchen/humidity"]
        assert until(lambda: routed == [21.5]) and client.last["sensors/kitchen/humidity"].value == 40
        for qos in (0, 1, 2):
            assert client.publish("lamp/set", {"on": True, "qos": qos}, qos=qos)
        assert until(lambda: len(broker.received) == 6)
        assert broker.received[3:] == [("lamp/set", b'{"on": true, "qos": %d}' % q) for q in range(3)]
        assert until(lambda: events.count(("published", "lamp/set")) == 2)  # QoS 1 and 2 are acknowledged
        client.disconnect()
        assert not client.connected and not client.publish("lamp/set", "off")


def test_mqtt_receives_qos_1_and_2_and_retained():
    with MqttBroker() as broker:
        broker.publish("state/door", "open", qos=1, retain=True)
        got = []
        client = pz.MqttClient("127.0.0.1", broker.port, on_message=got.append)
        client.connect()
        assert client.wait_connected()
        client.subscribe("state/#", qos=2)
        assert until(lambda: got) and got[0].retain and got[0].text == "open"
        broker.publish("state/window", "closed", qos=2)
        assert until(lambda: len(got) == 2) and got[1].qos == 2
        client.disconnect()


def test_mqtt_reports_a_refused_login_and_reconnects():
    with MqttBroker(users={"kev": "secret"}) as broker:
        failed = []
        client = pz.MqttClient("127.0.0.1", broker.port, username="kev", password="wrong", reconnect=0,
                               on_failed=failed.append)
        client.connect()
        assert until(lambda: failed) and "user name or password" in failed[0]
        events = []
        good = pz.MqttClient("127.0.0.1", broker.port, username="kev", password="secret", reconnect=100,
                             on_connected=lambda: events.append("up"), on_disconnected=lambda: events.append("down"))
        good.connect()
        assert until(lambda: events == ["up"])
        broker.kick()
        assert until(lambda: events[:3] == ["up", "down", "up"])  # it came back by itself
        good.disconnect()


def test_mqtt_keeps_qos_1_messages_until_connected():
    with MqttBroker() as broker:
        client = pz.MqttClient("127.0.0.1", broker.port)
        assert client.publish("queue/job", "1", qos=1) and not client.publish("queue/job", "lost")
        client.connect()
        assert until(lambda: broker.received == [("queue/job", b"1")])
        client.disconnect()


def test_mqtt_will_is_published_when_the_app_disappears():
    with MqttBroker() as broker:
        watcher_got = []
        watcher = pz.MqttClient("127.0.0.1", broker.port, subscribe="status/#", on_message=watcher_got.append)
        watcher.connect()
        assert watcher.wait_connected() and until(lambda: broker._subs and all(broker._subs.values()))
        device = pz.MqttClient("127.0.0.1", broker.port, will_topic="status/device", will_message="offline")
        device.connect()
        assert device.wait_connected()
        device._sock.close()  # gone without saying goodbye
        assert until(lambda: [m.text for m in watcher_got] == ["offline"])
        device.disconnect()
        watcher.disconnect()


# -- WebSocket ------------------------------------------------------------------------------------------------------
def test_websocket_sends_and_receives_text_bytes_and_json():
    with WebSocketServer() as server:
        got = []
        ws = pz.WebSocket(server.url + "live?id=1", headers={"Authorization": "Bearer t"}, protocols="v1, v2",
                          on_message=got.append)
        assert ws.connect() and ws.wait_connected() and ws.protocol == "v1"
        assert server.requests[0]["path"] == "/live?id=1" and server.requests[0]["authorization"] == "Bearer t"
        assert ws.send("hello") and ws.send(b"\x01\x02") and ws.send({"led": 1}) and ws.send(42)
        assert until(lambda: got == ["hello", b"\x01\x02", '{"led": 1}', "42"])
        ws.json = True
        server.send('{"t": 21.5}')
        server.send("x" * 70000)  # a long message (64-bit length)
        assert until(lambda: len(got) == 6) and got[4] == {"t": 21.5} and got[5] == "x" * 70000
        ws.disconnect()
        assert not ws.connected and not ws.send("late")


def test_websocket_reports_a_refused_handshake():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)

    def refuse():
        sock, _ = listener.accept()
        sock.recv(4096)
        sock.sendall(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
        sock.close()

    threading.Thread(target=refuse, daemon=True).start()
    failed = []
    ws = pz.WebSocket(f"ws://127.0.0.1:{listener.getsockname()[1]}/", on_failed=failed.append)
    ws.connect()
    assert until(lambda: failed) and "404" in failed[0]
    listener.close()
    with pytest.raises(iot.WebSocketError, match="ws://"):
        pz.WebSocket("http//nope")._open()


# -- UDP and TCP ----------------------------------------------------------------------------------------------------
def test_udp_sends_receives_and_replies():
    server_got, client_got = [], []
    server = pz.UdpSocket(0, host="127.0.0.1")
    server.on("message", lambda m: (server_got.append(m), server.reply(m, m.text.upper())))
    client = pz.UdpSocket(0, host="127.0.0.1", remote_host="127.0.0.1", on_message=client_got.append)
    assert server.start() and client.start() and server.port
    client.remote_port = server.port
    assert client.send("ping") and client.send({"n": 1}, "127.0.0.1", server.port)
    assert until(lambda: [m.text for m in client_got] == ["PING", '{"N": 1}'])
    assert server_got[1].json() == {"n": 1} and server_got[0].port == client.port
    server.stop()
    client.stop()
    failed = []
    assert not pz.UdpSocket(on_failed=failed.append).send("nowhere") and failed


def test_tcp_client_reads_lines():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    received = []

    def device():
        sock, _ = listener.accept()
        sock.sendall(b"READY\r\nV=12")
        sock.sendall(b".1\n")
        received.append(sock.recv(100))
        sock.close()

    threading.Thread(target=device, daemon=True).start()
    lines, events = [], []
    tcp = pz.TcpClient("127.0.0.1", listener.getsockname()[1], on_line=lines.append,
                       on_disconnected=lambda: events.append("down"))
    tcp.connect()
    assert until(lambda: lines == ["READY", "V=12.1"])
    assert tcp.send_line("MEASURE?") and until(lambda: received == [b"MEASURE?\n"])
    assert until(lambda: events == ["down"])  # the device closed the connection
    listener.close()


# -- Modbus ---------------------------------------------------------------------------------------------------------
def test_modbus_values_encode_and_decode():
    assert modbus.crc16(b"\x01\x03\x00\x00\x00\x01") == 0x0A84
    regs = modbus.encode(21.5, "float32")
    assert modbus.decode(regs, "float32") == [21.5]
    assert modbus.decode(modbus.encode([-2, 70000], "int32", "little"), "int32", "little") == [-2, 70000]
    assert modbus.decode([0xFFFF], "int16") == [-1] and modbus.decode([0xFFFF]) == [65535]
    item = modbus.PollItem.parse("power input 0x10 float32")
    assert (item.name, item.table, item.address, item.format, item.count) == ("power", "input", 16, "float32", 1)
    assert modbus.PollItem.parse("relays coils 0 8").count == 8
    with pytest.raises(ValueError):
        modbus.PollItem.parse("bad table")


def test_modbus_tcp_reads_writes_and_polls():
    with ModbusServer() as server:
        server.set_registers(0, modbus.encode(230.4, "float32"), "input")
        server.set_registers(10, [7, 8, 9])
        server.discrete[3] = True
        updates, failed = [], []
        client = pz.ModbusClient("127.0.0.1", server.port, poll="voltage input 0 float32\nsetpoints holding 10 2",
                                 interval=50, on_update=updates.append, on_failed=failed.append)
        client.connect()
        assert client.wait_connected()
        assert client.read_holding_registers(10, 3) == [7, 8, 9]
        assert client.read_discrete_inputs(2, 2) == [False, True]
        assert round(client.read("input", 0, "float32"), 1) == 230.4
        client.write_coil(5, True)
        client.write_coils(8, [True, False, True])
        client.write_register(20, 1234)
        client.write(30, 1.5, "float32")
        assert client.read_coils(5, 6) == [True, False, False, True, False, True]
        assert server.holding[20] == 1234 and modbus.decode([server.holding[30], server.holding[31]], "float32") == [1.5]
        assert until(lambda: updates) and updates[-1]["setpoints"] == [7, 8]
        assert round(updates[-1]["voltage"], 1) == 230.4 and not failed
        with pytest.raises(modbus.ModbusError, match="illegal data address"):
            client.read_holding_registers(500)
        client.disconnect()
    with pytest.raises(modbus.ModbusError):
        pz.ModbusClient().read_coils(0)


@posix_only
def test_modbus_rtu_over_a_serial_port():
    device, path = serial_pair()
    memory = modbus_rtu_device(device, unit=3)
    memory.set_registers(0, [11, 22])
    client = pz.ModbusClient(serial_port=path, baud_rate=19200, unit=3, timeout=500)
    client.connect()
    assert client.wait_connected() and client.rtu
    assert client.read_holding_registers(0, 2) == [11, 22]
    client.write_registers(4, [5, 6])
    assert memory.holding[4] == 5 and memory.holding[5] == 6
    with pytest.raises(modbus.ModbusError, match="did not answer"):
        client.request(3, struct.pack(">HH", 0, 1), unit=9)  # nobody at address 9
    client.disconnect()
    os.close(device)


# -- discovery ------------------------------------------------------------------------------------------------------
def _dns_answer(records):
    """A DNS response with ``(name, type, rdata)`` records."""
    out = struct.pack("!6H", 0, 0x8400, 0, len(records), 0, 0)
    for name, kind, rdata in records:
        out += discovery._encode_name(name) + struct.pack("!HHIH", kind, 1, 120, len(rdata)) + rdata
    return out


def _fake_responder(answer):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))

    def run():
        while True:
            try:
                data, sender = sock.recvfrom(9000)
            except OSError:
                return
            reply = answer(data)
            if reply:
                try:
                    sock.sendto(reply, sender)
                except OSError:
                    return

    threading.Thread(target=run, daemon=True).start()
    return sock


def test_mdns_finds_services_and_ssdp_finds_upnp_devices():
    def mdns(data):
        name, _ = discovery._read_name(data, 12)
        if name == "_http._tcp.local":
            instance = "Greenhouse._http._tcp.local"
            txt = b"".join(bytes([len(i)]) + i for i in (b"version=1.2", b"board=esp32"))
            return _dns_answer([("_http._tcp.local", 12, discovery._encode_name(instance)),
                                (instance, 33, struct.pack("!3H", 0, 0, 8080) + discovery._encode_name("gh.local")),
                                (instance, 16, txt), ("gh.local", 1, socket.inet_aton("192.168.1.77"))])
        return None

    def ssdp(data):
        assert data.startswith(b"M-SEARCH") and b"ST: ssdp:all" in data
        return (b"HTTP/1.1 200 OK\r\nLOCATION: http://192.168.1.9:49000/desc.xml\r\nSERVER: Linux UPnP/1.0\r\n"
                b"ST: urn:schemas-upnp-org:device:MediaRenderer:1\r\nUSN: uuid:abc::urn:x\r\n\r\n")

    mdns_sock, ssdp_sock = _fake_responder(mdns), _fake_responder(ssdp)
    found, lost = [], []
    finder = pz.DeviceDiscovery("_http._tcp", describe=False, timeout=400, on_found=found.append, on_lost=lost.append)
    finder.mdns_address = mdns_sock.getsockname()
    finder.ssdp_address = ssdp_sock.getsockname()
    finder.scan(wait=True)
    by_kind = {d.kind: d for d in found}
    web = by_kind["mdns"]
    assert (web.name, web.host, web.port, web.service, web.hostname) == ("Greenhouse", "192.168.1.77", 8080,
                                                                          "_http._tcp", "gh.local")
    assert web.properties == {"version": "1.2", "board": "esp32"} and web.address == "192.168.1.77:8080"
    tv = by_kind["ssdp"]
    assert (tv.host, tv.port, tv.url) == ("192.168.1.9", 49000, "http://192.168.1.9:49000/desc.xml")
    assert tv.service == "urn:schemas-upnp-org:device:MediaRenderer:1" and tv.properties["server"]
    assert finder.devices == sorted(found, key=lambda d: (d.name.lower(), d.host))
    ssdp_sock.close()
    for _ in range(2):  # the TV stops answering: lost after two scans
        finder.scan(wait=True)
    assert [d.kind for d in lost] == ["ssdp"] and len(finder.devices) == 1
    mdns_sock.close()


def test_dns_names_with_compression():
    question = discovery._encode_name("_ipp._tcp.local") + struct.pack("!2H", 12, 1)
    rdata = b"\x07Printer" + struct.pack("!H", 0xC00C)  # "Printer" + a pointer to the question's name
    record = struct.pack("!H", 0xC00C) + struct.pack("!HHIH", 12, 1, 60, len(rdata)) + rdata
    message = struct.pack("!6H", 0, 0x8400, 1, 1, 0, 0) + question + record
    assert discovery.parse(message) == [("_ipp._tcp.local", 12, "Printer._ipp._tcp.local")]


# -- Bluetooth LE ---------------------------------------------------------------------------------------------------
def test_bluetooth_uuids():
    assert bluetooth.uuid("2a37") == "00002a37-0000-1000-8000-00805f9b34fb"
    assert bluetooth.uuid("0x180D") == "0000180d-0000-1000-8000-00805f9b34fb"
    assert bluetooth.uuid("Heart rate measurement") == bluetooth.uuid("2a37")
    assert bluetooth.uuid("nordic_uart_tx").startswith("6e400003")
    assert bluetooth.BleNotification("x", b"\x48").value == 72
    assert bluetooth.BleNotification("x", b"21.5").value == 21.5


@pytest.fixture
def fake_bleak(monkeypatch):
    """A stand-in for bleak: one heart-rate strap nearby."""
    module = types.ModuleType("bleak")
    state = {"written": [], "notify": {}, "connected": False}

    class Dev:
        address, name = "AA:BB:CC:DD:EE:01", "Polar H10"

    class Adv:
        local_name, rssi = "Polar H10", -52
        service_uuids = [bluetooth.uuid("heart_rate")]
        manufacturer_data = {107: b"\x01"}
        service_data = {}

    class Other:
        address, name = "AA:BB:CC:DD:EE:02", "Lamp"

    class OtherAdv:
        local_name, rssi, service_uuids, manufacturer_data, service_data = "Lamp", -80, [], {}, {}

    class BleakScanner:
        def __init__(self, detection_callback):
            self.callback = detection_callback

        async def start(self):
            self.callback(Dev(), Adv())
            self.callback(Other(), OtherAdv())

        async def stop(self):
            pass

        @staticmethod
        async def find_device_by_filter(test, timeout):
            return Dev() if test(Dev(), Adv()) else None

    class BleakClient:
        def __init__(self, target, disconnected_callback, timeout):
            self.target, self.gone = target, disconnected_callback
            self.services = []

        async def connect(self):
            state["connected"] = True
            state["client"] = self

        async def disconnect(self):
            state["connected"] = False

        async def start_notify(self, uuid, callback):
            state["notify"][uuid] = callback

        async def stop_notify(self, uuid):
            state["notify"].pop(uuid, None)

        async def read_gatt_char(self, uuid):
            return bytearray(b"\x5a")

        async def write_gatt_char(self, uuid, data, response=False):
            state["written"].append((uuid, data, response))

    module.BleakScanner, module.BleakClient = BleakScanner, BleakClient
    monkeypatch.setitem(sys.modules, "bleak", module)
    return state


def test_bluetooth_scanner_finds_devices(fake_bleak):
    found, done = [], []
    scanner = pz.BluetoothScanner(services="heart_rate", timeout=500, on_found=found.append, on_done=done.append)
    scanner.scan(wait=True)
    assert [d.label for d in found] == ["Polar H10"] and found[0].rssi == -52
    assert done and done[0] == found
    everything = pz.BluetoothScanner(timeout=500)
    assert [d.name for d in everything.scan(wait=True)] == ["Polar H10", "Lamp"]  # nearest first


def test_bluetooth_device_reads_writes_and_notifies(fake_bleak):
    notes, events = [], []
    strap = pz.BluetoothDevice(name="polar", notify="heart_rate_measurement", on_notification=notes.append,
                               on_connected=lambda: events.append("up"), on_disconnected=lambda: events.append("down"))
    strap.connect()
    assert until(lambda: events == ["up"])
    hr = bluetooth.uuid("2a37")
    assert hr in fake_bleak["notify"]
    fake_bleak["notify"][hr](None, bytearray(b"\x00\x48"))
    assert until(lambda: notes) and notes[0].data == b"\x00\x48" and strap.last[hr] is notes[0]
    assert strap.read("battery_level") == b"\x5a"
    strap.write("nordic_uart_rx", "hi", response=True)
    strap.write("2a06", 1)
    assert fake_bleak["written"] == [(bluetooth.uuid("nordic_uart_rx"), b"hi", True), (bluetooth.uuid("2a06"), b"\x01",
                                                                                      False)]
    fake_bleak["client"].gone(None)  # out of range
    assert until(lambda: events == ["up", "down"]) and not fake_bleak["connected"]


def test_bluetooth_without_bleak_says_how_to_install(monkeypatch):
    monkeypatch.setitem(sys.modules, "bleak", None)
    failed = []
    pz.BluetoothScanner(on_failed=failed.append).scan(wait=True)
    assert failed == [bluetooth.INSTALL]
    device = pz.BluetoothDevice("AA:BB", on_failed=failed.append)
    device.connect()
    assert until(lambda: len(failed) == 2) and "pyzed-ui[bluetooth]" in failed[1]


# -- in a form made with Pyzed Design -------------------------------------------------------------------------------
def test_iot_components_run_in_a_form():
    from pyzed.designer import components, nonvisual
    from pyzed.designer.model import Control, Form
    from pyzed.designer.runtime import FormApp

    assert {c.type for c in components.categories()[components.IOT]} == {
        "serial_port", "serial_watcher", "mqtt_client", "websocket", "udp_socket", "tcp_client", "modbus_client",
        "device_discovery", "bluetooth_scanner", "bluetooth_device"}
    with MqttBroker() as broker:
        got = []
        form = Form(width=300, height=200)
        form.add(Control("mqtt1", "mqtt_client", props={"host": "127.0.0.1", "port": broker.port,
                                                         "subscribe": "sensors/#"},
                         events={"message": "on_message", "connected": "on_connected"}))
        form.add(Control("ble1", "bluetooth_device", props={"device_name": "Polar", "running": False}))
        app = FormApp(form, {"on_message": lambda f, e: got.append((e.value.topic, e.value.value)),
                             "on_connected": lambda f, e: f.mqtt1.publish("sensors/hello", "1")})
        runtime = app.runtime
        mqtt1 = runtime.services["mqtt1"]
        assert isinstance(mqtt1, pz.MqttClient) and not mqtt1.running  # it connects when the form opens
        assert mqtt1.topics == ["sensors/#"] and runtime.services["ble1"].name == "Polar"
        runtime.load()
        assert until(lambda: got == [("sensors/hello", 1)])
        assert not runtime.services["ble1"].running
        nonvisual.stop(runtime)
        assert not mqtt1.running
