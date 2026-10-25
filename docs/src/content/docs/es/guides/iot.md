---
title: IoT y dispositivos
description: "Habla con placas Arduino y ESP32 por serie o USB, brokers MQTT, WebSockets, dispositivos UDP y TCP, PLC y medidores de energía Modbus, aparatos Bluetooth LE y los dispositivos de tu red local desde una app de escritorio en Python hecha con Pyzed."
sidebar:
  order: 5.6
---

`pyzed.iot` conecta una app con lo que tiene alrededor: una placa en un cable USB, un broker
MQTT, un PLC en la red de la fábrica, una banda de pulso, las impresoras y altavoces de tu casa.
Cada uno es un [servicio](/pyzed/es/guides/services/): le das manejadores, se conecta en un hilo
propio y sus eventos llegan a tus manejadores en el hilo de la app, así que pueden cambiar el
estado de la app en el momento. En [Pyzed Design](/pyzed/es/editor/non-visual-components/) son
los componentes de la categoría **IoT** de la caja de herramientas.

![El ejemplo del panel MQTT: los sensores se actualizan a medida que llegan los mensajes](/pyzed/media/iot/dashboard.webp)

| Servicio | Habla con | Eventos principales |
| --- | --- | --- |
| `pz.SerialPort` | Arduino, ESP32, Raspberry Pi Pico, GPS, balanzas, instrumentos de laboratorio (serie y serie USB) | `line`, `data` |
| `pz.SerialWatcher` | Los dispositivos serie que se enchufan y desenchufan | `plugged`, `unplugged` |
| `pz.MqttClient` | Mosquitto, Home Assistant, EMQX, HiveMQ, Zigbee2MQTT, Tasmota... | `message` |
| `pz.WebSocket` | Servidores y dispositivos con WebSocket (ESPHome, OctoPrint, tu propia API) | `message` |
| `pz.UdpSocket` | Difusiones, OSC, Art-Net, WLED, sketches que envían UDP | `message` |
| `pz.TcpClient` | TCP directo: impresoras de etiquetas, consolas de PLC, dispositivos tipo Telnet | `line`, `data` |
| `pz.ModbusClient` | PLC, medidores de energía, inversores, variadores (Modbus TCP y RTU por RS-485) | `update` |
| `pz.DeviceDiscovery` | Lo que responde en la red local (mDNS/Bonjour y SSDP/UPnP) | `found`, `lost` |
| `pz.BluetoothScanner` | Dispositivos Bluetooth LE cercanos | `found` |
| `pz.BluetoothDevice` | Un dispositivo Bluetooth LE: leer, escribir y recibir avisos | `notification` |

Todos funcionan en Windows, macOS y Linux sin paquetes extra, salvo Bluetooth, que necesita
`bleak`:

```bash
uv add "pyzed-ui[bluetooth]"        # o: pip install "pyzed-ui[bluetooth]"
```

## Conexiones

Todas las conexiones (serie, MQTT, WebSocket, TCP, Modbus, dispositivo Bluetooth) funcionan
igual:

```python
mqtt = pz.MqttClient("broker.local", on_connected=..., on_disconnected=..., on_failed=...)
mqtt.connect()        # en segundo plano: vuelve enseguida
mqtt.connected        # True cuando ya está conectado
mqtt.disconnect()     # la cierra y deja de reconectar
```

`failed` recibe el motivo como texto ("connection refused", "wrong user name or password"...).
Con `reconnect` (en milisegundos) la conexión vuelve sola cuando se desenchufa el dispositivo o
se cae la red; los puertos serie y los clientes MQTT y Modbus lo hacen por defecto. Detenlas al
cerrar la ventana, en `on_close`.

## Una placa en un puerto serie

```python
import pyzed as pz
from pyzed import ui


class Termometro(pz.App):
    def __init__(self):
        self.temperatura = None
        self.placa = pz.SerialPort(match="arduino", baud_rate=115200, on_line=self.lectura)
        self.placa.connect()

    def lectura(self, linea):            # lo que la placa imprimió con Serial.println()
        if linea.startswith("t="):
            self.temperatura = float(linea[2:])

    def cambiar_led(self, encendido):
        self.placa.send_line("LED ON" if encendido else "LED OFF")

    def on_close(self):
        self.placa.disconnect()

    def view(self):
        return pz.column([ui.heading(f"{self.temperatura or '--'} °C"),
                          ui.switch(False, self.cambiar_led, label="LED")], padding=24, spacing=12)


pz.run(Termometro)
```

`port` nombra el puerto (`"COM3"` en Windows, `"/dev/ttyUSB0"` o `"/dev/ttyACM0"` en Linux,
`"/dev/cu.usbmodem…"` en macOS). Si lo dejas vacío se usa el primer puerto que nombre `match`:
parte del fabricante o del producto (`"arduino"`, `"cp210"`, `"pico"`) o los ids USB
(`"2341:0043"`). `pz.SerialPort.ports()` los lista con su `description`, `usb_id`,
`manufacturer` y `product`, y un `pz.SerialWatcher` lanza `plugged` y `unplugged` cuando las
placas llegan y se van.

![El ejemplo del monitor serie leyendo una placa y enviándole una orden](/pyzed/media/iot/serial.webp)

:::tip[¿No tienes una placa a mano?]
`examples/iot/serial_monitor.py --demo` simula una placa en un cable serie virtual (Linux y
macOS), hecho con `pyzed.iot.testing.serial_pair()`. Úsalo también en tus pruebas.
:::

## MQTT

```python
mqtt = pz.MqttClient("192.168.1.5", username="kev", password="…", subscribe="casa/#",
                     on_message=self.recibido)
mqtt.on_topic("casa/+/temperatura", self.temperatura)   # solo esos temas, a su propio manejador
mqtt.connect()

def recibido(self, mensaje):
    print(mensaje.topic, mensaje.value)   # 21.5, {"on": true}, "abierta"... (texto, número o JSON)

mqtt.publish("casa/lampara/set", "on")
mqtt.publish("casa/lampara/config", {"brillo": 80}, qos=1, retain=True)   # los dicts van como JSON
```

`subscribe` acepta un tema, una lista o uno por línea (`"casa/# 1"` pide QoS 1); funcionan los
comodines `+` (un nivel) y `#` (todos los niveles de debajo), y las suscripciones se rehacen
tras cada reconexión. `tls=True` conecta al puerto 8883 (`ca_file` para tu propia autoridad
certificadora, `insecure` para un broker con certificado autofirmado en tu red). `will_topic` y
`will_message` los publica el broker si la app desaparece sin desconectarse, que es como los
paneles saben que un dispositivo se quedó sin conexión. Los mensajes de QoS 1 y 2 publicados
mientras el cliente está desconectado esperan y salen al conectarse.

## WebSocket, UDP y TCP

```python
ws = pz.WebSocket("ws://esp32.local/ws", json=True, on_message=self.actualizar)
ws.connect()
ws.send({"led": True})          # texto, bytes o JSON

udp = pz.UdpSocket(4210, on_message=lambda m: print(m.host, m.text))
udp.start()                      # escucha en el puerto 4210
udp.send("ping", "192.168.1.50", 4210)
udp.reply(mensaje, "pong")       # responde a quien envió el mensaje

tcp = pz.TcpClient("192.168.1.80", 9100, on_line=print)   # una impresora de etiquetas, la consola de un PLC...
tcp.connect()
tcp.send_line("~HS")
```

## Modbus

```python
medidor = pz.ModbusClient("192.168.1.40", unit=1, poll="""
    tension   input 0  float32
    potencia  input 12 float32
    rele      coils 0
""", interval=1000, on_update=self.mostrar)
medidor.connect()

def mostrar(self, valores):       # {"tension": 230.4, "potencia": 1487.3, "rele": True}
    self.potencia = valores["potencia"]

medidor.write_coil(0, False)                      # apaga el relé
medidor.write(100, 21.5, "float32")               # una consigna en dos registros holding
medidor.read_holding_registers(0, 4)              # [0, 17, 230, 1]
```

Con `serial_port="/dev/ttyUSB0"` (y `baud_rate`, `parity`) en lugar de un host habla Modbus RTU
por un adaptador RS-485. Cada línea de `poll` es `nombre tabla dirección [formato] [cantidad]`:
la tabla es `coils`, `discrete`, `holding` o `input`, el formato `uint16` (por defecto),
`int16`, `int32`, `uint32`, `float32`, `int64` o `float64`; `word_order="little"` es para los
dispositivos que ponen primero la palabra baja. El mapa de registros está en el manual del
dispositivo. Las llamadas esperan como mucho `timeout` milisegundos y lanzan
`pyzed.iot.ModbusError` si el dispositivo rechaza la petición o no responde.

![El ejemplo del medidor de energía Modbus](/pyzed/media/iot/meter.webp)

## Encontrar dispositivos en la red

```python
buscador = pz.DeviceDiscovery("_http._tcp", on_found=lambda d: print(d.name, d.address, d.properties))
buscador.start()      # busca ahora y cada 30 segundos; buscador.scan() busca una vez
```

`service` es un tipo de mDNS/Bonjour: `"_http._tcp"` (páginas web), `"_ipp._tcp"`
(impresoras), `"_googlecast._tcp"`, `"_esphomelib._tcp"`, `"_hap._tcp"` (HomeKit)...; si lo dejas
vacío se preguntan todos los tipos. SSDP/UPnP encuentra también televisores, routers y
servidores multimedia (`ssdp=False` lo apaga). Cada `Device` tiene `name`, `host`, `port`,
`hostname` (`esp32.local`), `service` y `properties` (el registro TXT, o el fabricante y el
modelo de un dispositivo UPnP). `lost` se lanza cuando un dispositivo deja de responder durante
dos búsquedas. `pyzed.iot.resolve_local("raspberrypi.local")` busca una sola dirección.

![El ejemplo del escáner de red encontrando dispositivos](/pyzed/media/iot/scanner.webp)

## Bluetooth LE

```python
escaner = pz.BluetoothScanner(services="heart_rate", on_found=lambda d: print(d.name, d.address, d.rssi))
escaner.scan()

banda = pz.BluetoothDevice(name="Polar", notify="heart_rate_measurement", on_notification=self.latido)
banda.connect()

def latido(self, aviso):
    self.ppm = aviso.data[1]

banda.read("battery_level")          # b"\x5a" (90 %)
banda.write("nordic_uart_rx", "hola")
```

Las características y servicios pueden ser UUID completos, cortos (`"2a37"`, `"180d"`) o los
nombres de `pyzed.iot.bluetooth.KNOWN` (`battery_level`, `heart_rate_measurement`,
`temperature`, `humidity`, `nordic_uart_tx`...). `read` y `write` esperan al dispositivo:
llámalos desde un manejador o un [`pz.Worker`](/pyzed/es/guides/services/). En Linux usa BlueZ,
en Windows el Bluetooth del sistema (Windows 10 o posterior) y en macOS CoreBluetooth, que pide
permiso al usuario la primera vez.

## En Pyzed Design

![Añadir un cliente MQTT y un puerto serie desde la categoría IoT: van a la bandeja bajo el formulario, y un doble clic abre el manejador del mensaje](/pyzed/media/iot/tray.webp)

Busca **IoT** en la caja de herramientas (o escribe `mqtt`, `serial`, `modbus`...) y haz clic en
un componente: va a la bandeja bajo el formulario. Sus propiedades son las del servicio (el
broker, los temas, el puerto, las líneas de lectura...), **Conectar al abrir** lo conecta cuando
se abre el formulario y **Reconectar (ms)** lo recupera tras un corte. Un doble clic abre el
manejador de su evento principal (`message`, `line`, `update`, `notification`), y los
manejadores lo usan por su nombre:

```python
def mqtt_client1_message(form, event):
    if event.value.topic == "casa/salon/temperatura":
        form.label1.text = f"Temperatura: {event.value.value} °C"


def button1_click(form, event):
    form.mqtt_client1.publish("casa/lampara/set", "on")
```

## Probar sin hardware

`pyzed.iot.testing` trae sustitutos pequeños que corren en tu equipo, para pruebas, demos y
capturas: `MqttBroker` (QoS 0 a 2, mensajes retenidos, usuarios), `WebSocketServer`,
`ModbusServer` (rellena sus coils y registros), `FakeNetwork` (dispositivos que responden a
`DeviceDiscovery`) y `serial_pair()` (un cable serie virtual, Linux y macOS).

```python
from pyzed.iot.testing import MqttBroker

def test_el_panel_muestra_la_temperatura():
    with MqttBroker() as broker:
        app = Panel("127.0.0.1", broker.port)
        app.mqtt.wait_connected()
        broker.publish("casa/salon/temperatura", "21.5")
        ...
```

Los cuatro ejemplos IoT de la [galería](/pyzed/es/editor/examples/) (Panel MQTT, Monitor serie,
Medidor de energía Modbus, Escáner de red) los usan cuando no hay dispositivo, así que funcionan
en cualquier equipo. Mira la [referencia](/pyzed/es/reference/iot/) para cada propiedad y método.
