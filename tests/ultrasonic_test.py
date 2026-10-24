# Ultrasonic sensor test: prints the distance to your hand.
# Copy this onto CIRCUITPY as code.py (temporarily) to check the HC-SR04 wiring.
# Wiring: VCC -> VBUS, GND -> GND, Trig -> GP2,
#         Echo -> 1k -> GP3, plus 2k from GP3 to GND

import time
import board
import adafruit_hcsr04

sonar = adafruit_hcsr04.HCSR04(trigger_pin=board.GP2, echo_pin=board.GP3)

while True:
    try:
        print("distance:", round(sonar.distance, 1), "cm")
    except RuntimeError:
        print("no echo (nothing in range, or check wiring)")
    time.sleep(0.2)
