import asyncio
import json
import threading
import time
from concurrent.futures import TimeoutError as FutureTimeoutError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
import spidev

HOST = "0.0.0.0"
PORT = 8000
DEVICE_NAME = "IOT-PicoW"
STATE_CHARACTERISTIC_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
PIXEL_COUNT = 64

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1_000_000
spi.mode = 0
state_lock = threading.Lock()
stop_server = threading.Event()
display_on = False
connected = False
ble_loop: Optional[asyncio.AbstractEventLoop] = None
ble_client: Optional[BleakClient] = None


def write_matrix_register(register, value):
    spi.xfer2([register, value])


def set_matrix(on):
    row_value = 0xFF if on else 0x00
    for row in range(1, 9):
        write_matrix_register(row, row_value)


write_matrix_register(0x0F, 0x00)
write_matrix_register(0x0C, 0x00)
write_matrix_register(0x0B, 0x07)
write_matrix_register(0x09, 0x00)
write_matrix_register(0x0A, 0x04)
set_matrix(False)
write_matrix_register(0x0C, 0x01)


class DashboardHandler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/status":
            with state_lock:
                payload = {"connected": connected, "display_on": display_on}
            self._send_json(200, payload)
            return

        if self.path != "/":
            self.send_error(404)
            return

        body = Path(__file__).with_name("dashboard.html").read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/control":
            self.send_error(404)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if not 0 < content_length <= 1024:
                raise ValueError
            payload = json.loads(self.rfile.read(content_length))
        except ValueError:
            self._send_json(400, {"error": "Požadavek musí obsahovat platný JSON."})
            return

        if not isinstance(payload, dict) or not isinstance(payload.get("on"), bool):
            self._send_json(400, {"error": "Hodnota on musí být true nebo false."})
            return

        with state_lock:
            client = ble_client
            loop = ble_loop
            is_connected = connected
        if not is_connected or client is None or loop is None:
            self._send_json(503, {"error": "Pico W není připojeno přes Bluetooth."})
            return

        try:
            command = client.write_gatt_char(
                STATE_CHARACTERISTIC_UUID,
                bytes((int(payload["on"]),)),
                response=True,
            )
            asyncio.run_coroutine_threadsafe(command, loop).result(timeout=5)
        except (BleakError, OSError, asyncio.TimeoutError, FutureTimeoutError) as error:
            self._send_json(502, {"error": f"Příkaz se nepodařilo odeslat do Pico W: {error}"})
            return

        self._send_json(200, {"ok": True, "display_on": payload["on"]})


def handle_notification(_sender, data):
    global display_on, connected

    if len(data) != 1 or data[0] not in (0, 1):
        print(f"Neplatná zpráva z Pico: {bytes(data)!r}")
        return

    with state_lock:
        display_on = bool(data[0])
        connected = True
        set_matrix(display_on)


def set_disconnected():
    global ble_client, connected, display_on

    with state_lock:
        ble_client = None
        connected = False
        display_on = False
        set_matrix(False)


async def connect_to_pico():
    global ble_client, ble_loop

    ble_loop = asyncio.get_running_loop()
    while not stop_server.is_set():
        try:
            device = await BleakScanner.find_device_by_filter(
                lambda candidate, advertisement: (
                    candidate.name == DEVICE_NAME
                    or advertisement.local_name == DEVICE_NAME
                ),
                timeout=5,
            )
            if device is None:
                print(f"Hledám Bluetooth zařízení {DEVICE_NAME}…")
                continue

            print(f"Připojuji se k {DEVICE_NAME}.")
            async with BleakClient(device) as client:
                with state_lock:
                    ble_client = client
                await client.start_notify(
                    STATE_CHARACTERISTIC_UUID,
                    handle_notification,
                )
                initial_state = await client.read_gatt_char(
                    STATE_CHARACTERISTIC_UUID
                )
                handle_notification(STATE_CHARACTERISTIC_UUID, initial_state)
                print(f"Bluetooth spojení s {DEVICE_NAME} navázáno.")
                while client.is_connected and not stop_server.is_set():
                    await asyncio.sleep(0.5)
        except (BleakError, OSError, asyncio.TimeoutError) as error:
            print(f"Bluetooth spojení selhalo: {error}")
            await asyncio.sleep(2)
        finally:
            set_disconnected()


server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
server_thread = threading.Thread(target=server.serve_forever, daemon=True)
server_thread.start()
print(f"Dashboard běží na http://<IP-Raspberry-Pi>:{PORT}")

try:
    asyncio.run(connect_to_pico())
except KeyboardInterrupt:
    print("\nUkončuji dashboard.")
finally:
    stop_server.set()
    server.shutdown()
    server.server_close()
    set_disconnected()
    spi.close()
