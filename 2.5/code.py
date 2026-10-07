import bluetooth
import utime
from machine import Pin
from micropython import const
 
 
# Nahraj tento soubor na obe Pico W a pro kazde nastav spravnou roli.
DEVICE_ROLE = "button"
 
SERVICE_UUID = bluetooth.UUID("9f4c0001-7c3a-4b8e-9d2a-6a1b5c8d0001")
CHARACTERISTIC_UUID = bluetooth.UUID("9f4c0002-7c3a-4b8e-9d2a-6a1b5c8d0001")
LED_DEVICE_NAME = b"PICO-LED"
 
_IRQ_CENTRAL_CONNECT = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE = const(3)
_IRQ_SCAN_RESULT = const(5)
_IRQ_PERIPHERAL_CONNECT = const(7)
_IRQ_PERIPHERAL_DISCONNECT = const(8)
_IRQ_GATTC_SERVICE_RESULT = const(9)
_IRQ_GATTC_SERVICE_DONE = const(10)
_IRQ_GATTC_CHARACTERISTIC_RESULT = const(11)
_IRQ_GATTC_CHARACTERISTIC_DONE = const(12)
 
 
def advertising_payload(name):
    return bytes((2, 0x01, 0x06, len(name) + 1, 0x09)) + name
 
 
def advertised_name(payload):
    index = 0
    while index < len(payload):
        field_length = payload[index]
        if field_length == 0:
            break
        field_end = index + field_length + 1
        if field_end > len(payload):
            break
        if payload[index + 1] in (0x08, 0x09):
            return payload[index + 2:field_end]
        index = field_end
    return b""
 
 
class LedPeripheral:
    def __init__(self, led):
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self._irq)
        self.led = led
        self.write_pending = False
        ((self.value_handle,),) = self.ble.gatts_register_services((
            (SERVICE_UUID, ((CHARACTERISTIC_UUID,
                             bluetooth.FLAG_WRITE |
                             bluetooth.FLAG_WRITE_NO_RESPONSE),)),
        ))
        self.ble.gatts_write(self.value_handle, b"\x00")
        self._advertise()
 
    def _advertise(self):
        self.ble.gap_advertise(
            100000, adv_data=advertising_payload(LED_DEVICE_NAME)
        )
 
    def _irq(self, event, data):
        if event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            if value_handle == self.value_handle:
                self.write_pending = True
        elif event == _IRQ_CENTRAL_DISCONNECT:
            self.led.off()
            self._advertise()
 
    def update_led(self):
        if self.write_pending:
            self.write_pending = False
            value = self.ble.gatts_read(self.value_handle)
            self.led.value(1 if value == b"\x01" else 0)
 
 
class ButtonCentral:
    def __init__(self):
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self._irq)
        self.conn_handle = None
        self.connecting = False
        self.service_range = None
        self.value_handle = None
        self.ready = False
        self.last_sent = None
        self._scan()
 
    def _scan(self):
        self.ble.gap_scan(0, 30000, 30000)
 
    def _irq(self, event, data):
        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data
            if (not self.connecting and self.conn_handle is None and
                    advertised_name(adv_data) == LED_DEVICE_NAME):
                self.connecting = True
                self.ble.gap_scan(None)
                self.ble.gap_connect(addr_type, addr)
        elif event == _IRQ_PERIPHERAL_CONNECT:
            self.conn_handle, addr_type, addr = data
            self.connecting = False
            self.ble.gattc_discover_services(self.conn_handle)
        elif event == _IRQ_GATTC_SERVICE_RESULT:
            conn_handle, start_handle, end_handle, uuid = data
            if conn_handle == self.conn_handle and uuid == SERVICE_UUID:
                self.service_range = (start_handle, end_handle)
        elif event == _IRQ_GATTC_SERVICE_DONE:
            conn_handle, status = data
            if conn_handle == self.conn_handle:
                if status == 0 and self.service_range is not None:
                    self.ble.gattc_discover_characteristics(
                        conn_handle, self.service_range[0],
                        self.service_range[1]
                    )
                else:
                    self.ble.gap_disconnect(conn_handle)
        elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
            conn_handle, def_handle, value_handle, properties, uuid = data
            if conn_handle == self.conn_handle and uuid == CHARACTERISTIC_UUID:
                self.value_handle = value_handle
        elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
            conn_handle, status = data
            if conn_handle == self.conn_handle:
                if status == 0 and self.value_handle is not None:
                    self.ready = True
                    self.last_sent = None
                else:
                    self.ble.gap_disconnect(conn_handle)
        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            self.conn_handle, addr_type, addr = data
            self.conn_handle = None
            self.connecting = False
            self.service_range = None
            self.value_handle = None
            self.ready = False
            self.last_sent = None
            self._scan()
 
    def send_button_state(self, pressed):
        if self.ready and pressed != self.last_sent:
            value = b"\x01" if pressed else b"\x00"
            self.ble.gattc_write(
                self.conn_handle, self.value_handle, value, 0
            )
            self.last_sent = pressed
 
 
if DEVICE_ROLE == "led":
    led = Pin(14, Pin.OUT)
    led.off()
    peripheral = LedPeripheral(led)
    while True:
        peripheral.update_led()
        utime.sleep_ms(100)
 
elif DEVICE_ROLE == "button":
    button = Pin(13, Pin.IN, Pin.PULL_UP)
    central = ButtonCentral()
    pressed = button.value() == 0
    candidate = pressed
    candidate_since = utime.ticks_ms()
 
    while True:
        reading = button.value() == 0
        if reading != candidate:
            candidate = reading
            candidate_since = utime.ticks_ms()
        elif candidate != pressed and utime.ticks_diff(
                utime.ticks_ms(), candidate_since) >= 30:
            pressed = candidate
 
        central.send_button_state(pressed)
        utime.sleep_ms(5)
 
else:
    raise ValueError('DEVICE_ROLE must be "led" or "button"')
 
 