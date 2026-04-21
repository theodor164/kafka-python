import RPi.GPIO as GPIO
import dht11
import time
import datetime

# initialize GPIO
GPIO.setwarnings(True)
GPIO.setmode(GPIO.BCM)

# read data using pin 14
instance = dht11.DHT11(pin=7)

def printTemperatureAndHumidity():
	try:
		while True:
			result = instance.read()
			if result.is_valid():
					timeStamp = str(datetime.datetime.now())
					temperature = result.temperature
					humidity = result.humidity
					message = str(timeStamp) + " " + str(temperature) + " " + str(humidity)
					return message


	except KeyboardInterrupt:
			print("Cleanup")
			GPIO.cleanup()



