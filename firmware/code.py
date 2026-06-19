import math

import board
import terminalio
from displayio import Group, release_displays
from adafruit_display_text import label
from adafruit_74hc595 import ShiftRegister74HC595
from adafruit_st7735 import ST7735
from analogio import AnalogIn, AnalogOut
from audiobusio import I2SOut
from digitalio import DigitalInOut, Direction
from fourwire import FourWire
from synthio import Synthesizer

from midi_tools import note_or_name

board_voltage = 3.3
voltage_tolerance = 0.5

# Shift register init
sr_latch_pin = DigitalInOut(board.D9)
sr = ShiftRegister74HC595(board.SPI(), sr_latch_pin)

select_pins = [sr.get_pin(pin) for pin in range(1, 5)]
for pin in select_pins:
    pin.direction = Direction.OUTPUT

# Analog multiplexer init

mux_pin = AnalogIn(board.A0)
# mux_pins = ["1", "3", "5", "7", "9", "11", "13", "row0", "col0", "col1", "col2", "row1", "row2", "loop", "invert", "octave"]

# Inputs init
row_pins = [7, 11, 12]
col_pins = [8, 9, 10]
keys = [["I", "II", "III"], ["IV", "V", "VI"], ["VII", "keyup", "keydown"]]
chord_labels = ["I", "II", "III", "IV", "V", "VI", "VII"]
pressed_keys = []

pot_voltage_bounds = [[0.0, 0.5], [0.6, 1.0], [1.2, 1.8], [2.0, 2.6], [2.8, 3.3]] # TODO: Fill with actual voltage max/min boundary at each marking when testing the physical board

invert_pin = 14
octave_pin = 13
loop_pin = 15

# TFT screen init
release_displays()

display_bus = FourWire(board.SPI(), command=board.D2, chip_select=board.D7)
display = ST7735(display_bus, width=160, height=80, rotation=180)

splash = Group()
text_group = Group(scale=2, x=10, y=10) # TODO: Figure out a good offset for the words when testing physical board

# DAC for speaker init
audio = I2SOut(board.D5, board.D1, board.D4)

# Synth for playing music
synth = Synthesizer(sample_rate=44100)
audio.play(synth)

# Processing variables init
current_octave = 4
current_key = note_or_name(f"C{current_octave}")
root_note = current_key
rel_notes = []
notes = []

CHORD_NAMES = {
    "maj": [0, 4, 7],
    "min": [0, 3, 7],
    "aug": [0, 4, 8],
    "dim": [0, 3, 6],
    "sus": [0, 5, 7],
    "sus2": [0, 2, 7],
    "6": [0, 4, 7, 9],
    "(add2), (add9)": [0, 2, 4, 7],
    "maj7": [0, 4, 7, 11],
    "7": [0, 4, 7, 10],
    "7♭5": [0, 4, 6, 10],
    "7sus": [0, 5, 7, 10],
    "m(add2), m(add9)": [0, 2, 3, 7],
    "m6": [0, 3, 7, 9],
    "m7": [0, 3, 7, 10],
    "m(maj7)": [0, 3, 7, 11],
    "m7♭5": [0, 3, 6, 10],
    "dim7": [0, 3, 6, 9],
    "5": [0, 7],
    "maj7♯11": [0, 4, 7, 11, 18],
    "maj9": [0, 4, 7, 11, 14],
    "7♯9": [0, 4, 7, 10, 15],
    "9": [0, 4, 7, 10, 14],
    "11, 9(sus4)": [0, 7, 10, 14, 17],
    "13": [0, 4, 7, 10, 14, 21],
    "m9": [0, 3, 7, 10, 14],
    "m11": [0, 3, 7, 10, 17]
}

chord_sequence = []
timer = 0
time_sequence = []
is_recording_loop = False
loop_pos = 0

def get_analog_voltage(mux_pin):
    return (mux_pin.value / 65536)*board_voltage


def number_to_bits(number):
    number = number & 0xF
    return format(number, '04b')


def bits_to_booleans(bits: str):
    booleans = []
    for bit in bits:
        booleans.append(True if bit == '1' else False)
    return booleans


def set_select_pins(pin, select_pins):
    booleans = bits_to_booleans(number_to_bits(pin))
    i = 0
    while i < 4:
        select_pins[i].value = booleans[i]
        i += 1


def raise_key(key):
    key += 1
    if key > note_or_name(f"C{current_octave+1}"):
        key - 12
    return key


def lower_key(key):
    key -= 1
    if key < note_or_name(f"C{current_octave-1}"):
        key + 12
    return key


def get_rel_note_num_from_index(index):
    return index*2


def get_note_mod_from_index(index):
    return index - 2


def invert_chord(notes, voltage):
    num_inversions = math.floor(board_voltage - voltage)/(board_voltage/len(notes)) # Assuming linear voltage by slider's distance, divide voltage by the proportion of the slider's distance
    if num_inversions == 0:
        return notes
    shifted_notes = [(note - 12) for note in notes[-num_inversions:]]
    del notes[-num_inversions:]
    return shifted_notes + notes


def cycle_octave(octave):
    octave += 1
    if octave > 6:
        octave = 2
    return octave


def update_key(key):
    keystring = note_or_name(key)[-1] # Isolates the key without the octave designation
    return note_or_name(f"{keystring}{current_octave}")


def next_loop_pos(pos, len):
    pos += 1
    if pos >= len:
        pos = 0
    return pos


def get_chord_notes(notes):
    string = ""
    for note in notes:
        string += f"{note_or_name(notes)}   "
    return string


def get_chord_name(rel_notes):
    reordered_notes = [note + 12 if note < 0 else note for note in rel_notes]

    for name, notes in CHORD_NAMES.items():
        if notes == reordered_notes:
            return f" - {name}"
    return ""


def get_base_note(notes):
    if notes[0] != 0:
        return f" / {note_or_name(notes[0])}"
    else:
        return ""

while True:
    # Read from Analog Multiplexer first
    pin_readings = []
    pressed_keys = []
    for pin in range(0, 16):
        set_select_pins(pin, select_pins)

        pin_readings.append(get_analog_voltage(mux_pin))

        if pin in row_pins:
            mux_pin.deinit()
            mux_pin = AnalogOut(board.A0)
            mux_pin.value = 0
            for col in col_pins:
                set_select_pins(col, select_pins)

                mux_pin.deinit()
                mux_pin = AnalogIn(board.A0)
                if abs(get_analog_voltage(mux_pin)-board_voltage) <= voltage_tolerance:
                    pressed_keys.append(keys[pin][col])

    pot_readings = pin_readings[:7]
    for reading_index, reading in enumerate(pot_readings):
        for bound_index, bound in enumerate(pot_voltage_bounds):
            if bound[0] <= reading <= bound[1]:
                note = get_rel_note_num_from_index(reading_index)
                mod = get_note_mod_from_index(bound_index)
                rel_notes.append(note + mod)
                break

    invert_chord(rel_notes, pin_readings[invert_pin])

    if abs(pin_readings[octave_pin] - board_voltage) < voltage_tolerance:
        current_octave = cycle_octave(current_octave)
        current_key = update_key(current_key)

    if abs(pin_readings[loop_pin] - board_voltage) < voltage_tolerance:
        if not is_recording_loop: #Reset at the beginning of each record
            chord_sequence.clear()
            time_sequence.clear()
            timer = 0
            loop_pos = 0
            is_recording_loop = True
        timer += 1
    else:
        if is_recording_loop:
            time_sequence.append(timer)
            timer = 0
            is_recording_loop = False
        if timer > time_sequence[loop_pos]:
            synth.release(chord_sequence[loop_pos])
            loop_pos = next_loop_pos(loop_pos, len(time_sequence))
            synth.press(chord_sequence[loop_pos])

        timer += 1

    for key in pressed_keys:
        if key in chord_labels:
            root_note = current_key + chord_labels.index(key)
            synth.release(notes)
            notes.clear()

            notes = [int(note + root_note) for note in rel_notes]
            synth.press(notes)

            text = f"{note_or_name(current_key)}{get_chord_name(rel_notes)}{get_base_note(notes)} \n {get_chord_notes(notes)}"
            text_label = label.Label(terminalio.FONT, text=text)
            text_group.append(text_label)
            splash.append(text_group)

            if is_recording_loop:
                if timer != 0:
                    time_sequence.append(timer)
                    timer = 0
                chord_sequence.append(notes)
            else:
                chord_sequence.clear()
                time_sequence.clear()

        elif key == "keyup":
            current_key = raise_key(current_key)
        elif key == "keydown":
            current_key = lower_key(current_key)
