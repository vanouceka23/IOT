import json
import math
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import serial
from gpiozero import PWMLED

HOST = "0.0.0.0"
PORT = 8000
SERIAL_PORT = "/dev/serial0"
BAUD_RATE = 115200
ADC_MAX = 65535
CONNECTION_TIMEOUT = 2

led = PWMLED(17)
uart = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
state_lock = threading.Lock()
stop_reader = threading.Event()
adc_raw = 0
brightness = 0
last_update = None
control_mode = "auto"


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
                    "brightness": brightness,
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
        global brightness, control_mode

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
                brightness = round(adc_raw * 100 / ADC_MAX) if connected else 0
                led.value = brightness / 100
        elif mode == "manual":
            value = payload.get("brightness")
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not 0 <= value <= 100
                or not math.isfinite(value)
            ):
                self._send_json(400, {"error": "Jas musí být číslo od 0 do 100."})
                return
            with state_lock:
                control_mode = "manual"
                brightness = round(value)
                led.value = brightness / 100
        else:
            self._send_json(400, {"error": "Režim musí být auto nebo manual."})
            return

        self._send_json(200, {
            "ok": True,
            "control_mode": control_mode,
            "brightness": brightness,
        })


def read_pico():
    global adc_raw, brightness, last_update

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
                        brightness = 0
                        led.off()
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
                brightness = round(value * 100 / ADC_MAX)
                led.value = value / ADC_MAX
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
    led.close()
