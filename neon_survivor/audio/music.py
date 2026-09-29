"""Procedural chiptune soundtrack.

A tiny step sequencer builds a seamless loop from a bass line, a pulse
lead and noise percussion.  Three intensity tiers ("calm", "action",
"boss") select different patterns and tempo so the music reacts to the
game state without ever cross-fading two loops.

Everything is generated at runtime, so there is no audio file to license.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

from neon_survivor.audio import synth
from neon_survivor.config import AUDIO_SAMPLE_RATE

SR = AUDIO_SAMPLE_RATE


@dataclass(frozen=True)
class TrackSpec:
    """Pattern and tempo for one music tier."""

    key: str
    bpm: float
    bars: int
    steps_per_bar: int
    bass_pattern: Tuple[str, ...]
    lead_pattern: Tuple[Tuple[int, str, float], ...]
    pad_chords: Tuple[Tuple[str, ...], ...]
    drums: bool
    lead_wave: str = "pulse"
    lead_duty: float = 0.25


#: Notes are given as names so the pattern stays readable.
MINOR_PROGRESSION = (
    ("A2", "C3", "E3"),
    ("A2", "C3", "E3"),
    ("F2", "A2", "C3"),
    ("F2", "A2", "C3"),
    ("C3", "E3", "G3"),
    ("C3", "E3", "G3"),
    ("G2", "B2", "D3"),
    ("G2", "B2", "D3"),
)

CALM = TrackSpec(
    key="calm",
    bpm=92.0,
    bars=8,
    steps_per_bar=8,
    bass_pattern=("A2", "-", "A2", "-", "E3", "-", "C3", "-",
                  "F2", "-", "F2", "-", "C3", "-", "A2", "-",
                  "C3", "-", "C3", "-", "G3", "-", "E3", "-",
                  "G2", "-", "G2", "-", "D3", "-", "B2", "-"),
    lead_pattern=(
        (0, "A4", 1.0), (3, "C5", 0.6), (6, "E5", 1.0),
        (8, "F4", 1.0), (11, "A4", 0.6), (14, "C5", 1.0),
        (16, "E5", 1.0), (19, "G5", 0.6), (22, "E5", 1.0),
        (24, "D5", 1.0), (27, "B4", 0.6), (30, "G4", 1.0),
    ),
    pad_chords=MINOR_PROGRESSION,
    drums=False,
    lead_wave="triangle",
)

ACTION = TrackSpec(
    key="action",
    bpm=138.0,
    bars=8,
    steps_per_bar=8,
    bass_pattern=("A1", "A1", "-", "A1", "A1", "-", "E2", "-",
                  "F1", "F1", "-", "F1", "F1", "-", "C2", "-",
                  "C2", "C2", "-", "C2", "C2", "-", "G2", "-",
                  "G1", "G1", "-", "G1", "G1", "-", "D2", "A2"),
    lead_pattern=(
        (0, "A4", 0.5), (2, "C5", 0.5), (4, "E5", 1.0), (6, "A5", 0.5),
        (8, "F4", 0.5), (10, "A4", 0.5), (12, "C5", 1.0), (14, "F5", 0.5),
        (16, "E5", 0.5), (18, "G5", 0.5), (20, "B5", 1.0), (22, "E5", 0.5),
        (24, "D5", 0.5), (26, "F5", 0.5), (28, "A5", 1.0), (30, "D5", 0.5),
    ),
    pad_chords=MINOR_PROGRESSION,
    drums=True,
    lead_wave="pulse",
    lead_duty=0.25,
)

BOSS = TrackSpec(
    key="boss",
    bpm=152.0,
    bars=8,
    steps_per_bar=8,
    bass_pattern=("A1", "A1", "A1", "A1", "-", "A1", "A1", "A1",
                  "F1", "F1", "F1", "F1", "-", "F1", "F1", "F1",
                  "C2", "C2", "C2", "C2", "-", "C2", "C2", "C2",
                  "G1", "G1", "G1", "G1", "-", "G1", "G1", "G1"),
    lead_pattern=(
        (0, "A5", 0.5), (2, "G5", 0.5), (4, "E5", 0.5), (6, "C5", 0.5),
        (8, "F5", 0.5), (10, "E5", 0.5), (12, "C5", 1.0),
        (16, "G5", 0.5), (18, "E5", 0.5), (20, "D5", 0.5), (22, "B4", 0.5),
        (24, "D5", 0.5), (26, "F5", 0.5), (28, "A5", 1.0), (30, "F5", 0.5),
    ),
    pad_chords=MINOR_PROGRESSION,
    drums=True,
    lead_wave="saw",
    lead_duty=0.5,
)

TRACKS: Dict[str, TrackSpec] = {t.key: t for t in (CALM, ACTION, BOSS)}


def _step_duration(spec: TrackSpec) -> float:
    return 60.0 / spec.bpm / 2.0  # eighth notes


def _render_kick(sample_rate: int) -> List[float]:
    length = int(0.14 * sample_rate)
    out = [0.0] * length
    for i in range(length):
        t = i / sample_rate
        freq = 150.0 * math.exp(-t * 26.0) + 45.0
        out[i] = math.sin(t * freq * math.tau) * math.exp(-t * 15.0)
    return out


def _render_snare(sample_rate: int) -> List[float]:
    noise = synth.render_noise(0.12, 0.6, sample_rate, decay=20.0, seed=77)
    body = synth.render_tone(190, 0.10, "triangle", 0.35, sample_rate, decay=22.0)
    return synth.mix(noise, body)


def _render_hat(sample_rate: int) -> List[float]:
    return synth.render_noise(0.05, 0.28, sample_rate, decay=42.0, seed=91)


def render_track(spec: TrackSpec, sample_rate: int = SR) -> List[float]:
    """Render one seamless loop of *spec*."""
    step = _step_duration(spec)
    total_steps = spec.bars * spec.steps_per_bar
    total = int(total_steps * step * sample_rate)
    buffer = [0.0] * total

    step_samples = int(step * sample_rate)

    # --- bass ---------------------------------------------------------
    bass_table = synth.wave_table("square", 0.5)
    for i, note in enumerate(spec.bass_pattern[:total_steps]):
        if note == "-":
            continue
        offset = i * step_samples
        length = int(step * 0.92 * sample_rate)
        freq = synth.note_to_freq(note)
        env = synth.adsr(length, 0.005, 0.04, 0.72, 0.05)
        phase = 0.0
        for j in range(length):
            if offset + j >= total:
                break
            phase += freq / sample_rate
            buffer[offset + j] += bass_table[int(phase * synth.TABLE_SIZE) % synth.TABLE_SIZE] * env[j] * 0.30

    # --- lead ---------------------------------------------------------
    lead_table = synth.wave_table(spec.lead_wave, spec.lead_duty)
    for start, note, length_steps in spec.lead_pattern:
        if start >= total_steps:
            continue
        offset = start * step_samples
        lead_len = int(step * length_steps * 0.95 * sample_rate)
        freq = synth.note_to_freq(note)
        env = synth.adsr(lead_len, 0.006, 0.06, 0.55, min(0.12, step * 0.6))
        phase = 0.0
        for j in range(lead_len):
            if offset + j >= total:
                break
            phase += freq / sample_rate
            buffer[offset + j] += lead_table[int(phase * synth.TABLE_SIZE) % synth.TABLE_SIZE] * env[j] * 0.20

    # --- pad / chords -------------------------------------------------
    pad_table = synth.wave_table("triangle")
    chord_len = spec.steps_per_bar * step
    for bar, chord in enumerate(spec.pad_chords):
        offset = int(bar * chord_len * sample_rate)
        length = int(chord_len * 0.95 * sample_rate)
        if offset >= total:
            break
        env = synth.adsr(length, 0.05, 0.2, 0.5, 0.25)
        for note in chord:
            freq = synth.note_to_freq(note)
            phase = 0.0
            for j in range(length):
                if offset + j >= total:
                    break
                phase += freq / sample_rate
                buffer[offset + j] += pad_table[int(phase * synth.TABLE_SIZE) % synth.TABLE_SIZE] * env[j] * 0.055

    # --- drums --------------------------------------------------------
    if spec.drums:
        kick = _render_kick(sample_rate)
        snare = _render_snare(sample_rate)
        hat = _render_hat(sample_rate)
        for bar in range(spec.bars):
            base = bar * spec.steps_per_bar * step_samples
            for s in range(spec.steps_per_bar):
                idx = base + s * step_samples
                if idx >= total:
                    continue
                if s in (0, 4):
                    synth.overlay(buffer, kick, idx, 0.55)
                if s in (2, 6):
                    synth.overlay(buffer, snare, idx, 0.32)
                if s % 2 == 0:
                    synth.overlay(buffer, hat, idx, 0.16)

    buffer = synth.soft_clip(buffer, 1.1)
    buffer = synth.normalize(buffer, 0.72)
    return _make_seamless(buffer, sample_rate)


def _make_seamless(buffer: List[float], sample_rate: int) -> List[float]:
    """Cross-fade the tail into the head so the loop has no click."""
    fade = min(len(buffer) // 8, int(0.35 * sample_rate))
    if fade <= 1:
        return buffer
    for i in range(fade):
        t = i / fade
        head = buffer[i]
        tail = buffer[len(buffer) - fade + i]
        buffer[i] = head * t + tail * (1.0 - t)
    return buffer[: len(buffer) - fade]


def available_tracks() -> List[str]:
    return sorted(TRACKS.keys())


def track_length(spec: TrackSpec, sample_rate: int = SR) -> float:
    return spec.bars * spec.steps_per_bar * _step_duration(spec)


__all__ = [
    "TrackSpec",
    "TRACKS",
    "CALM",
    "ACTION",
    "BOSS",
    "render_track",
    "available_tracks",
    "track_length",
]
