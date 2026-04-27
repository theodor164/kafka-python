import smbus2
import datetime

MPU6050_ADDR = 0x68
PWR_MGMT_1   = 0x6B
ACCEL_XOUT_H = 0x3B
GYRO_XOUT_H  = 0x43
TEMP_OUT_H   = 0x41

def read_word_2c(bus, reg):
    high = bus.read_byte_data(MPU6050_ADDR, reg)
    low  = bus.read_byte_data(MPU6050_ADDR, reg + 1)
    val  = (high << 8) + low
    return val - 65536 if val >= 0x8000 else val

def readMPU6050() -> dict | None:
    try:
        bus = smbus2.SMBus(1)
        bus.write_byte_data(MPU6050_ADDR, PWR_MGMT_1, 0)

        ax = round(read_word_2c(bus, ACCEL_XOUT_H)     / 16384.0, 4)
        ay = round(read_word_2c(bus, ACCEL_XOUT_H + 2) / 16384.0, 4)
        az = round(read_word_2c(bus, ACCEL_XOUT_H + 4) / 16384.0, 4)

        gx = round(read_word_2c(bus, GYRO_XOUT_H)     / 131.0, 4)
        gy = round(read_word_2c(bus, GYRO_XOUT_H + 2) / 131.0, 4)
        gz = round(read_word_2c(bus, GYRO_XOUT_H + 4) / 131.0, 4)

        temp = round(read_word_2c(bus, TEMP_OUT_H) / 340.0 + 36.53, 2)

        bus.close()

        return {
            "sensor_type": "mpu6050",
            "timestamp": datetime.datetime.now().isoformat(),
            "accel_x": ax, "accel_y": ay, "accel_z": az,
            "gyro_x":  gx, "gyro_y":  gy, "gyro_z":  gz,
            "temperature": temp,
        }
    except Exception as e:
        print(f"[MPU-6050] Eroare citire: {e}")
        return None