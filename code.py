import board, digitalio, analogio, busio, audiobusio, synthio
import adafruit_74hc595
from midi_tools import note_or_name
import math

board_voltage = 3.3
voltage_tolerance = 0.5

# Shift register init
sr_latch_pin = digitalio.DigitalInOut(board.D9)
sr = adafruit_74hc595.ShiftRegister74HC595(board.SPI(), sr_latch_pin)

select_pins = [sr.get_pin(pin) for pin in range(1, 5)]
for pin in select_pins:
    pin.direction = digitalio.Direction.OUTPUT

# Analog multiplexer init

mux_pin = analogio.AnalogIn(board.A0)
# mux_pins = ["1", "3", "5", "7", "9", "11", "13", "row0", "col0", "col1", "col2", "row1", "row2", "loop", "invert", "octave"]

# Inputs init
row_pins = [7, 11, 12]
col_pins = [8, 9, 10]
keys = [["i", "ii", "iii"], ["iv", "v", "vi"], ["vii", "keyup", "keydown"]]
chord_labels = ["i", "ii", "iii", "iv", "v", "vi", "vii"]
pressed_keys = []

pot_voltage_bounds = [[0.0, 0.5], [0.6, 1.0], [1.2, 1.8], [2.0, 2.6], [2.8, 3.3]] # Fill with actual voltage max/min boundary at each marking when testing the physical board

invert_pin = 14
octave_pin = 13
loop_pin = 15

# DAC for speaker init
audio = audiobusio.I2SOut(board.D5, board.D1, board.D4)

# Synth for playing music
synth = synthio.Synthesizer(sample_rate=44100)
audio.play(synth)

# Processing variables init
current_octave = 4
current_key = note_or_name(f"C{current_octave}")
root_note = current_key
rel_notes = []
notes = []
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
    keystring = note_or_name(key)[:1] # Isolates the key without the octave designation
    return note_or_name(f"{keystring}{current_octave}")


def next_loop_pos(pos, len):
    pos += 1
    if pos >= len:
        pos = 0
    return pos


while True:
    # Read from Analog Multiplexer first
    pin_readings = []
    pressed_keys = []
    for pin in range(0, 16):
        set_select_pins(pin, select_pins)

        pin_readings.append(get_analog_voltage(mux_pin))

        if pin in row_pins:
            mux_pin.deinit()
            mux_pin = analogio.AnalogOut(board.A0)
            mux_pin.value = 0
            for col in col_pins:
                set_select_pins(col, select_pins)

                mux_pin.deinit()
                mux_pin = analogio.AnalogIn(board.A0)
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

            if is_recording_loop:
                if timer != 0:
                    time_sequence.append(timer)
                    timer = 0
                chord_sequence.append(notes)

        elif key == "keyup":
            current_key = raise_key(current_key)
        elif key == "keydown":
            current_key = lower_key(current_key)