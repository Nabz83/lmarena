"""Scoring: points, combo multiplier and per-run statistics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from neon_survivor.config import (
    SCORE_COMBO_MAX,
    SCORE_COMBO_STEP,
    SCORE_COMBO_WINDOW,
    SCORE_PER_WAVE,
    SCORE_SURVIVAL_PER_SECOND,
)
from neon_survivor.core.mathutils import clamp


@dataclass
class ScoreBoard:
    """Tracks the score of a single run."""

    score: int = 0
    kills: int = 0
    combo: int = 0
    combo_timer: float = 0.0
    best_combo: int = 0
    damage_taken: float = 0.0
    shots_fired: int = 0
    shots_hit: int = 0
    pickups: int = 0
    wave: int = 1
    elapsed: float = 0.0
    per_kind: Dict[str, int] = field(default_factory=dict)

    # -- combo -----------------------------------------------------------
    @property
    def combo_multiplier(self) -> float:
        return 1.0 + min(SCORE_COMBO_MAX - 1.0, self.combo * SCORE_COMBO_STEP)

    @property
    def combo_ratio(self) -> float:
        """0..1 progress of the combo timer, for the HUD bar."""
        if SCORE_COMBO_WINDOW <= 0:
            return 0.0
        return clamp(self.combo_timer / SCORE_COMBO_WINDOW, 0.0, 1.0)

    def bump_combo(self) -> None:
        self.combo += 1
        self.combo_timer = SCORE_COMBO_WINDOW
        self.best_combo = max(self.best_combo, self.combo)

    def break_combo(self) -> None:
        self.combo = 0
        self.combo_timer = 0.0

    # -- scoring ---------------------------------------------------------
    def add(self, base: int, multiplier: float = 1.0) -> int:
        """Add points and return the amount actually credited."""
        amount = int(round(base * multiplier))
        self.score += amount
        return amount

    def register_kill(self, kind: str, base_score: int, wave_multiplier: float = 1.0) -> int:
        self.kills += 1
        self.per_kind[kind] = self.per_kind.get(kind, 0) + 1
        # The multiplier of the *current* streak is applied, so the first
        # kill of a streak is worth its base value and the bonus builds up.
        amount = self.add(int(base_score), wave_multiplier * self.combo_multiplier)
        self.bump_combo()
        return amount

    def register_hit(self) -> None:
        self.shots_hit += 1

    def register_shot(self) -> None:
        self.shots_fired += 1

    def register_damage(self, amount: float) -> None:
        self.damage_taken += amount

    def register_pickup(self) -> None:
        self.pickups += 1

    def register_wave(self, wave: int) -> int:
        self.wave = wave
        return self.add(SCORE_PER_WAVE, 1.0 + 0.08 * (wave - 1))

    # -- per-frame -------------------------------------------------------
    def update(self, dt: float) -> None:
        self.elapsed += dt
        if self.combo_timer > 0.0:
            self.combo_timer = max(0.0, self.combo_timer - dt)
            if self.combo_timer <= 0.0:
                self.combo = 0

    def survival_points(self) -> int:
        return int(self.elapsed * SCORE_SURVIVAL_PER_SECOND)

    def accuracy(self) -> float:
        if self.shots_fired <= 0:
            return 0.0
        return clamp(self.shots_hit / self.shots_fired, 0.0, 1.0)

    @property
    def formatted_time(self) -> str:
        minutes = int(self.elapsed) // 60
        seconds = int(self.elapsed) % 60
        return f"{minutes:02d}:{seconds:02d}"


__all__ = ["ScoreBoard"]
