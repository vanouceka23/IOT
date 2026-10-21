import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import serial
import spidev

HOST = "0.0.0.0"
PORT = 8000
SERIAL_PORT = "/dev/serial0"
BAUD_RATE = 115200
ADC_MAX = 65535
PIXEL_COUNT = 64
CONNECTION_TIMEOUT = 2

uart = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1_000_000
spi.mode = 0
state_lock = threading.Lock()
stop_reader = threading.Event()
adc_raw = 0
pixels_lit = 0
last_update = None
control_mode = "auto"


def write_matrix_register(register, value):
    spi.xfer2([register, value])


def show_pixels(count):
    rows = [0] * 8
    for pixel in range(count):
        row, column = divmod(pixel, 8)
        rows[row] |= 1 << (7 - column)

    for row, value in enumerate(rows, start=1):
        write_matrix_register(row, value)


write_matrix_register(0x0F, 0x00)
write_matrix_register(0x0C, 0x00)
write_matrix_register(0x0B, 0x07)
write_matrix_register(0x09, 0x00)
write_matrix_register(0x0A, 0x04)
show_pixels(0)
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
                connected = (
                    last_update is not None
                    and time.monotonic() - last_update < CONNECTION_TIMEOUT
                )
                payload = {
                    "connected": connected,
                    "adc_raw": adc_raw if connected else 0,
                    "pixels_lit": pixels_lit,
                    "control_mode": control_mode,
                }
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
        global control_mode, pixels_lit

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

        if not isinstance(payload, dict):
            self._send_json(400, {"error": "Požadavek musí být JSON objekt."})
            return

        mode = payload.get("mode")
        if mode == "auto":
            with state_lock:
                control_mode = "auto"
                connected = (
                    last_update is not None
                    and time.monotonic() - last_update < CONNECTION_TIMEOUT
                )
                pixels_lit = round(adc_raw * PIXEL_COUNT / ADC_MAX) if connected else 0
                show_pixels(pixels_lit)
        elif mode == "manual":
            value = payload.get("pixels")
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 <= value <= PIXEL_COUNT
            ):
                self._send_json(400, {"error": "Počet pixelů musí být celé číslo od 0 do 64."})
                return
            with state_lock:
                control_mode = "manual"
                pixels_lit = value
                show_pixels(pixels_lit)
        else:
            self._send_json(400, {"error": "Režim musí být auto nebo manual."})
            return

        self._send_json(200, {
            "ok": True,
            "control_mode": control_mode,
            "pixels_lit": pixels_lit,
        })


def read_pico():
    global adc_raw, pixels_lit, last_update

    while not stop_reader.is_set():
        line = uart.readline()
        if not line:
            with state_lock:
                if (
                    last_update is not None
                    and time.monotonic() - last_update >= CONNECTION_TIMEOUT
                ):
                    adc_raw = 0
                    if control_mode == "auto":
                        pixels_lit = 0
                        show_pixels(0)
                    last_update = None
            continue

        try:
            value = int(line.decode("ascii").strip())
        except (UnicodeDecodeError, ValueError):
            print(f"Neplatná zpráva z Pico: {line!r}")
            continue

        if not 0 <= value <= ADC_MAX:
            print(f"Hodnota ADC mimo rozsah: {value}")
            continue

        with state_lock:
            adc_raw = value
            if control_mode == "auto":
                pixels_lit = round(value * PIXEL_COUNT / ADC_MAX)
                show_pixels(pixels_lit)
            last_update = time.monotonic()


server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
reader_thread = threading.Thread(target=read_pico, daemon=True)
reader_thread.start()
print(f"Dashboard běží na http://<IP-Raspberry-Pi>:{PORT}")

try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\nUkončuji dashboard.")
finally:
    stop_reader.set()
    reader_thread.join(timeout=2)
    server.server_close()
    uart.close()
    show_pixels(0)
    spi.close()
