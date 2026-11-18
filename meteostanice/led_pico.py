import bluetooth
import machine
import struct
import time
from micropython import const


DEVICE_NAME = "METEO_LED_PICO"
SERVICE_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdea0")
CHAR_UUID = bluetooth.UUID("12345678-1234-5678-1234-56789abcdea1")
TEMPERATURE_THRESHOLD = 30.0
TEMPERATURE_TIMEOUT_MS = 90000

FLAG_WRITE = const(0x0008)
IRQ_CENTRAL_CONNECT = const(1)
IRQ_CENTRAL_DISCONNECT = const(2)
IRQ_GATTS_WRITE = const(3)

led = machine.Pin("LED", machine.Pin.OUT)
led.value(0)
connections = set()
threshold_centi = round(TEMPERATURE_THRESHOLD * 100)
last_update_ms = time.ticks_ms()

ble = bluetooth.BLE()
ble.active(True)

service = (
    SERVICE_UUID,
    (
        (CHAR_UUID, FLAG_WRITE),
    ),
)

((char_handle,),) = ble.gatts_register_services((service,))


def advertise():
    name = DEVICE_NAME.encode()
    payload = (
        bytes((2, 0x01, 0x06))
        + bytes((len(name) + 1, 0x09))
        + name
    )
    ble.gap_advertise(100000, adv_data=payload)


def ble_irq(event, data):
    global last_update_ms

    if event == IRQ_CENTRAL_CONNECT:
        conn_handle, _, _ = data
        connections.add(conn_handle)
        return

    if event == IRQ_CENTRAL_DISCONNECT:
        conn_handle, _, _ = data
        connections.discard(conn_handle)
        if not connections:
            led.value(0)
        advertise()
        return

    if event != IRQ_GATTS_WRITE:
        return

    _, value_handle = data
    if value_handle != char_handle:
        return

    packet = ble.gatts_read(char_handle)
    if len(packet) != 2:
        print("Neplatny teplotni paket.")
        return

    temperature_centi = struct.unpack("<h", packet)[0]
    last_update_ms = time.ticks_ms()
    led.value(1 if temperature_centi > threshold_centi else 0)
    print("Teplota: {:.2f} C, LED: {}".format(
        temperature_centi / 100,
        "zapnuta" if led.value() else "vypnuta"
    ))


ble.irq(ble_irq)
advertise()

print("LED Pico W spusteno; limit: {:.1f} C".format(TEMPERATURE_THRESHOLD))

while True:
    if time.ticks_diff(time.ticks_ms(), last_update_ms) > TEMPERATURE_TIMEOUT_MS:
        led.value(0)
    time.sleep(1)
