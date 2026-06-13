import smbus2
import bme280
import datetime
from i2c_lock import i2c_lock

I2C_ADDRESS = 0x77

_bus               = None  # ← singleton
_calibration_params = None  # ← singleton

def _get_bus():
    global _bus, _calibration_params
    if _bus is None:
        _bus = smbus2.SMBus(1)
        _calibration_params = bme280.load_calibration_params(_bus, I2C_ADDRESS)
    return _bus, _calibration_params

def readSensorData():
    with i2c_lock:
        try:
            bus, calibration_params = _get_bus()
            data = bme280.sample(bus, I2C_ADDRESS, calibration_params)
            return {
                "sensor_type": "bme280",
                "timestamp":   datetime.datetime.now().isoformat(),
                "temperature": round(data.temperature, 2),
                "humidity":    round(data.humidity, 2),
                "pressure":    round(data.pressure, 2),
            }
        except Exception as e:
            print(f"Eroare citire senzor: {e}")
            return None