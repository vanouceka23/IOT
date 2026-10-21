import bluetooth
from machine import Pin
from time import sleep_ms, ticks_diff, ticks_ms

DEVICE_NAME = "IOT-PicoW"
SERVICE_UUID = bluetooth.UUID("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
STATE_CHARACTERISTIC_UUID = bluetooth.UUID(
    "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
)
IRQ_CENTRAL_CONNECT = 1
IRQ_CENTRAL_DISCONNECT = 2
IRQ_GATTS_WRITE = 3
DEBOUNCE_MS = 40

button = Pin(15, Pin.IN, Pin.PULL_UP)
ble = bluetooth.BLE()
ble.active(True)

((state_handle,),) = ble.gatts_register_services(
    (
        (
            SERVICE_UUID,
            (
                (
                    STATE_CHARACTERISTIC_UUID,
                    bluetooth.FLAG_READ | bluetooth.FLAG_WRITE | bluetooth.FLAG_NOTIFY,
                ),
            ),
        ),
    )
)


def advertising_payload(name):
    name_bytes = name.encode()
    return bytearray((2, 0x01, 0x06, len(name_bytes) + 1, 0x09)) + name_bytes


connections = set()
display_on = False


def notify_state(connection_handle):
    ble.gatts_notify(connection_handle, state_handle, bytes((int(display_on),)))


def on_bluetooth_event(event, data):
    global display_on

    if event == IRQ_CENTRAL_CONNECT:
        connection_handle, _, _ = data
        connections.add(connection_handle)
    elif event == IRQ_CENTRAL_DISCONNECT:
        connection_handle, _, _ = data
        connections.discard(connection_handle)
        ble.gap_advertise(100_000, adv_data=payload)
    elif event == IRQ_GATTS_WRITE:
        _, attribute_handle = data
        if attribute_handle == state_handle:
            value = ble.gatts_read(state_handle)
            if len(value) == 1 and value[0] in (0, 1):
                display_on = bool(value[0])
                for connection_handle in tuple(connections):
                    try:
                        notify_state(connection_handle)
                    except OSError:
                        connections.discard(connection_handle)


ble.irq(on_bluetooth_event)
payload = advertising_payload(DEVICE_NAME)
ble.gatts_write(state_handle, bytes((int(display_on),)))
ble.gap_advertise(100_000, adv_data=payload)

raw_pressed = button.value() == 0
stable_pressed = raw_pressed
changed_at = ticks_ms()

while True:
    pressed = button.value() == 0
    now = ticks_ms()

    if pressed != raw_pressed:
        raw_pressed = pressed
        changed_at = now
    elif pressed != stable_pressed and ticks_diff(now, changed_at) >= DEBOUNCE_MS:
        stable_pressed = pressed
        if stable_pressed:
            display_on = not display_on
            ble.gatts_write(state_handle, bytes((int(display_on),)))
            for connection_handle in tuple(connections):
                try:
                    notify_state(connection_handle)
                except OSError:
                    connections.discard(connection_handle)

    sleep_ms(10)
