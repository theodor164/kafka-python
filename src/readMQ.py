import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import datetime

def _get_channels():
    i2c = busio.I2C(board.SCL, board.SDA)
    ads = ADS.ADS1115(i2c, address=0x48)
    ads.gain = 1
    return AnalogIn(ads, 0), AnalogIn(ads, 1)

def readMQ9() -> dict | None:
    try:
        chan_mq9, _ = _get_channels()
        voltage = chan_mq9.voltage
        return {
            "sensor_type": "mq9",
            "timestamp": datetime.datetime.now().isoformat(),
            "voltage": round(voltage, 4),
            "co_ppm": round((voltage / 3.3) * 1000, 2),
        }
    except Exception as e:
        print(f"[MQ-9] Eroare citire: {e}")
        return None

def readMQ135() -> dict | None:
    try:
        _, chan_mq135 = _get_channels()
        voltage = chan_mq135.voltage
        return {
            "sensor_type": "mq135",
            "timestamp": datetime.datetime.now().isoformat(),
            "voltage": round(voltage, 4),
            "air_quality_ppm": round(400 + (voltage / 3.3) * 600, 2),
        }
    except Exception as e:
        print(f"[MQ-135] Eroare citire: {e}")
        return None