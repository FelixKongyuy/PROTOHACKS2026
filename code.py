# Air-gesture DJ effects controller
# Board: Raspberry Pi Pico running CircuitPython
# Parts: HC-SR04 ultrasonic sensor, KY-040 rotary encoder, RGB LED module
#
# Turn the dial to choose an effect (LED color shows which one).
# Move your hand over the sensor to control that effect's amount.
# Bring your hand in and the effect switches on; pull it away and it switches
# off, remembering the amount you left it at.
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
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff
import adafruit_hcsr04

# ---------------- SETTINGS ----------------
# Each effect: (name, MIDI knob number, on/off note, LED color as (R, G, B) 0-255)
EFFECTS = [
    ("Filter",  20, 60, (255, 0, 0)),     # red
    ("Echo",    21, 61, (0, 255, 0)),     # green
    ("Reverb",  22, 62, (0, 0, 255)),     # blue
    ("Flanger", 23, 63, (255, 0, 255)),   # purple
]

MIN_CM = 5        # hand this close (or closer) = value 0
MAX_CM = 30       # hand this high = value 127; higher = "no hand"
                  # (kept below ~35 so nearby people/screens don't count as a hand)
SMOOTHING = 0.6   # 0 = jumpy, closer to 1 = smoother but slower
IDLE_BRIGHTNESS = 0.15   # LED brightness when no hand is present

# Hand enters range = effect switches on, hand leaves = effect switches off.
AUTO_ON_OFF = True
# "tap":  a short button press when the hand enters and another when it leaves
#         (for an FX ON button that toggles on each press)
# "hold": button held down while the hand is in range
#         (use this if "tap" turns the effect on and straight back off)
SWITCH_STYLE = "tap"
LEAVE_DELAY = 0.25  # seconds without a hand before switching off (ignores brief dropouts)
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


def switch_effect(name, note, on):
    """Press the effect's on/off button in the DJ software."""
    if SWITCH_STYLE == "hold":
        midi.send(NoteOn(note, 127) if on else NoteOff(note, 0))
    else:
        midi.send(NoteOn(note, 127))
        midi.send(NoteOff(note, 0))
    print(name, "ON" if on else "OFF")


# ---- State ----
effect_index = 0
last_position = encoder.position
smoothed = None
last_value = -1
hand_present = False
last_seen = 0

print("Ready. Effect:", EFFECTS[effect_index][0])

while True:
    now = time.monotonic()

    # ---- 1. Read the dial: which effect are we controlling? ----
    position = encoder.position
    if position != last_position:
        # Switch the old effect off before moving to the next one
        if AUTO_ON_OFF and hand_present:
            old_name, _, old_note, _ = EFFECTS[effect_index]
            switch_effect(old_name, old_note, False)
        hand_present = False
        effect_index = position % len(EFFECTS)
        last_position = position
        smoothed = None
        last_value = -1
        print("Effect:", EFFECTS[effect_index][0])

    name, cc_number, note, color = EFFECTS[effect_index]

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

        # Hand just arrived: switch the effect on (after setting its amount)
        last_seen = now
        if not hand_present:
            hand_present = True
            if AUTO_ON_OFF:
                switch_effect(name, note, True)

        set_led(color, 0.2 + 0.8 * value / 127)

    # ---- 4. No hand: freeze the amount, dim the LED ----
    else:
        smoothed = None
        # Hand gone for long enough: switch the effect off
        if hand_present and now - last_seen > LEAVE_DELAY:
            hand_present = False
            if AUTO_ON_OFF:
                switch_effect(name, note, False)
        set_led(color, IDLE_BRIGHTNESS)

    time.sleep(0.03)
