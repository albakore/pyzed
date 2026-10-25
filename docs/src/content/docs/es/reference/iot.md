---
title: "IoT y dispositivos (pyzed.iot)"
description: "Referencia de la API de pyzed.iot: puertos serie y serie USB, MQTT, WebSocket, sockets UDP y TCP, Modbus TCP y RTU, descubrimiento en la red con mDNS/SSDP y Bluetooth LE para apps de escritorio en Python."
sidebar:
  order: 10.6
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs_es.py. -->

Servicios que hablan con dispositivos: placas en un puerto serie, brokers MQTT, WebSockets,
sockets UDP y TCP, PLC y medidores Modbus, aparatos Bluetooth LE y lo que responde en la red
local. Funcionan como los [servicios](/pyzed/es/reference/services/): los manejadores van en
`on_<evento>=`, la conexión corre en un hilo propio y los eventos llegan a los manejadores en
el hilo de la app. En Pyzed Design son los componentes de la categoría IoT. Mira la
[guía de IoT](/pyzed/es/guides/iot/).

```python
placa = pz.SerialPort(match="arduino", baud_rate=115200, on_line=self.lectura)
placa.connect()

mqtt = pz.MqttClient("broker.local", subscribe="casa/#", on_message=self.recibido)
mqtt.connect()
mqtt.publish("casa/lampara/set", "on")
```

Toda conexión tiene `connect()`, `disconnect()`, `connected`, `running` y los eventos
`connected`, `disconnected` y `failed`; con `reconnect` (milisegundos) vuelve sola.

## Puertos serie

### `SerialPort`

```python
class SerialPort
```

Un puerto serie o serie USB (Arduino, ESP32, Pico, GPS...): `port` lo nombra (`"COM3"`, `"/dev/ttyUSB0"`) o, vacío, se usa el primero que nombre `match` (`"arduino"`, `"2341:0043"`; vacío: el primer puerto USB). Lanza `data` (bytes) y `line` (texto); `write()`, `send_line()`, `reset()` (DTR), `set_baud_rate()`. `SerialPort.ports(match)` lista los puertos. Vuelve a abrir el dispositivo cuando regresa (`reconnect`, 1000 ms por defecto).

### `SerialWatcher`

```python
class SerialWatcher
```

Avisa cuando se enchufan y desenchufan dispositivos serie, cada `interval` milisegundos: `plugged` y `unplugged` con un `PortInfo` (`name`, `kind`, `vid`, `pid`, `usb_id`, `manufacturer`, `product`, `description`), `change` con la lista; `ports` es la última lista.

## Mensajes y sockets

### `MqttClient`

```python
class MqttClient
```

Un cliente MQTT 3.1.1 (Mosquitto, Home Assistant, EMQX...): `publish(tema, datos, qos, retain)`, `subscribe(tema)`, `unsubscribe()` y `on_topic(patrón, manejador)` con los comodines `+` y `#`. Cada mensaje lanza `message` con un `MqttMessage` (`topic`, `payload`, `text`, `value`, `json()`); `last` guarda el último de cada tema. TLS, usuario y contraseña, QoS 0, 1 y 2, último deseo (will) y las suscripciones se mantienen tras cada reconexión (2000 ms por defecto).

### `WebSocket`

```python
class WebSocket
```

Un cliente WebSocket (`ws://`, `wss://`): `send()` texto, bytes o JSON; cada mensaje lanza `message` (texto, bytes o, con `json=True`, los datos ya leídos). `headers`, `protocols` y un ping cada `ping_interval` milisegundos.

### `UdpSocket`

```python
class UdpSocket
```

Envía y recibe datagramas UDP: `start()` escucha en `port` y cada uno lanza `message` con un `UdpMessage` (`data`, `text`, `json()`, `host`, `port`); `send(datos, host, puerto)`, `reply(mensaje, datos)`, `broadcast` y `multicast_group`.

### `TcpClient`

```python
class TcpClient
```

Una conexión TCP (con TLS si se quiere) a un dispositivo o servidor: lanza `data` y `line`; `write()` y `send_line()`.

## Industrial

### `ModbusClient`

```python
class ModbusClient
```

Un cliente Modbus por TCP (`host`) o RTU (`serial_port`, RS-485): `read_coils`, `read_discrete_inputs`, `read_holding_registers`, `read_input_registers`, `read(tabla, dirección, formato)` (`"float32"`, `"int32"`...), `write_coil`, `write_register`, `write_coils`, `write_registers` y `write(dirección, valor, formato)`. Las líneas de `poll` (`nombre tabla dirección [formato] [cantidad]`) se leen cada `interval` milisegundos y lanzan `update` con un dict. Lanza `ModbusError` si el dispositivo rechaza la petición o no responde.

## Descubrimiento y Bluetooth

### `DeviceDiscovery`

```python
class DeviceDiscovery
```

Encuentra los dispositivos de la red local con mDNS/Bonjour (`service`: `"_http._tcp"`, `"_esphomelib._tcp"`...; vacío: todos) y SSDP/UPnP: `scan()`, `start()`; lanza `found` y `lost` con un `Device` (`name`, `host`, `port`, `address`, `kind`, `service`, `hostname`, `properties`, `url`), `change` y `done`. `pyzed.iot.resolve_local("esp32.local")` busca una dirección.

### `BluetoothScanner`

```python
class BluetoothScanner
```

Busca dispositivos Bluetooth LE cercanos durante `timeout` milisegundos, filtrados por `match` (nombre o dirección) y `services`: `scan()`, `start()`, `devices` (el más cercano primero); lanza `found` con un `BleDevice` (`address`, `name`, `rssi`, `uuids`, `manufacturer_data`), `change`, `done` y `failed`. Necesita `pip install "pyzed-ui[bluetooth]"` (bleak).

### `BluetoothDevice`

```python
class BluetoothDevice
```

Una conexión a un dispositivo Bluetooth LE por `address` o `name`: `read(uuid)`, `write(uuid, datos, response)`, `subscribe(uuid)`, `services()`; las características de `notify` lanzan `notification` con un `BleNotification` (`uuid`, `data`, `text`, `value`). Los UUID pueden ser cortos (`"2a37"`) o nombres (`"heart_rate_measurement"`, `"battery_level"`, `"nordic_uart_tx"`).
