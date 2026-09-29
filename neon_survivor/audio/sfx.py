"""Sound-effect factory.

Each effect is a small pure function producing a normalised float buffer.
Effects are described declaratively in :data:`SFX_RECIPES` so the audio
manager can build them lazily and only once.
"""

from __future__ import annotations

from typing import Callable, Dict, List

from neon_survivor.audio import synth
from neon_survivor.config import AUDIO_SAMPLE_RATE

SR = AUDIO_SAMPLE_RATE

#: A recipe is ``name -> (builder, volume)``.
SFX_RECIPES: Dict[str, tuple] = {}


def recipe(name: str, volume: float = 1.0):
    """Decorator registering a sound-effect builder under *name*."""

    def wrapper(func: Callable[[], List[float]]):
        SFX_RECIPES[name] = (func, volume)
        return func

    return wrapper


def arpeggio(
    notes,
    wave: str = "triangle",
    note_len: float = 0.12,
    gap: float = 0.055,
    amplitude: float = 0.5,
    duty: float = 0.5,
) -> List[float]:
    """Lay a list of notes back to back into a single buffer."""
    length = note_len * SR
    total = int(gap * SR * (len(notes) - 1) + length) + 1
    out = [0.0] * total
    for i, note in enumerate(notes):
        tone = synth.render_tone(
            synth.note_to_freq(note),
            note_len,
            wave,
            amplitude,
            SR,
            duty=duty,
            envelope=synth.adsr(int(length), 0.005, 0.04, 0.55, note_len * 0.45),
        )
        synth.overlay(out, tone, int(i * gap * SR))
    return out


# --------------------------------------------------------------------------
# Player
# --------------------------------------------------------------------------
@recipe("shoot", 0.55)
def _shoot() -> List[float]:
    tone = synth.render_sweep(880, 220, 0.09, "square", 0.55, SR, decay=16.0)
    body = synth.render_tone(180, 0.07, "triangle", 0.4, SR, decay=18.0)
    out = synth.mix(tone, body)
    return synth.fade_edges(synth.normalize(out, 0.7), 24)


@recipe("shoot_heavy", 0.6)
def _shoot_heavy() -> List[float]:
    tone = synth.render_sweep(420, 120, 0.16, "saw", 0.6, SR, decay=9.0)
    body = synth.render_noise(0.10, 0.28, SR, decay=20.0, seed=3)
    out = synth.soft_clip(synth.mix(tone, body), 1.4)
    return synth.fade_edges(synth.normalize(out, 0.8), 32)


@recipe("hit", 0.5)
def _hit() -> List[float]:
    noise = synth.render_noise(0.09, 0.6, SR, decay=26.0, seed=11)
    tone = synth.render_sweep(1200, 500, 0.07, "square", 0.35, SR, decay=22.0)
    return synth.fade_edges(synth.normalize(synth.mix(noise, tone), 0.65), 24)


@recipe("enemy_die", 0.6)
def _enemy_die() -> List[float]:
    noise = synth.render_noise(0.26, 0.5, SR, decay=11.0, seed=5)
    sweep = synth.render_sweep(520, 90, 0.24, "saw", 0.5, SR, decay=8.0)
    out = synth.soft_clip(synth.mix(noise, sweep), 1.5)
    return synth.fade_edges(synth.normalize(out, 0.8), 40)


@recipe("enemy_die_big", 0.75)
def _enemy_die_big() -> List[float]:
    noise = synth.render_noise(0.7, 0.55, SR, decay=5.0, seed=9)
    sweep = synth.render_sweep(300, 45, 0.65, "saw", 0.6, SR, decay=4.0)
    sub = synth.render_tone(70, 0.5, "sine", 0.5, SR, decay=5.0)
    out = synth.soft_clip(synth.mix(noise, sweep, sub), 1.8)
    return synth.fade_edges(synth.normalize(out, 0.9), 80)


@recipe("player_hurt", 0.8)
def _player_hurt() -> List[float]:
    sweep = synth.render_sweep(320, 70, 0.34, "square", 0.6, SR, decay=7.0)
    noise = synth.render_noise(0.2, 0.35, SR, decay=12.0, seed=17)
    out = synth.soft_clip(synth.mix(sweep, noise), 1.6)
    return synth.fade_edges(synth.normalize(out, 0.85), 48)


@recipe("dash", 0.4)
def _dash() -> List[float]:
    noise = synth.render_noise(0.22, 0.35, SR, decay=9.0, seed=23)
    return synth.fade_edges(synth.normalize(noise, 0.45), 48)


@recipe("shield", 0.6)
def _shield() -> List[float]:
    a = synth.render_tone(440, 0.30, "sine", 0.4, SR, glide=2.0, decay=5.0)
    b = synth.render_tone(660, 0.30, "sine", 0.3, SR, glide=2.0, decay=6.0)
    return synth.fade_edges(synth.normalize(synth.mix(a, b), 0.6), 48)


# --------------------------------------------------------------------------
# Pickups
# --------------------------------------------------------------------------
@recipe("pickup", 0.55)
def _pickup() -> List[float]:
    return synth.fade_edges(
        synth.normalize(arpeggio(("E5", "B5"), "triangle", 0.12, 0.055, 0.5), 0.65), 40
    )
@recipe("pickup_health", 0.6)
def _pickup_health() -> List[float]:
    return synth.fade_edges(
        synth.normalize(arpeggio(("C5", "E5", "G5"), "sine", 0.16, 0.05, 0.45), 0.7), 40
    )
@recipe("pickup_power", 0.6)
def _pickup_power() -> List[float]:
    parts: List[float] = []
    for i in range(4):
        tone = synth.render_sweep(
            400 * (1.26 ** i), 500 * (1.26 ** i), 0.09, "square", 0.4, SR, decay=10.0
        )
        if not parts:
            parts = [0.0] * (int(i * 0.045 * SR) + len(tone))
        synth.overlay(parts, tone, int(i * 0.045 * SR))
    return synth.fade_edges(synth.normalize(parts, 0.7), 32)
@recipe("pickup_nuke", 0.85)
def _pickup_nuke() -> List[float]:
    rise = synth.render_sweep(120, 1400, 0.45, "saw", 0.55, SR, decay=1.2)
    boom = synth.render_noise(0.9, 0.6, SR, decay=4.0, seed=31)
    sub = synth.render_tone(48, 0.8, "sine", 0.6, SR, decay=4.0)
    out = synth.soft_clip(synth.mix(rise, boom, sub), 1.7)
    return synth.fade_edges(synth.normalize(out, 0.95), 80)


@recipe("nuke_wave", 0.8)
def _nuke_wave() -> List[float]:
    noise = synth.render_noise(0.8, 0.5, SR, decay=3.5, seed=41)
    sweep = synth.render_sweep(900, 60, 0.75, "square", 0.5, SR, decay=3.0)
    out = synth.soft_clip(synth.mix(noise, sweep), 1.6)
    return synth.fade_edges(synth.normalize(out, 0.9), 80)


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------
@recipe("ui_move", 0.4)
def _ui_move() -> List[float]:
    tone = synth.render_tone(660, 0.05, "square", 0.35, SR, decay=18.0)
    return synth.fade_edges(synth.normalize(tone, 0.4), 16)


@recipe("ui_select", 0.55)
def _ui_select() -> List[float]:
    return synth.fade_edges(
        synth.normalize(arpeggio(("G5", "C6"), "square", 0.14, 0.06, 0.4), 0.6), 32
    )
@recipe("ui_back", 0.45)
def _ui_back() -> List[float]:
    tone = synth.render_sweep(520, 300, 0.10, "square", 0.4, SR, decay=12.0)
    return synth.fade_edges(synth.normalize(tone, 0.5), 24)


# --------------------------------------------------------------------------
# Progression
# --------------------------------------------------------------------------
@recipe("wave_start", 0.8)
def _wave_start() -> List[float]:
    return synth.fade_edges(
        synth.normalize(arpeggio(("C4", "G4", "C5", "E5"), "pulse", 0.22, 0.09, 0.42, 0.25), 0.75), 48
    )
@recipe("boss_spawn", 0.9)
def _boss_spawn() -> List[float]:
    low = synth.render_tone(55, 1.3, "saw", 0.6, SR, glide=0.6, decay=2.0)
    sweep = synth.render_sweep(90, 420, 1.1, "square", 0.45, SR, decay=1.6)
    noise = synth.render_noise(1.2, 0.3, SR, decay=2.5, seed=53)
    out = synth.soft_clip(synth.mix(low, sweep, noise), 1.6)
    return synth.fade_edges(synth.normalize(out, 0.92), 120)


@recipe("game_over", 0.9)
def _game_over() -> List[float]:
    return synth.fade_edges(
        synth.normalize(arpeggio(("A4", "F4", "D4", "A3"), "saw", 0.5, 0.19, 0.45), 0.85), 80
    )
@recipe("record", 0.85)
def _record() -> List[float]:
    return synth.fade_edges(
        synth.normalize(
            arpeggio(("C5", "E5", "G5", "C6", "G5", "C6"), "pulse", 0.16, 0.085, 0.4, 0.3), 0.75
        ), 48
    )
# --------------------------------------------------------------------------
def available_sounds() -> List[str]:
    return sorted(SFX_RECIPES.keys())


__all__ = ["SFX_RECIPES", "available_sounds", "recipe", "arpeggio", "SR"]
