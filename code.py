import board, digitalio, analogio, busio
import adafruit_74hc595

# Shift register init
sr_latch_pin = digitalio.DigitalInOut(board.D9)
sr = adafruit_74hc595.ShiftRegister74HC595(board.SPI(), sr_latch_pin)

select_pins = [sr.get_pin(pin) for pin in range(1, 5)]
for pin in select_pins:
    pin.direction = digitalio.Direction.OUTPUT

mux_pin = analogio.AnalogIn(board.A0)

mux_pins = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "ROW0", "COL0", "COL1", "COL2", "ROW1", "ROW2"]
row_pins = [7, 11, 12]
col_pins = [8, 9, 10]
keys = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
pressed_keys = []

def get_analog_voltage(mux_pin):
    return mux_pin.value / 65536


def number_to_bits(number):
    number = number & 0xF
    return format(number, '04b')


def bits_to_booleans(bits: str):
    booleans = []
    for bit in bits:
        booleans.append(True if bit == '1' else False)
    return booleans


while True:
    pin_readings = []
    for pin in range(0, 16):
        booleans = bits_to_booleans(number_to_bits(pin))
        i = 0
        while i < 4:
            select_pins[i].value = booleans[i]
            i += 1

        pin_readings.append(get_analog_voltage(mux_pin))

        if pin in row_pins:
            mux_pin.deinit()
            mux_pin = analogio.AnalogOut(board.A0)
            mux_pin.value = 0
            for col in col_pins:
                booleans = bits_to_booleans(number_to_bits(pin))
                i = 0
                while i < 4:
                    select_pins[i].value = booleans[i]
                    i += 1

                mux_pin.deinit()
                mux_pin = analogio.AnalogIn(board.A0)
                if mux_pin.value == 1:
                    pressed_keys.append(keys[pin][col])

