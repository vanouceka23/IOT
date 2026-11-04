
import asyncio
import threading
import queue
import sqlite3
import struct
import time
from datetime import datetime

import tkinter as tk
from tkinter import ttk

from bleak import BleakScanner, BleakClient

import matplotlib
matplotlib.use("TkAgg")

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from database import create_database, save_measurement, DB_NAME


DEVICE_NAME = "METEO_PICO"

CHAR_UUID = "12345678-1234-5678-1234-56789abcdef1"

data_queue = queue.Queue()


# Bluetooth prijimac
async def bluetooth_receiver():

    while True:
        try:
            print("Hledam METEO_PICO...")

            device = await BleakScanner.find_device_by_filter(
                lambda d, ad:
                    d.name == DEVICE_NAME or ad.local_name == DEVICE_NAME,
                timeout=15
            )

            if device is None:
                print("Pico nenalezeno.")
                await asyncio.sleep(5)
                continue

            print("Pico nalezeno:", device.address)

            async with BleakClient(device) as client:

                def notification_handler(sender, data):

                    if len(data) != 6:
                        return

                    tmp, dht, humidity = struct.unpack("<hhh", data)

                    tmp = tmp / 100
                    dht = dht / 100
                    humidity = humidity / 100

                    timestamp = datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

                    save_measurement(tmp, dht, humidity)

                    data_queue.put(
                        (timestamp, tmp, dht, humidity)
                    )

                    print(
                        f"{timestamp} | "
                        f"{tmp:.2f} C | "
                        f"{dht:.2f} C | "
                        f"{humidity:.2f} %"
                    )

                await client.start_notify(
                    CHAR_UUID,
                    notification_handler
                )

                print("Bluetooth spojeni aktivni.")

                while client.is_connected:
                    await asyncio.sleep(1)

        except Exception as e:
            print("Bluetooth chyba:", e)

        await asyncio.sleep(5)


def bluetooth_thread():
    asyncio.run(bluetooth_receiver())


# Graficke rozhrani
class WeatherStation:

    def __init__(self, root):

        self.root = root
        self.root.title("DOMACI METEOSTANICE")
        self.root.geometry("1050x720")

        self.root.configure(bg="#17212b")

        title = tk.Label(
            root,
            text="DOMACI METEOSTANICE",
            font=("Arial", 23, "bold"),
            fg="white",
            bg="#17212b"
        )
        title.pack(pady=15)

        self.status = tk.Label(
            root,
            text="Cekam na Pico W...",
            font=("Arial", 12),
            fg="#55cc99",
            bg="#17212b"
        )
        self.status.pack()

        values = tk.Frame(root, bg="#17212b")
        values.pack(fill="x", padx=20, pady=20)

        self.tmp_label = self.create_value(
            values, "TMP36", "0.0 °C"
        )

        self.dht_label = self.create_value(
            values, "DHT22", "0.0 °C"
        )

        self.humidity_label = self.create_value(
            values, "VLHKOST", "0.0 %"
        )

        # Grafy
        self.figure = Figure(figsize=(9, 4), dpi=100)

        self.ax1 = self.figure.add_subplot(211)
        self.ax2 = self.figure.add_subplot(212)

        self.figure.tight_layout()

        self.canvas = FigureCanvasTkAgg(
            self.figure,
            master=root
        )

        self.canvas.get_tk_widget().pack(
            fill="both",
            expand=True,
            padx=20,
            pady=10
        )

        self.update_dashboard()

    def create_value(self, parent, title, initial):

        frame = tk.Frame(
            parent,
            bg="#263746",
            padx=20,
            pady=15
        )

        frame.pack(side="left", expand=True, fill="x", padx=8)

        tk.Label(
            frame,
            text=title,
            font=("Arial", 13, "bold"),
            fg="#8db9d8",
            bg="#263746"
        ).pack()

        label = tk.Label(
            frame,
            text=initial,
            font=("Arial", 25, "bold"),
            fg="white",
            bg="#263746"
        )

        label.pack(pady=8)

        return label

    def update_dashboard(self):

        received = False

        while not data_queue.empty():

            try:
                timestamp, tmp, dht, humidity = (
                    data_queue.get_nowait()
                )

                self.tmp_label.config(
                    text=f"{tmp:.1f} °C"
                )

                self.dht_label.config(
                    text=f"{dht:.1f} °C"
                )

                self.humidity_label.config(
                    text=f"{humidity:.1f} %"
                )

                self.status.config(
                    text="PICO W ONLINE",
                    fg="#55cc99"
                )

                received = True

            except queue.Empty:
                break

        if received:
            self.update_graph()

        self.root.after(1000, self.update_dashboard)

    def update_graph(self):

        conn = sqlite3.connect(DB_NAME)

        rows = conn.execute("""
            SELECT timestamp, temp_tmp, temp_dht, humidity
            FROM measurements
            ORDER BY id DESC
            LIMIT 2880
        """).fetchall()

        conn.close()

        rows.reverse()

        if not rows:
            return

        times = [
            datetime.strptime(r[0], "%Y-%m-%d %H:%M:%S")
            for r in rows
        ]

        tmp = [r[1] for r in rows]
        dht = [r[2] for r in rows]
        humidity = [r[3] for r in rows]

        self.ax1.clear()
        self.ax2.clear()

        self.ax1.plot(
            times, tmp,
            label="TMP36",
            color="orange"
        )

        self.ax1.plot(
            times, dht,
            label="DHT22",
            color="cyan"
        )

        self.ax1.set_title("VYVOJ TEPLOTY")
        self.ax1.set_ylabel("°C")
        self.ax1.legend()
        self.ax1.grid(True, alpha=0.3)

        self.ax2.plot(
            times, humidity,
            label="Vlhkost",
            color="green"
        )

        self.ax2.set_title("VYVOJ VLHKOSTI")
        self.ax2.set_ylabel("%")
        self.ax2.set_ylim(0, 100)
        self.ax2.grid(True, alpha=0.3)

        self.figure.tight_layout()
        self.canvas.draw_idle()


if __name__ == "__main__":

    create_database()

    threading.Thread(
        target=bluetooth_thread,
        daemon=True
    ).start()

    root = tk.Tk()

    app = WeatherStation(root)

    root.mainloop()
