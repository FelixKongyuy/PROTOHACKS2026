# Air-gesture DJ effects controller
# Board: Raspberry Pi Pico running CircuitPython
# Parts: HC-SR04 ultrasonic sensor, KY-040 rotary encoder, RGB LED module
#
# Turn the dial to choose an effect (LED color shows which one).
# Move your hand over the sensor to control that effect's amount.
# Pull your hand away and the effect stays where you left it.
#
# ---------------- WIRING ----------------
# HC-SR04 ultrasonic (sensor facing UP):
#   VCC  -> Pico VBUS (pin 40, 5V from USB)
#   GND  -> Pico GND
#   Trig -> GP2
#   Echo -> 1k resistor -> GP3
#           and a 2k resistor from GP3 to GND
#           (this divider drops the 5V echo signal to a safe ~3.3V)
#
# KY-040 rotary encoder:
#   +    -> Pico 3V3 (pin 36)
#   GND  -> Pico GND
#   CLK  -> GP10
#   DT   -> GP11
#   SW   -> not used
#
# RGB LED module:
#   R    -> GP13
#   G    -> GP14
#   B    -> GP15
#   -    -> Pico GND
#   (If the module has no small resistors on it, put a 220 ohm
#    resistor in each of the R, G and B wires.)
#
# Libraries needed in CIRCUITPY/lib:
#   adafruit_hcsr04.mpy  and the  adafruit_midi  folder
# ----------------------------------------

import time
import board
import pwmio
import rotaryio
import usb_midi
import adafruit_midi
from adafruit_midi.control_change import ControlChange
import adafruit_hcsr04

# ---------------- SETTINGS ----------------
# Each effect: (name, MIDI knob number, LED color as (R, G, B) 0-255)
EFFECTS = [
    ("Filter",  20, (255, 0, 0)),     # red
    ("Echo",    21, (0, 255, 0)),     # green
    ("Reverb",  22, (0, 0, 255)),     # blue
    ("Flanger", 23, (255, 0, 255)),   # purple
]

MIN_CM = 5        # hand this close (or closer) = value 0
MAX_CM = 40       # hand this high = value 127; higher = "no hand"
SMOOTHING = 0.6   # 0 = jumpy, closer to 1 = smoother but slower
IDLE_BRIGHTNESS = 0.15   # LED brightness when no hand is present
# ------------------------------------------

# ---- Set up hardware ----
sonar = adafruit_hcsr04.HCSR04(trigger_pin=board.GP2, echo_pin=board.GP3)

# If one click of the dial skips two effects, change divisor to 4.
# If it takes two clicks to change effect, change divisor to 2.
encoder = rotaryio.IncrementalEncoder(board.GP10, board.GP11, divisor=4)

red = pwmio.PWMOut(board.GP13, frequency=1000)
green = pwmio.PWMOut(board.GP14, frequency=1000)
blue = pwmio.PWMOut(board.GP15, frequency=1000)

midi = adafruit_midi.MIDI(midi_out=usb_midi.ports[1], out_channel=0)


def set_led(color, brightness):
    """Show a color at a brightness from 0.0 to 1.0."""
    r, g, b = color
    red.duty_cycle = int(r / 255 * brightness * 65535)
    green.duty_cycle = int(g / 255 * brightness * 65535)
    blue.duty_cycle = int(b / 255 * brightness * 65535)


# ---- State ----
effect_index = 0
last_position = encoder.position
smoothed = None
last_value = -1

print("Ready. Effect:", EFFECTS[effect_index][0])

while True:
    # ---- 1. Read the dial: which effect are we controlling? ----
    position = encoder.position
    if position != last_position:
        effect_index = position % len(EFFECTS)
        last_position = position
        smoothed = None
        last_value = -1
        print("Effect:", EFFECTS[effect_index][0])

    name, cc_number, color = EFFECTS[effect_index]

    # ---- 2. Read the hand distance ----
    try:
        distance = sonar.distance   # in centimetres
    except RuntimeError:
        distance = None             # no echo came back = no hand

    # ---- 3. Hand present: send MIDI and brighten LED ----
    if distance is not None and distance <= MAX_CM:
        distance = max(MIN_CM, min(MAX_CM, distance))

        if smoothed is None:
            smoothed = distance
        smoothed = smoothed * SMOOTHING + distance * (1 - SMOOTHING)

        # Hand higher = bigger value (sound "opens up")
        value = int((smoothed - MIN_CM) / (MAX_CM - MIN_CM) * 127)

        if value != last_value:
            midi.send(ControlChange(cc_number, value))
            print(name, "| distance:", round(distance, 1), "cm -> value:", value)
            last_value = value

        set_led(color, 0.2 + 0.8 * value / 127)

    # ---- 4. No hand: freeze the effect, dim the LED ----
    else:
        smoothed = None
        set_led(color, IDLE_BRIGHTNESS)

    time.sleep(0.03)
