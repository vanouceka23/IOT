import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import sleep

from gpiozero import LED, Button

HOST = "0.0.0.0"
PORT = 8000

led = LED(17)
tlacitko = Button(27)
state_lock = threading.Lock()
led_on = False


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
                payload = {"led_on": led.is_lit}
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
        global led_on

        if self.path != "/api/led":
            self.send_error(404)
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if not 0 < content_length <= 1024:
                raise ValueError
            payload = json.loads(self.rfile.read(content_length))
        except ValueError:
            self._send_json(400, {"error": "Požadavek musí obsahovat JSON s hodnotou on true/false."})
            return

        if not isinstance(payload, dict) or not isinstance(payload.get("on"), bool):
            self._send_json(400, {"error": "Hodnota on musí být true nebo false."})
            return

        with state_lock:
            led_on = payload["on"]
            led.value = led_on
        self._send_json(200, {"ok": True, "led_on": led_on})


server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
server_thread = threading.Thread(target=server.serve_forever, daemon=True)
server_thread.start()
print(f"Dashboard běží na http://<IP-Raspberry-Pi>:{PORT}")

try:
    while True:
        if tlacitko.is_pressed:
            led.on()
            sleep(0.5)
            led.off()
            sleep(0.5)
        else:
            with state_lock:
                led.value = led_on
            sleep(0.1)
except KeyboardInterrupt:
    print("\nUkončuji dashboard.")
finally:
    server.shutdown()
    server.server_close()
    led.close()
    tlacitko.close()
