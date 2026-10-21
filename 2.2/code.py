import json
import math
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from gpiozero import PWMLED

HOST = "0.0.0.0"
PORT = 8000

led = PWMLED(14)
brightness = 0
state_lock = threading.Lock()


class DashboardHandler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/status":
            with state_lock:
                payload = {"brightness": brightness}
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
        global brightness

        if self.path != "/api/brightness":
            self.send_error(404)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if not 0 < content_length <= 1024:
                raise ValueError
            payload = json.loads(self.rfile.read(content_length))
        except ValueError:
            self._send_json(400, {"error": "Požadavek musí obsahovat JSON s jasem 0 až 100."})
            return

        if not isinstance(payload, dict):
            self._send_json(400, {"error": "Požadavek musí obsahovat JSON s jasem 0 až 100."})
            return

        value = payload.get("brightness")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0 <= value <= 100
        ):
            self._send_json(400, {"error": "Jas musí být číslo od 0 do 100."})
            return

        with state_lock:
            brightness = round(value)
            led.value = brightness / 100

        self._send_json(200, {"ok": True, "brightness": brightness})


server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
print(f"Dashboard běží na http://<IP-Raspberry-Pi>:{PORT}")
try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\nUkončuji dashboard.")
finally:
    server.server_close()
    led.close()
