import board
import adafruit_ccs811
import datetime
import time
from i2c_lock import i2c_lock

_ccs = None

def _get_sensor():
    global _ccs
    if _ccs is None:
        i2c = board.I2C()   # ← aceeași instanță ca ADS1115
        _ccs = adafruit_ccs811.CCS811(i2c)
        _ccs.drive_mode = adafruit_ccs811.DRIVE_MODE_1SEC
        time.sleep(2)
    return _ccs

def readCCS811() -> dict | None:
    with i2c_lock:
        try:
            ccs = _get_sensor()
            timeout = 20
            while not ccs.data_ready and timeout > 0:
                time.sleep(0.1)
                timeout -= 1
            if not ccs.data_ready:
                return None
            eco2 = ccs.eco2
            tvoc = ccs.tvoc
            if eco2 == 0:
                return None
            return {
                "sensor_type": "ccs811",
                "timestamp":   datetime.datetime.now().isoformat(),
                "eco2_ppm":    eco2,
                "tvoc_ppb":    tvoc,
            }
        except Exception as e:
            print(f"[CCS811] Eroare citire: {e}")
            return None