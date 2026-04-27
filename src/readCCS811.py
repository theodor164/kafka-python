import board
import busio
import adafruit_ccs811
import datetime
import time

def readCCS811() -> dict | None:
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        ccs = adafruit_ccs811.CCS811(i2c)

        # Așteptăm max 2s pentru prima citire
        timeout = 20
        while not ccs.data_ready and timeout > 0:
            time.sleep(0.1)
            timeout -= 1

        if not ccs.data_ready:
            return None

        eco2 = ccs.eco2
        tvoc = ccs.tvoc

        

        return {
            "sensor_type": "ccs811",
            "timestamp": datetime.datetime.now().isoformat(),
            "eco2_ppm": eco2,
            "tvoc_ppb": tvoc,
        }
    except Exception as e:
        print(f"[CCS811] Eroare citire: {e}")
        return None