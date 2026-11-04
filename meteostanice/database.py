
import sqlite3

DB_NAME = "meteo.db"

def create_database():
    conn = sqlite3.connect(DB_NAME)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            temp_tmp REAL,
            temp_dht REAL,
            humidity REAL
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp
        ON measurements(timestamp)
    """)

    conn.commit()
    conn.close()

def save_measurement(tmp, dht, humidity):
    conn = sqlite3.connect(DB_NAME)

    conn.execute("""
        INSERT INTO measurements
        (temp_tmp, temp_dht, humidity)
        VALUES (?, ?, ?)
    """, (tmp, dht, humidity))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_database()
    print("Databaze pripravena.")
