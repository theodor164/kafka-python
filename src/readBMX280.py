import smbus2
import bme280
import datetime
import json

I2C_ADDRESS = 0x77

def readSensorData():
    try:
        # Inițializare la fiecare citire — nu la import
        bus = smbus2.SMBus(1)
        calibration_params = bme280.load_calibration_params(bus, I2C_ADDRESS)
        
        data = bme280.sample(bus, I2C_ADDRESS, calibration_params)
        timestamp = datetime.datetime.now().isoformat()
        message = {
            "sensor_type": "bme280",
            "timestamp": timestamp,
            "temperature": round(data.temperature, 2),
            "humidity": round(data.humidity, 2),
            "pressure": round(data.pressure, 2),
        }
        return message  # returnăm dict, nu JSON string
    except Exception as e:
        print(f"Eroare citire senzor: {e}")
        return None