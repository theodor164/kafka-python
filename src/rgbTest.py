from gpiozero import RGBLED
from time import sleep

my_led = RGBLED(21, 20, 16)  # Common cathode

def colorSelection(color):
  if color == "red":
    my_led.color = (1, 0, 0)
  elif color == "green":
    my_led.color = (0, 1, 0)
  elif color == "blue":
    my_led.color = (0, 0, 1)
  else:
    my_led.color = (1, 1, 1)

