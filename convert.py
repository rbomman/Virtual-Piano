from mido import MidiFile

# --- Explicit mapping between keys and MIDI notes ---
key_to_midi = {
    # number row
    '1': 36, '!': 37, '2': 38, '@': 39, '3': 40, '4': 41, '$': 42,
    '5': 43, '%': 44, '6': 45, '^': 46, '7': 47, '8': 48, '*': 49,
    '9': 50, '(': 51, '0': 52, 

    # qwertyuiop
    'q': 53, 'Q': 54, 'w': 55, 'W': 56, 'e': 57, 'E': 58, 'r': 59, 
    't': 60, 'T': 61, 'y': 62, 'Y': 63, 'u': 64, 'i': 65, 'I': 66,
    'o': 67, 'O': 68, 'p': 69, 'P': 70,

    # asdfghjkl
    'a': 71, 's': 72, 'S': 73, 'd': 74, 'D': 75, 'f': 76,
    'g': 77, 'G': 78, 'h': 79, 'H': 80, 'j': 81, 'J': 82, 'k': 83, 
    'l': 84, 'L': 85,

    # zxcvbnm
    'z': 86, 'Z': 87, 'x': 88, 'c': 89, 'C': 90, 'v': 91, 'V': 92,
    'b': 93, 'B': 94, 'n': 95, 'm': 96, 'M': 97
}

# Build reverse map favouring the last declared key for each MIDI note
midi_to_key = {v: k for k, v in key_to_midi.items()}

DEFAULT_DURATION_BEATS = 0.5
REST_THRESHOLD = 1e-3
DEFAULT_TIME_SIGNATURE = "4/4"


def _format_duration(value: float) -> str:
    """Format beat durations with up to three decimal places."""
    formatted = f"{value:.3f}".rstrip('0').rstrip('.')
    return formatted or "0"


def midi_to_text(
    midi_path,
    output_path,
    chord_threshold=0,
    seq_threshold=0.1,
    line_length=16,
    time_signature: str = DEFAULT_TIME_SIGNATURE,
):
    """Convert a MIDI file to the keyboard text format including durations.

    Each token is emitted as SYMBOL|durations;wait where durations are measured in
    beats. For chords the shortest member duration is used; for sequences each
    element keeps its own duration; the wait value encodes the total beats until
    the next token (covering any silence without needing explicit rest tokens).
    """
    mid = MidiFile(midi_path)
    ticks_per_beat = mid.ticks_per_beat or 480

    # Collect note events with their start time (in beats) and duration (in beats)
    events = []  # (start_beat, midi_note, duration_beats)
    for track in mid.tracks:
        abs_time = 0
        active_notes = {}
        for msg in track:
            abs_time += msg.time
            if msg.type == 'note_on' and msg.velocity > 0:
                active_notes.setdefault(msg.note, []).append(abs_time)
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                starts = active_notes.get(msg.note)
                if starts:
                    start_tick = starts.pop()
                    start_beat = start_tick / ticks_per_beat
                    duration_beats = max((abs_time - start_tick) / ticks_per_beat, 1e-4)
                    events.append((start_beat, msg.note, duration_beats))

    events.sort(key=lambda x: (x[0], x[1]))

    # Trim note lengths so overlapping entries are cut short by the next onset
    if events:
        unique_starts = sorted({start for start, _, _ in events})
        next_start_for = {}
        for idx, start in enumerate(unique_starts):
            next_start_for[start] = unique_starts[idx + 1] if idx + 1 < len(unique_starts) else None
        trimmed = []
        for start, midi_note, duration in events:
            next_start = next_start_for.get(start)
            trimmed_duration = duration
            if next_start is not None and next_start > start:
                overlap = next_start - start
                if overlap < trimmed_duration:
                    trimmed_duration = max(overlap, 1e-4)
            trimmed.append((start, midi_note, trimmed_duration))
        events = trimmed

    tokens = []
    i = 0
    while i < len(events):
        start, midi_note, duration = events[i]
        group = [(midi_note, duration, start)]
        j = i + 1

        # Detect simultaneous notes (chords)
        while j < len(events) and abs(events[j][0] - start) <= chord_threshold:
            group.append((events[j][1], events[j][2], events[j][0]))
            j += 1

        token = None
        hold_span = duration

        if len(group) > 1:
            sorted_group = sorted(group, key=lambda item: item[0])
            keys = [midi_to_key.get(note_value) for note_value, _, _ in sorted_group]
            keys = [key for key in keys if key]
            if keys:
                chord_duration = min(item[1] for item in group)
                token = {
                    'text': f"[{''.join(keys)}]",
                    'durations': [chord_duration],
                    'type': 'chord',
                    'start': start,
                }
                hold_span = chord_duration
        else:
            seq = [(midi_note, duration, start)]
            k = i + 1
            while (
                k < len(events)
                and 0 < events[k][0] - seq[-1][2] <= seq_threshold
            ):
                seq.append((events[k][1], events[k][2], events[k][0]))
                k += 1

            if len(seq) > 1:
                keys = [midi_to_key.get(note_value) for note_value, _, _ in seq]
                keys = [key for key in keys if key]
                if keys:
                    durations = [item[1] for item in seq]
                    last_start = seq[-1][2]
                    last_duration = seq[-1][1]
                    hold_span = (last_start + last_duration) - start
                    token = {
                        'text': f"{{{''.join(keys)}}}",
                        'durations': durations,
                        'type': 'sequence',
                        'start': start,
                    }
                    j = k
            else:
                key = midi_to_key.get(midi_note)
                if key:
                    token = {
                        'text': key,
                        'durations': [duration],
                        'type': 'single',
                        'start': start,
                    }
                    hold_span = duration

        if token:
            next_start = events[j][0] if j < len(events) else None
            if next_start is not None:
                wait = max(next_start - start, hold_span)
            else:
                wait = hold_span
            token['wait'] = wait
            tokens.append(token)

        i = j

    if not tokens:
        with open(output_path, 'w', encoding='utf-8') as handle:
            header = f"# meter={time_signature}"
            handle.write(header + '\n')
        print(f"Written to {output_path}")
        return

    def token_to_string(token):
        duration_str = ','.join(_format_duration(d) for d in token['durations'])
        wait_str = _format_duration(token.get('wait', sum(token['durations'])))
        if duration_str:
            payload = f"{duration_str};{wait_str}"
        else:
            payload = wait_str
        return f"{token['text']}|{payload}"

    string_tokens = [token_to_string(t) for t in tokens]

    lines = []
    if line_length > 0:
        for idx in range(0, len(string_tokens), line_length):
            lines.append(' '.join(string_tokens[idx:idx + line_length]))
    else:
        lines.append(' '.join(string_tokens))

    output_lines = [f"# meter={time_signature}"]
    output_lines.extend(lines)
    text_out = '\n'.join(output_lines)

    with open(output_path, 'w', encoding='utf-8') as handle:
        handle.write(text_out)

    print(f"Written to {output_path}")


if __name__ == "__main__":
    midi_to_text("input.mid", "output.txt", line_length=16)
