from mido import MidiFile

# --- Explicit mapping between keys and MIDI notes ---

key_to_midi = {
    # number row
    '1':36, '!':37, '2':38, '@':39, '3':40, '4':41, '$':42, '5':43, '%':44,
    '6':45, '^':46, '7':47, '8':48, '*':49, '9':50, '(':51, '0':52, 

    # qwertyuiop
    'q':53, 'Q':54, 'w':55, 'W':56, 'e':57, 'E':58, 'r':59, 't':60, 'T':61,
    'y':62, 'Y':63, 'u':64, 'i':65, 'I':66, 'o':67, 'O':68, 'p':69, 'P':70,

    # asdfghjkl
    'a':71, 's':72, 'S':73, 'd':74, 'D':75, 'f':76, 'g':77, 'G':78,
    'h':79, 'H':80, 'j':81, 'J':82, 'k':83, 'l':84, 'L':85,

    # zxcvbnm
    'z':86, 'Z':87, 'x':88, 'c':89, 'C':90, 'v':91, 'V':92,
    'b':93, 'B':94, 'n':95, 'm':96, 'M':97
}

# reverse map for output
midi_to_key = {v: k for k, v in key_to_midi.items()}


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
                    #output.append("?")

        if j < len(events):
            gap = events[j][0] - events[i][0]
            if gap > 1:
                output.append("_")

        i = j

    # Break into lines
    lines = []
    for k in range(0, len(output), line_length):
        lines.append(" ".join(output[k:k+line_length]))

    # Join and strip out all "?" placeholders
    text_out = "\n".join(lines).replace("?", "")

    with open(output_path, "w") as f:
        f.write(text_out)

    print(f"Written to {output_path}")


# Example usage
if __name__ == "__main__":
    midi_to_text("input.mid", "output.txt", line_length=16)
