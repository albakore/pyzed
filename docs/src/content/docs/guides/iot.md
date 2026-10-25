---
title: IoT and devices
description: "Talk to Arduino and ESP32 boards over serial or USB, MQTT brokers, WebSockets, UDP and TCP devices, Modbus PLCs and energy meters, Bluetooth LE gadgets and the devices of your local network from a Python desktop app made with Pyzed."
sidebar:
  order: 5.6
---

`pyzed.iot` connects an app to the things around it: a board on a USB cable, an MQTT broker, a
PLC on the factory network, a heart-rate strap, the printers and speakers of your home network.
Each one is a [service](/pyzed/guides/services/): you give it handlers, it connects in a thread
of its own, and its events reach your handlers on the app's thread, so they can change the app's
state right away. In [Pyzed Design](/pyzed/editor/non-visual-components/) they are the
components of the **IoT** category of the toolbox.

![The MQTT dashboard example: sensor tiles that update as messages arrive](/pyzed/media/iot/dashboard.webp)

| Service | Talks to | Main events |
| --- | --- | --- |
| `pz.SerialPort` | Arduino, ESP32, Raspberry Pi Pico, GPS, scales, lab instruments (serial and USB serial) | `line`, `data` |
| `pz.SerialWatcher` | The serial devices being plugged in and unplugged | `plugged`, `unplugged` |
| `pz.MqttClient` | Mosquitto, Home Assistant, EMQX, HiveMQ, Zigbee2MQTT, Tasmota... | `message` |
| `pz.WebSocket` | Servers and devices with a WebSocket (ESPHome, OctoPrint, your own API) | `message` |
| `pz.UdpSocket` | Broadcasts, OSC, Art-Net, WLED, sketches that send UDP | `message` |
| `pz.TcpClient` | Raw TCP: label printers, PLC consoles, Telnet-style devices | `line`, `data` |
| `pz.ModbusClient` | PLCs, energy meters, inverters, VFDs (Modbus TCP and RTU over RS-485) | `update` |
| `pz.DeviceDiscovery` | Whatever answers on the local network (mDNS/Bonjour and SSDP/UPnP) | `found`, `lost` |
| `pz.BluetoothScanner` | Bluetooth LE devices nearby | `found` |
| `pz.BluetoothDevice` | One Bluetooth LE device: read, write and get notified | `notification` |

All of them work on Windows, macOS and Linux without extra packages, except Bluetooth, which
needs `bleak`:

```bash
uv add "pyzed-ui[bluetooth]"        # or: pip install "pyzed-ui[bluetooth]"
```

## Connections

Every connection (serial, MQTT, WebSocket, TCP, Modbus, Bluetooth device) works the same way:

```python
mqtt = pz.MqttClient("broker.local", on_connected=..., on_disconnected=..., on_failed=...)
mqtt.connect()        # in the background: returns at once
mqtt.connected        # True once it is up
mqtt.disconnect()     # closes it and stops reconnecting
```

`failed` receives the reason as text ("connection refused", "wrong user name or password"...).
With `reconnect` (in milliseconds) the connection comes back by itself after the device is
unplugged or the network drops; serial ports and MQTT and Modbus clients do it by default. Stop them
when the window closes, in `on_close`.

## A board on a serial port

```python
import pyzed as pz
from pyzed import ui


class Thermometer(pz.App):
    def __init__(self):
        self.temperature = None
        self.board = pz.SerialPort(match="arduino", baud_rate=115200, on_line=self.reading)
        self.board.connect()

    def reading(self, line):            # what the board printed with Serial.println()
        if line.startswith("t="):
            self.temperature = float(line[2:])

    def toggle_led(self, on):
        self.board.send_line("LED ON" if on else "LED OFF")

    def on_close(self):
        self.board.disconnect()

    def view(self):
        return pz.column([ui.heading(f"{self.temperature or '--'} °C"),
                          ui.switch(False, self.toggle_led, label="LED")], padding=24, spacing=12)


pz.run(Thermometer)
```

`port` names the port (`"COM3"` on Windows, `"/dev/ttyUSB0"` or `"/dev/ttyACM0"` on Linux,
`"/dev/cu.usbmodem…"` on macOS). Leave it empty and the first port that `match` names is used:
part of the maker or product (`"arduino"`, `"cp210"`, `"pico"`) or the USB ids (`"2341:0043"`).
`pz.SerialPort.ports()` lists them with their `description`, `usb_id`, `manufacturer` and
`product`, and a `pz.SerialWatcher` raises `plugged` and `unplugged` as boards come and go.

![The serial monitor example reading a board and sending it a command](/pyzed/media/iot/serial.webp)

:::tip[No board at hand?]
`examples/iot/serial_monitor.py --demo` plays a board on a virtual serial cable (Linux and
macOS), made with `pyzed.iot.testing.serial_pair()`. Use it in your own tests too.
:::

## MQTT

```python
mqtt = pz.MqttClient("192.168.1.5", username="kev", password="…", subscribe="home/#",
                     on_message=self.received)
mqtt.on_topic("home/+/temperature", self.temperature)   # only these topics, to their own handler
mqtt.connect()

def received(self, message):
    print(message.topic, message.value)   # 21.5, {"on": true}, "open"... (text, number or JSON)

mqtt.publish("home/lamp/set", "on")
mqtt.publish("home/lamp/config", {"brightness": 80}, qos=1, retain=True)   # dicts go as JSON
```

`subscribe` takes one topic, a list or one per line (`"home/# 1"` asks for QoS 1); the
wildcards `+` (one level) and `#` (every level below) work, and the subscriptions are made again
after every reconnection. `tls=True` connects to port 8883 (`ca_file` for your own certificate
authority, `insecure` for a self-signed broker on your network). `will_topic` and
`will_message` are published by the broker if the app disappears without disconnecting, which is
how dashboards know a device went offline. Messages of QoS 1 and 2 published while the client
is disconnected wait and go out when it connects.

## WebSocket, UDP and TCP

```python
ws = pz.WebSocket("ws://esp32.local/ws", json=True, on_message=self.update_state)
ws.connect()
ws.send({"led": True})          # text, bytes, or JSON

udp = pz.UdpSocket(4210, on_message=lambda m: print(m.host, m.text))
udp.start()                      # listens on port 4210
udp.send("ping", "192.168.1.50", 4210)
udp.reply(message, "pong")       # answers whoever sent message

tcp = pz.TcpClient("192.168.1.80", 9100, on_line=print)   # a label printer, a PLC console...
tcp.connect()
tcp.send_line("~HS")
```

## Modbus

```python
meter = pz.ModbusClient("192.168.1.40", unit=1, poll="""
    voltage  input 0  float32
    power    input 12 float32
    relay    coils 0
""", interval=1000, on_update=self.show)
meter.connect()

def show(self, values):        # {"voltage": 230.4, "power": 1487.3, "relay": True}
    self.power = values["power"]

meter.write_coil(0, False)                        # switch the relay off
meter.write(100, 21.5, "float32")                 # a setpoint in two holding registers
meter.read_holding_registers(0, 4)                # [0, 17, 230, 1]
```

With `serial_port="/dev/ttyUSB0"` (and `baud_rate`, `parity`) instead of a host it speaks
Modbus RTU over an RS-485 adapter. Each `poll` line is `name table address [format] [count]`:
the table is `coils`, `discrete`, `holding` or `input`, the format `uint16` (the default),
`int16`, `int32`, `uint32`, `float32`, `int64` or `float64`; `word_order="little"` is for devices
that put the low word first. The device's register map is in its manual. Calls block for at
most `timeout` milliseconds and raise `pyzed.iot.ModbusError` when the device refuses or does
not answer.

![The Modbus energy meter example](/pyzed/media/iot/meter.webp)

## Finding devices on the network

```python
finder = pz.DeviceDiscovery("_http._tcp", on_found=lambda d: print(d.name, d.address, d.properties))
finder.start()      # scans now and every 30 seconds; finder.scan() scans once
```

`service` is an mDNS/Bonjour type: `"_http._tcp"` (web pages), `"_ipp._tcp"` (printers),
`"_googlecast._tcp"`, `"_esphomelib._tcp"`, `"_hap._tcp"` (HomeKit)...; left empty, every type is
asked. SSDP/UPnP finds TVs, routers and media servers too (`ssdp=False` turns it off). Each
`Device` has a `name`, `host`, `port`, `hostname` (`esp32.local`), `service` and `properties`
(the TXT record, or the maker and model of a UPnP device). `lost` is raised when a device stops
answering for two scans. `pyzed.iot.resolve_local("raspberrypi.local")` finds a single address.

![The network scanner example finding devices](/pyzed/media/iot/scanner.webp)

## Bluetooth LE

```python
scanner = pz.BluetoothScanner(services="heart_rate", on_found=lambda d: print(d.name, d.address, d.rssi))
scanner.scan()

strap = pz.BluetoothDevice(name="Polar", notify="heart_rate_measurement", on_notification=self.beat)
strap.connect()

def beat(self, note):
    self.bpm = note.data[1]

strap.read("battery_level")          # b"\x5a" (90 %)
strap.write("nordic_uart_rx", "hello")
```

Characteristics and services can be full UUIDs, short ones (`"2a37"`, `"180d"`) or the names
in `pyzed.iot.bluetooth.KNOWN` (`battery_level`, `heart_rate_measurement`, `temperature`,
`humidity`, `nordic_uart_tx`...). `read` and `write` wait for the device: call them from a
handler or a [`pz.Worker`](/pyzed/guides/services/). On Linux it uses BlueZ, on Windows the
system's Bluetooth (Windows 10 or later) and on macOS CoreBluetooth, which asks the user for
permission the first time.

## In Pyzed Design

![Adding an MQTT client and a serial port from the IoT category: they go to the tray under the form, and a double click opens the message handler](/pyzed/media/iot/tray.webp)

Search the toolbox for **IoT** (or type `mqtt`, `serial`, `modbus`...) and click a component: it
goes to the tray under the form. Its properties are the service's (the broker, the topics, the
port, the poll lines...), **Connect on load** connects it when the form opens and **Reconnect
(ms)** brings it back after a drop. A double click opens the handler of its main event
(`message`, `line`, `update`, `notification`), and handlers reach it by name:

```python
def mqtt_client1_message(form, event):
    if event.value.topic == "home/living/temperature":
        form.label1.text = f"Temperature: {event.value.value} °C"


def button1_click(form, event):
    form.mqtt_client1.publish("home/lamp/set", "on")
```

## Trying without hardware

`pyzed.iot.testing` has small stand-ins that run on your computer, for tests, demos and
screenshots: `MqttBroker` (QoS 0 to 2, retained messages, logins), `WebSocketServer`,
`ModbusServer` (fill its coils and registers), `FakeNetwork` (devices that answer
`DeviceDiscovery`) and `serial_pair()` (a virtual serial cable, Linux and macOS).

```python
from pyzed.iot.testing import MqttBroker

def test_dashboard_shows_the_temperature():
    with MqttBroker() as broker:
        app = Dashboard("127.0.0.1", broker.port)
        app.mqtt.wait_connected()
        broker.publish("home/living/temperature", "21.5")
        ...
```

The four IoT examples of the [gallery](/pyzed/editor/examples/) (MQTT dashboard, Serial
monitor, Modbus energy meter, Network scanner) use them when there is no device, so they run on
any computer. See the [reference](/pyzed/reference/iot/) for every property and method.
