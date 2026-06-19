# Copied from https://github.com/CedarGroveStudios/CircuitPython_MIDI_Tools/blob/main/cedargrove_midi_tools.py

# Note names used by note_or_name, note_name, and name_note helpers
NOTE_BASE = ["C", "C#/D♭", "D", "D#/E♭", "E", "F", "F#/G♭", "G", "G#/A♭", "A", "A#/B♭", "B"]


def note_or_name(value):
    """Bidirectionally translates a MIDI sequential note value to a note name
    or a note name to a MIDI sequential note value. Note values are integers in
    the range of 0 to 127 (inclusive). Note names are character strings
    expressed in the format NoteOctave such as 'C4' or 'G#7'. Note names range
    from 'C-1' (note value 0) to 'F#9' (note value 127). If the input value is
    outside the note value or name range, the value of `None` is returned.

    :param union(int, str) value: The note name or note value input. Note value
    is an integer Note name is a string. No default value.
    """
    if isinstance(value, str):
        # Input is a string, so it's a note name
        return name_to_note(value)
    if isinstance(value, int):
        # Input is an integer, so it's a note value
        return note_to_name(value)
    return None  # Invalid input parameter type


def note_to_name(note):
    """Translates a MIDI sequential note value to a note name. Note values are
    integers in the range of 0 to 127 (inclusive). Note names are character
    strings expressed in the format NoteOctave such as 'C4' or 'G#7'. Note
    names range from 'C-1' (note value 0) to 'F#9' (note value 127). If the
    input value is outside that range, the value of `None` is returned.

    :param int note: The note value input in the range of 0 to 127 (inclusive).
    No default value.
    """
    if 0 <= note <= 127:
        return NOTE_BASE[note % 12] + str((note // 12) - 1)
    return None  # Note value outside valid range


def name_to_note(name):
    """Translates a note name to a MIDI sequential note value. Note names are
    character strings expressed in Scienfic Pitch Notation (NoteOctave) format
    such as 'C4' or 'G#7' with middle C defined as 'C4'. Note names range from
    'C-1' (note value 0) to 'G9' (note value 127). Note values are of integer
    type in the range of 0 to 127 (inclusive). If the input value is outside
    that range, the value of `None` is returned.

    :param str name: The note name input in SPN format. No default value.
    """
    name = name.upper()  # Convert lower to uppercase
    if "-" in name:
        octave = int(name[-2:])
        name = name[:-2]
    else:
        octave = int(name[-1:])
        name = name[:-1]

    if name in NOTE_BASE:
        # Note name is valid
        note = NOTE_BASE.index(name)
        midi_note = note + (12 * (octave + 1))  # MIDI note value
        if 0 <= midi_note <= 127:
            return midi_note
    return None  # Name is invalid or outside MIDI value range