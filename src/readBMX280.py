import smbus2
import bme280
import datetime
import json

# BMX280 GroundStudio - adresa I2C default (jumper OPEN = 0x77)
I2C_ADDRESS = 0x77
bus = smbus2.SMBus(1)

calibration_params = bme280.load_calibration_params(bus, I2C_ADDRESS)

def readSensorData():
    try:
        data = bme280.sample(bus, I2C_ADDRESS, calibration_params)
        timestamp = datetime.datetime.now().isoformat()
        message = {
            "timestamp": timestamp,
            "temperature": round(data.temperature, 2),
            "humidity": round(data.humidity, 2),
            "pressure": round(data.pressure, 2),
        }
        return json.dumps(message)
    except Exception as e:
        print(f"Eroare citire senzor: {e}")
        return None