"""IoT: services that talk to devices: boards on a serial port, MQTT brokers, WebSockets, UDP and TCP sockets,
Modbus PLCs and meters, Bluetooth LE gadgets, and what answers on the local network.

They work like the ones in ``pyzed.services``: handlers are given as ``on_<event>=``, the
connection runs in a thread of its own, and events reach the handlers on the app's thread,
so they can change the app's state. In Pyzed Design they are non-visual components of the
IoT category, in the tray under the form::

    import pyzed as pz

    board = pz.SerialPort(match="arduino", baud_rate=115200, on_line=print)
    board.connect()

    mqtt = pz.MqttClient("broker.local", subscribe="home/#", on_message=lambda m: print(m.topic, m.value))
    mqtt.connect()
    mqtt.publish("home/lamp/set", "on")

====================  ===================================================================
``SerialPort``        A serial or USB serial port, line by line (``line``, ``data``).
``SerialWatcher``     Serial devices plugged in and unplugged (``plugged``, ``unplugged``).
``MqttClient``        Publishes and subscribes on an MQTT broker (``message``).
``WebSocket``         A WebSocket client (``message``).
``UdpSocket``         Sends and receives UDP datagrams, broadcast and multicast (``message``).
``TcpClient``         A TCP connection, line by line (``line``, ``data``).
``ModbusClient``      Reads and writes a Modbus TCP or RTU device; polls values (``update``).
``DeviceDiscovery``   Finds devices on the network with mDNS/Bonjour and SSDP/UPnP (``found``).
``BluetoothScanner``  Finds Bluetooth LE devices nearby (``found``); needs ``bleak``.
``BluetoothDevice``   Reads, writes and follows a Bluetooth LE device (``notification``).
====================  ===================================================================

Every connection has ``connect()``, ``disconnect()``, ``connected`` and the events
``connected``, ``disconnected`` and ``failed``; with ``reconnect`` (milliseconds) it comes
back by itself after the device or the network drops.
"""

from __future__ import annotations

from ._base import Connection
from .bluetooth import BleDevice, BleNotification, BluetoothDevice, BluetoothScanner
from .discovery import Device, DeviceDiscovery, resolve_local
from .modbus import ModbusClient, ModbusError
from .mqtt import MqttClient, MqttError, MqttMessage, topic_matches
from .serial import PortInfo, SerialPort, SerialWatcher, serial_ports
from .sockets import TcpClient, UdpMessage, UdpSocket
from .websocket import WebSocket, WebSocketError

__all__ = [
    "BleDevice", "BleNotification", "BluetoothDevice", "BluetoothScanner", "Connection", "Device", "DeviceDiscovery",
    "ModbusClient", "ModbusError", "MqttClient", "MqttError", "MqttMessage", "PortInfo", "SerialPort",
    "SerialWatcher", "TcpClient", "UdpMessage", "UdpSocket", "WebSocket", "WebSocketError", "resolve_local",
    "serial_ports", "topic_matches",
]
