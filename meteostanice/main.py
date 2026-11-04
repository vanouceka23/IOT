
import bluetooth
import machine
import dht
import time
import struct
from micropython import const

# Bluetooth identifikace
DEVICE_NAME = "METEO_PICO"

SERVICE_UUID = bluetooth.UUID(
    "12345678-1234-5678-1234-56789abcdef0"
)

CHAR_UUID = bluetooth.UUID(
    "12345678-1234-5678-1234-56789abcdef1"
)

FLAG_READ = const(0x0002)
FLAG_NOTIFY = const(0x0010)

# Senzory
tmp = machine.ADC(26)
dht_sensor = dht.DHT22(machine.Pin(16))

# BLE
ble = bluetooth.BLE()
ble.active(True)

connections = set()

service = (
    SERVICE_UUID,
    (
        (CHAR_UUID, FLAG_READ | FLAG_NOTIFY),
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
    if event == 1:
        conn_handle, _, _ = data
        connections.add(conn_handle)
        print("Bluetooth pripojeno")

    elif event == 2:
        conn_handle, _, _ = data
        connections.discard(conn_handle)
        print("Bluetooth odpojeno")
        advertise()

ble.irq(ble_irq)

# Spusteni Bluetooth vysilani
advertise()

print("Meteo Pico W spusteno")

while True:

    try:
        # TMP36
        voltage = tmp.read_u16() * 3.3 / 65535
        temp_tmp = (voltage - 0.500) * 100

        # DHT22
        dht_sensor.measure()

        temp_dht = dht_sensor.temperature()
        humidity = dht_sensor.humidity()

        print("TMP36:", temp_tmp)
        print("DHT22:", temp_dht)
        print("Vlhkost:", humidity)

        # Tri hodnoty, kazda v setinach
        packet = struct.pack(
            "<hhh",
            round(temp_tmp * 100),
            round(temp_dht * 100),
            round(humidity * 100)
        )

        ble.gatts_write(char_handle, packet)

        # Odeslani pripojenemu Raspberry Pi
        for conn in list(connections):
            try:
                ble.gatts_notify(conn, char_handle)
            except OSError:
                pass

    except Exception as e:
        print("Chyba senzoru:", e)

    time.sleep(1)
