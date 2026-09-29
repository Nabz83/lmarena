"""Low-level synthesis primitives (pure Python, no numpy).

The renderer is wave-table based: a single cycle of each waveform is
generated once and then read with a fractional index, which keeps music
generation fast enough to run on the main thread at start-up.

Buffers are plain ``list`` of floats in ``[-1, 1]``.
"""

from __future__ import annotations

import math
import random
from array import array
from typing import List, Optional, Sequence

#: Names of the available wave shapes.
WAVES = ("sine", "square", "pulse", "saw", "triangle", "noise")

#: Default resolution of a wave-table cycle.
TABLE_SIZE = 2048


# --------------------------------------------------------------------------
# Wave tables
# --------------------------------------------------------------------------
def _build_table(wave: str, duty: float = 0.5) -> List[float]:
    """One cycle of *wave*, normalised to roughly ``[-1, 1]``."""
    table: List[float] = []
    for i in range(TABLE_SIZE):
        phase = i / TABLE_SIZE
        if wave == "sine":
            value = math.sin(phase * math.tau)
        elif wave == "square":
            value = 1.0 if phase < 0.5 else -1.0
        elif wave == "pulse":
            value = 1.0 if phase < duty else -1.0
        elif wave == "saw":
            value = 2.0 * phase - 1.0
        elif wave == "triangle":
            value = 4.0 * abs(phase - 0.5) - 1.0
        elif wave == "noise":
            # Deterministic LCG so a given seed always sounds the same.
            seed = (i * 1103515245 + 12345) & 0x7FFFFFFF
            value = (seed / 0x3FFFFFFF) - 1.0
        else:
            value = math.sin(phase * math.tau)
        table.append(value)
    return table


_TABLE_CACHE: dict = {}


def wave_table(wave: str, duty: float = 0.5) -> List[float]:
    key = (wave, round(duty, 3))
    table = _TABLE_CACHE.get(key)
    if table is None:
        table = _build_table(wave, duty)
        _TABLE_CACHE[key] = table
    return table


# --------------------------------------------------------------------------
# Note helpers
# --------------------------------------------------------------------------
_A4 = 440.0
#: Semitone offset of each natural note (C = 0).
_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def note_to_freq(name: str | int | float) -> float:
    """Convert a note name (``'A4'``, ``'C#3'``), MIDI number or Hz to Hz."""
    if isinstance(name, (int, float)) and not isinstance(name, bool):
        value = float(name)
        if value <= 0:
            return 0.0
        # Bare numbers are treated as MIDI notes.
        return _A4 * (2.0 ** ((value - 69) / 12.0))
    if not name:
        return 0.0
    text = str(name).strip()
    if text and text[0].upper() in _SEMITONES:
        letter = text[0].upper()
        rest = text[1:]
        semitone = _SEMITONES[letter]
        for accidental in rest:
            if accidental in "#♯":
                semitone += 1
            elif accidental in "b♭":
                semitone -= 1
        digits = "".join(c for c in rest if c.isdigit())
        octave = int(digits) if digits else 4
        midi = (octave + 1) * 12 + semitone
        return _A4 * (2.0 ** ((midi - 69) / 12.0))
    try:
        return float(text)
    except ValueError:
        return 0.0


def midi_to_freq(midi: float) -> float:
    return _A4 * (2.0 ** ((midi - 69) / 12.0))


# --------------------------------------------------------------------------
# Envelopes
# --------------------------------------------------------------------------
def adsr(
    length: int,
    attack: float,
    decay: float,
    sustain: float,
    release: float,
) -> List[float]:
    """Build an ADSR envelope of *length* samples (all times in seconds)."""
    envelope = [0.0] * length
    a = max(0, int(attack * length))
    d = max(0, int(decay * length))
    r = max(0, int(release * length))
    s = max(0, length - a - d - r)
    index = 0
    for i in range(a):
        envelope[index] = (i / a) if a else 1.0
        index += 1
    for i in range(d):
        start = 1.0
        envelope[index] = start + (sustain - start) * (i / d if d else 1.0)
        index += 1
    for _ in range(s):
        envelope[index] = sustain
        index += 1
    for i in range(r):
        envelope[index] = sustain * (1.0 - (i / r if r else 1.0))
        index += 1
    while index < length:
        envelope[index] = 0.0
        index += 1
    return envelope


def exp_decay(length: int, rate: float) -> List[float]:
    """A simple exponential decay, ``rate`` per second."""
    return [math.exp(-rate * (i / length)) for i in range(length)]


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def render_tone(
    freq: float,
    duration: float,
    wave: str = "sine",
    amplitude: float = 0.6,
    sample_rate: int = 22050,
    duty: float = 0.5,
    envelope: Optional[Sequence[float]] = None,
    detune: float = 0.0,
    vibrato_hz: float = 0.0,
    vibrato_depth: float = 0.0,
    phase_offset: float = 0.0,
    glide: float = 1.0,
    decay: float = 0.0,
) -> List[float]:
    """Render a single oscillator with an optional pitch envelope.

    ``glide`` is a frequency ratio applied across the note (``0.5`` = an
    octave down).  ``decay`` is an exponential decay rate over the whole
    duration; ``0`` means a constant amplitude.
    """
    length = max(1, int(duration * sample_rate))
    table = wave_table(wave, duty)
    size = TABLE_SIZE
    if envelope is not None:
        env = list(envelope)
        if len(env) < length:
            env = env + [0.0] * (length - len(env))
    elif decay > 0.0:
        env = exp_decay(length, decay)
    else:
        env = [1.0] * length

    out = [0.0] * length
    if wave == "noise":
        rng = random.Random(int(freq) & 0xFFFF)
        for i in range(length):
            out[i] = (rng.random() * 2.0 - 1.0) * env[i] * amplitude
        return out

    phase = phase_offset
    vphase = 0.0
    for i in range(length):
        f = freq * (glide ** (i / length))
        if vibrato_depth > 0.0 and vibrato_hz > 0.0:
            f *= 1.0 + vibrato_depth * math.sin(vphase)
            vphase += math.tau * vibrato_hz / sample_rate
        phase += f / sample_rate
        phase2 = phase * (1.0 + detune)
        out[i] = (
            table[int((phase * size)) % size] * 0.5
            + table[int((phase2 * size)) % size] * 0.5
        ) * env[i] * amplitude
    return out


def render_noise(
    duration: float,
    amplitude: float = 0.5,
    sample_rate: int = 22050,
    decay: float = 12.0,
    seed: int = 0,
) -> List[float]:
    """Filtered white noise with an exponential decay."""
    length = max(1, int(duration * sample_rate))
    rng = random.Random(seed)
    out = [0.0] * length
    # One-pole low-pass keeps it from sounding like pure hiss.
    last = 0.0
    for i in range(length):
        white = rng.random() * 2.0 - 1.0
        last = last * 0.35 + white * 0.65
        out[i] = last * amplitude * math.exp(-decay * (i / length))
    return out


def render_sweep(
    f_start: float,
    f_end: float,
    duration: float,
    wave: str = "square",
    amplitude: float = 0.6,
    sample_rate: int = 22050,
    duty: float = 0.5,
    decay: float = 6.0,
) -> List[float]:
    """A tone whose frequency glides from *f_start* to *f_end*."""
    length = max(1, int(duration * sample_rate))
    table = wave_table(wave, duty)
    out = [0.0] * length
    phase = 0.0
    for i in range(length):
        t = i / length
        f = f_start * ((f_end / f_start) ** t) if f_start > 0 and f_end > 0 else f_start
        phase += f / sample_rate
        out[i] = table[int(phase * TABLE_SIZE) % TABLE_SIZE] * amplitude * math.exp(-decay * t)
    return out


# --------------------------------------------------------------------------
# Buffer maths
# --------------------------------------------------------------------------
def mix(*buffers: Sequence[float]) -> List[float]:
    """Sum buffers, zero-padding to the longest one."""
    if not buffers:
        return []
    length = max(len(b) for b in buffers)
    out = [0.0] * length
    for buf in buffers:
        for i, value in enumerate(buf):
            out[i] += value
    return out


def overlay(base: List[float], other: Sequence[float], offset: int, gain: float = 1.0) -> None:
    """Add *other* into *base* at sample *offset*, in place."""
    n = len(base)
    for i, value in enumerate(other):
        j = offset + i
        if 0 <= j < n:
            base[j] += value * gain


def normalize(buffer: Sequence[float], peak: float = 0.92) -> List[float]:
    """Scale so the loudest sample reaches *peak*."""
    highest = 0.0
    for value in buffer:
        av = value if value >= 0 else -value
        if av > highest:
            highest = av
    if highest <= 1e-9:
        return list(buffer)
    factor = peak / highest
    return [v * factor for v in buffer]


def soft_clip(buffer: Sequence[float], drive: float = 1.0) -> List[float]:
    """Gentle saturation — adds harmonics without harsh digital clipping.

    Uses the standard rational approximation of ``tanh``.
    """
    if drive <= 0:
        return list(buffer)
    out: List[float] = []
    for value in buffer:
        v = value * drive
        if v >= 3.0:
            out.append(1.0)
        elif v <= -3.0:
            out.append(-1.0)
        else:
            v2 = v * v
            out.append(v * (27.0 + v2) / (27.0 + 9.0 * v2))
    return out


def fade_edges(buffer: List[float], samples: int = 32) -> List[float]:
    """Fade the head and tail to avoid clicks."""
    length = len(buffer)
    samples = max(1, min(samples, length // 2))
    for i in range(samples):
        t = i / samples
        buffer[i] *= t
        buffer[length - 1 - i] *= t
    return buffer


def to_pcm16(buffer: Sequence[float]) -> bytes:
    """Pack floats into little-endian signed 16-bit PCM."""
    out = array("h", bytes(2 * len(buffer)))
    for i, value in enumerate(buffer):
        v = int(max(-1.0, min(1.0, value)) * 32767)
        out[i] = v
    return out.tobytes()


def to_stereo(buffer: Sequence[float]) -> bytes:
    """Duplicate a mono buffer into interleaved stereo 16-bit PCM."""
    out = array("h", bytes(4 * len(buffer)))
    for i, value in enumerate(buffer):
        v = int(max(-1.0, min(1.0, value)) * 32767)
        out[i * 2] = v
        out[i * 2 + 1] = v
    return out.tobytes()


def duration_of(buffer: Sequence[float], sample_rate: int) -> float:
    return len(buffer) / float(sample_rate)


__all__ = [
    "WAVES",
    "TABLE_SIZE",
    "wave_table",
    "note_to_freq",
    "midi_to_freq",
    "adsr",
    "exp_decay",
    "render_tone",
    "render_noise",
    "render_sweep",
    "mix",
    "overlay",
    "normalize",
    "soft_clip",
    "fade_edges",
    "to_pcm16",
    "to_stereo",
    "duration_of",
]
