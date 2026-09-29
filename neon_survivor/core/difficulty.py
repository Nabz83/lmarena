"""Difficulty curve and wave scheduling.

The whole progression is described by :class:`DifficultyCurve` which is a
pure, deterministic object: given the elapsed time it tells how many enemies
must be alive, how strong they are and which archetypes are unlocked.  This
is what makes the game fair and what the unit tests exercise.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from neon_survivor.config import BOSS_EVERY, WAVE_DURATION

#: Enemy archetype unlock wave (1-based).
UNLOCK_WAVES: Dict[str, int] = {
    "grunt": 1,
    "runner": 2,
    "shooter": 4,
    "tank": 5,
    "charger": 7,
    "splitter": 9,
    "weaver": 11,
    "boss": BOSS_EVERY,
}

#: Spawn weight of each archetype per wave-band.  Bands are exclusive and are
#: picked in order: the first band whose lower bound is <= wave wins.
WEIGHT_BANDS: Sequence[Tuple[int, Dict[str, float]]] = (
    (1, {"grunt": 1.0}),
    (2, {"grunt": 0.75, "runner": 0.25}),
    (4, {"grunt": 0.55, "runner": 0.30, "shooter": 0.15}),
    (5, {"grunt": 0.45, "runner": 0.28, "shooter": 0.15, "tank": 0.12}),
    (7, {"grunt": 0.38, "runner": 0.27, "shooter": 0.17, "tank": 0.10, "charger": 0.08}),
    (
        9,
        {
            "grunt": 0.30,
            "runner": 0.24,
            "shooter": 0.18,
            "tank": 0.10,
            "charger": 0.09,
            "splitter": 0.09,
        },
    ),
    (
        11,
        {
            "grunt": 0.24,
            "runner": 0.22,
            "shooter": 0.18,
            "tank": 0.11,
            "charger": 0.10,
            "splitter": 0.08,
            "weaver": 0.07,
        },
    ),
)


@dataclass
class WaveState:
    """Snapshot of the difficulty at a given moment of the run."""

    wave: int
    elapsed: float
    wave_elapsed: float
    wave_progress: float
    time_to_next_wave: float
    spawn_interval: float
    max_alive: int
    burst_size: int
    hp_multiplier: float
    speed_multiplier: float
    damage_multiplier: float
    score_multiplier: float
    is_boss_wave: bool
    boss_count: int
    composition: Dict[str, float] = field(default_factory=dict)

    @property
    def is_elite(self) -> bool:
        """Late waves spawn a fraction of tougher "elite" variants."""
        return self.wave >= 6


class DifficultyCurve:
    """Turns elapsed time into concrete spawn parameters."""

    def __init__(
        self,
        wave_duration: float = WAVE_DURATION,
        base_interval: float = 0.95,
        base_max_alive: int = 12,
        max_alive_cap: int = 64,
        max_interval_floor: float = 0.16,
    ) -> None:
        self.wave_duration = max(1.0, wave_duration)
        self.base_interval = base_interval
        self.base_max_alive = base_max_alive
        self.max_alive_cap = max_alive_cap
        self.max_interval_floor = max_interval_floor

    # -- basics ----------------------------------------------------------
    def wave_for_time(self, elapsed: float) -> int:
        return int(max(0.0, elapsed) // self.wave_duration) + 1

    def wave_bounds(self, elapsed: float) -> Tuple[int, float]:
        """Return ``(wave_index_0based, progress_0_1)`` for *elapsed*."""
        safe = max(0.0, elapsed)
        index = int(safe // self.wave_duration)
        progress = (safe - index * self.wave_duration) / self.wave_duration
        return index, min(1.0, max(0.0, progress))

    def is_boss_wave(self, wave: int) -> bool:
        return wave % BOSS_EVERY == 0

    # -- scaling ---------------------------------------------------------
    def hp_multiplier(self, wave: int) -> float:
        w = max(1, wave)
        # Gentle start, then a steady ramp.
        return 1.0 + 0.22 * (w - 1) + 0.015 * (w - 1) ** 2

    def speed_multiplier(self, wave: int) -> float:
        w = max(1, wave)
        return 1.0 + 0.035 * (w - 1)

    def damage_multiplier(self, wave: int) -> float:
        w = max(1, wave)
        return 1.0 + 0.08 * (w - 1)

    def score_multiplier(self, wave: int) -> float:
        w = max(1, wave)
        return 1.0 + 0.12 * (w - 1)

    def spawn_interval(self, wave: int) -> float:
        w = max(1, wave)
        value = self.base_interval * math.pow(0.935, w - 1)
        return max(self.max_interval_floor, value)

    def max_alive(self, wave: int) -> int:
        w = max(1, wave)
        return int(min(self.max_alive_cap, self.base_max_alive + 2.1 * (w - 1)))

    def burst_size(self, wave: int) -> int:
        w = max(1, wave)
        if w < 3:
            return 1
        if w < 7:
            return 2
        if w < 12:
            return 3
        return 4 if w < 20 else 5

    # -- composition -----------------------------------------------------
    def composition(self, wave: int) -> Dict[str, float]:
        weights: Dict[str, float] = {}
        for min_wave, band in WEIGHT_BANDS:
            if wave >= min_wave:
                weights = band
        # Respect the unlock table so no archetype appears before its wave.
        return {
            name: weight
            for name, weight in weights.items()
            if wave >= UNLOCK_WAVES.get(name, 1)
        }

    def available_types(self, wave: int) -> List[str]:
        """Archetypes unlocked at *wave*, boss excluded."""
        return [name for name, unlock in sorted(UNLOCK_WAVES.items()) if name != "boss" and wave >= unlock]

    def boss_count(self, wave: int) -> int:
        if not self.is_boss_wave(wave):
            return 0
        return 1 + (wave // (BOSS_EVERY * 3))

    # -- aggregate -------------------------------------------------------
    def state_for_time(self, elapsed: float) -> WaveState:
        index, progress = self.wave_bounds(elapsed)
        wave = index + 1
        remaining = self.wave_duration * (1.0 - progress)
        return WaveState(
            wave=wave,
            elapsed=max(0.0, elapsed),
            wave_elapsed=progress * self.wave_duration,
            wave_progress=progress,
            time_to_next_wave=remaining,
            spawn_interval=self.spawn_interval(wave),
            max_alive=self.max_alive(wave),
            burst_size=self.burst_size(wave),
            hp_multiplier=self.hp_multiplier(wave),
            speed_multiplier=self.speed_multiplier(wave),
            damage_multiplier=self.damage_multiplier(wave),
            score_multiplier=self.score_multiplier(wave),
            is_boss_wave=self.is_boss_wave(wave),
            boss_count=self.boss_count(wave),
            composition=self.composition(wave),
        )


def weighted_pick(
    weights: Dict[str, float], roll: float
) -> str | None:
    """Pick a key from *weights* given a random number in ``[0, 1)``."""
    total = sum(weights.values())
    if total <= 0.0:
        return None
    threshold = roll * total
    cumulative = 0.0
    for name, weight in weights.items():
        cumulative += weight
        if threshold < cumulative:
            return name
    # Numerical safety net.
    for name in weights:
        return name
    return None


__all__ = [
    "UNLOCK_WAVES",
    "WEIGHT_BANDS",
    "WaveState",
    "DifficultyCurve",
    "weighted_pick",
]
