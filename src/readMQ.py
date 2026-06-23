import board
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import datetime
from i2c_lock import i2c_lock

_ads  = None
_ch0  = None
_ch1  = None

def _get_channels():
    global _ads, _ch0, _ch1
    if _ads is None:
        i2c  = board.I2C()   # ← singleton partajat
        _ads = ADS.ADS1115(i2c, address=0x48)
        _ads.gain = 1
        _ch0 = AnalogIn(_ads, 0)
        _ch1 = AnalogIn(_ads, 1)
    return _ch0, _ch1
def readMQ9() -> dict | None:
    global _ads, _ch0, _ch1
    with i2c_lock:
        try:
            chan_mq9, _ = _get_channels()
            voltage = chan_mq9.voltage
            return {
                "sensor_type": "mq9",
                "timestamp":   datetime.datetime.now().isoformat(),
                "voltage":     round(voltage, 4),
                "co_ppm": max(0.0, round((voltage / 3.3) * 1000, 2)),
            }
        except Exception as e:
            _ads = _ch0 = _ch1 = None  # ← reset la eroare
            print(f"[MQ-9] Eroare citire: {e}")
            return None

def readMQ135() -> dict | None:
    global _ads, _ch0, _ch1
    with i2c_lock:
        try:
            _, chan_mq135 = _get_channels()
            voltage = chan_mq135.voltage
            return {
                "sensor_type": "mq135",
                "timestamp":   datetime.datetime.now().isoformat(),
                "voltage":     round(voltage, 4),
                "air_quality_ppm": max(0.0, round(400 + (voltage / 3.3) * 600, 2))
            }
        except Exception as e:
            _ads = _ch0 = _ch1 = None  # ← reset la eroare
            print(f"[MQ-135] Eroare citire: {e}")
            return None

def readMQBoth() -> tuple:
    """Citește ambii senzori într-o singură tranzacție I2C."""
    global _ads, _ch0, _ch1
    with i2c_lock:
        try:
            ch0, ch1 = _get_channels()
            return ch0.voltage, ch1.voltage
        except Exception as e:
            _ads = _ch0 = _ch1 = None
            print(f"[MQ] Eroare citire: {e}")
            return None, None