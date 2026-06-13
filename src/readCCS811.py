import board
import busio
import adafruit_ccs811
import datetime
import time
from i2c_lock import i2c_lock 

_i2c = board.I2C()   # ← în loc de busio.I2C(board.SCL, board.SDA)
_ccs = None

def _get_sensor():
    global _i2c, _ccs
    if _ccs is None:
        _i2c = busio.I2C(board.SCL, board.SDA)
        _ccs = adafruit_ccs811.CCS811(_i2c)
        _ccs.drive_mode = adafruit_ccs811.DRIVE_MODE_1SEC
        time.sleep(2)  # pauză inițială pentru prima măsurătoare
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