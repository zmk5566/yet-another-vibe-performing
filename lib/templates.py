"""
HANMAI-LIVE Instrument Templates

所有可用的 instrument template 注册表
"""

TEMPLATES = {
    # ===== Drum 类 =====
    "kick": {
        "type": "drum",
        "dsp": "dsp/instruments/kick.dsp",
        "pattern": "X...X...X...X...",
    },
    "snare": {
        "type": "drum",
        "dsp": "dsp/instruments/snare.dsp",
        "pattern": "....X.......X...",
    },
    "hihat": {
        "type": "drum",
        "dsp": "dsp/instruments/hihat.dsp",
        "pattern": "X.X.X.X.X.X.X.X.",
    },
    "clap": {
        "type": "drum",
        "dsp": "dsp/instruments/clap.dsp",
        "pattern": "....X.......X...",
    },
    "tom": {
        "type": "drum",
        "dsp": "dsp/instruments/tom.dsp",
        "pattern": "..........X.X...",
    },

    # ===== Synth 类 =====
    "bass": {
        "type": "synth",
        "dsp": "dsp/instruments/bass.dsp",
        "notes": [36, None, None, 36, None, None, 39, None,
                  36, None, None, 36, None, None, 41, None],
    },
    "lead": {
        "type": "synth",
        "dsp": "dsp/instruments/lead.dsp",
        "notes": [60, None, 64, None, 67, None, 64, None,
                  60, None, 67, None, 72, None, None, None],
    },
    "pad": {
        "type": "synth",
        "dsp": "dsp/instruments/pad.dsp",
        "notes": [60, None, None, None, None, None, None, None,
                  64, None, None, None, None, None, None, None],
    },
}


def midi_to_freq(midi_note):
    """MIDI note number → 频率 (Hz)"""
    return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))


def midi_to_name(midi_note):
    """MIDI note number → 音符名 (如 C4, A#3)"""
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    return f"{notes[midi_note % 12]}{(midi_note // 12) - 1}"
