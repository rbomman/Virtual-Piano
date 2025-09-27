from mido import MidiFile

# Full layout left-to-right as in your image (lowercase for white notes)
layout = list("1234567890qwertyuiopasdfghjklzxcvbnm")

# Shifted symbols for number row
number_shifts = "!@#$%^&*()"

# Anchor: 't' is middle C (C4 = MIDI 60)
anchor_key = 't'
anchor_midi = 60
anchor_index = layout.index(anchor_key)

# Build dictionary
# Build dictionary
midi_to_key = {}
key_to_midi = {}

for i, key in enumerate(layout):
    # Each layout key represents a whole tone (natural + sharp)
    midi_base = anchor_midi + (i - anchor_index) * 2

    # Natural
    midi_to_key[midi_base] = key
    key_to_midi[key] = midi_base

    # Black key
    if key.isdigit():  # number row
        shifted = number_shifts["1234567890".index(key)]
        midi_to_key[midi_base + 1] = shifted
        key_to_midi[shifted] = midi_base + 1
    elif key.isalpha():  # letters
        shifted = key.upper()
        midi_to_key[midi_base + 1] = shifted
        key_to_midi[shifted] = midi_base + 1


def midi_to_text(midi_path, output_path,
                 chord_threshold=0, seq_threshold=0.1, line_length=16):
    """
    Convert MIDI file to custom keyboard text format.
    - Chords -> [ ]
    - Quick successive notes -> { }
    - Pauses -> _
    - Wraps every `line_length` symbols to a new line
    """
    mid = MidiFile(midi_path)
    ticks_per_beat = mid.ticks_per_beat

    events = []  # (time_in_beats, note)
    for track in mid.tracks:
        abs_time = 0
        for msg in track:
            abs_time += msg.time
            if msg.type == 'note_on' and msg.velocity > 0:
                beat_time = abs_time / ticks_per_beat
                events.append((beat_time, msg.note))

    events.sort(key=lambda x: x[0])

    output = []
    i = 0
    while i < len(events):
        t, note = events[i]
        group = [note]

        j = i + 1
        while j < len(events) and abs(events[j][0] - t) <= chord_threshold:
            group.append(events[j][1])
            j += 1

        if len(group) > 1:
            keys = [midi_to_key.get(n, '?') for n in sorted(group)]
            output.append("[" + "".join(keys) + "]")
        else:
            if j < len(events) and 0 < events[j][0] - t <= seq_threshold:
                seq = [note]
                while j < len(events) and events[j][0] - seq[-1] <= seq_threshold:
                    seq.append(events[j][1])
                    j += 1
                keys = [midi_to_key.get(n, '?') for n in seq]
                output.append("{" + "".join(keys) + "}")
            else:
                if note in midi_to_key:
                    output.append(midi_to_key[note])
                else:
                    print(f"Unmapped MIDI note: {note}")
                    output.append("?")


        if j < len(events):
            gap = events[j][0] - events[i][0]
            if gap > 1:
                output.append("_")

        i = j

    # Break into lines
    lines = []
    for k in range(0, len(output), line_length):
        lines.append(" ".join(output[k:k+line_length]))

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Written to {output_path}")


# Example usage
if __name__ == "__main__":
    midi_to_text("input.mid", "output.txt", line_length=16)
