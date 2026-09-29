"""Spawn director: decides where and when enemies enter the arena.

The director guarantees two properties that make the game fair:

* enemies never appear inside the player's visible area (or too close to
  them) — ``spawn_points`` rejects any candidate closer than
  ``min_player_distance``;
* enemies never spawn inside a wall or a pillar.
"""

from __future__ import annotations

import math
import random
from typing import List, Sequence, Tuple

from neon_survivor.core.difficulty import DifficultyCurve, WaveState, weighted_pick
from neon_survivor.core.world import Pillar, pillar_at


class SpawnDirector:
    """Accumulates spawn time and emits spawn requests."""

    def __init__(
        self,
        curve: DifficultyCurve | None = None,
        seed: int | None = None,
        margin: float = 90.0,
        min_player_distance: float = 420.0,
    ) -> None:
        self.curve = curve or DifficultyCurve()
        self.rng = random.Random(seed)
        self.margin = margin
        self.min_player_distance = min_player_distance
        self._accumulator = 0.0
        self._burst_remaining = 0
        self._burst_timer = 0.0
        self.spawned_total = 0
        self.spawned_by_kind: dict = {}

    def reset(self) -> None:
        self._accumulator = 0.0
        self._burst_remaining = 0
        self._burst_timer = 0.0
        self.spawned_total = 0
        self.spawned_by_kind = {}

    # -- budget ----------------------------------------------------------
    def pending_spawns(self, state: WaveState, alive: int, dt: float) -> int:
        """Return how many enemies should be spawned this frame."""
        if alive >= state.max_alive:
            return 0

        self._accumulator += dt
        interval = max(0.01, state.spawn_interval)
        spawns = 0
        # Never emit an unbounded burst when a frame hitches.
        while self._accumulator >= interval and spawns < 8:
            self._accumulator -= interval
            spawns += 1

        # Occasional burst: several enemies at once, on top of the trickle.
        if self._burst_remaining > 0:
            self._burst_timer -= dt
            if self._burst_timer <= 0.0:
                spawns += 1
                self._burst_remaining -= 1
                self._burst_timer = 0.14
        elif self.rng.random() < 0.006:
            self._burst_remaining = max(0, state.burst_size - 1)
            self._burst_timer = 0.0

        spawns = min(spawns, state.max_alive - alive)
        self.spawned_total += spawns
        return spawns

    def record_spawn(self, kind: str) -> None:
        """Record which archetype was actually instantiated."""
        self.spawned_by_kind[kind] = self.spawned_by_kind.get(kind, 0) + 1

    # -- archetype -------------------------------------------------------
    def pick_type(self, state: WaveState) -> str | None:
        return weighted_pick(state.composition, self.rng.random())

    def pick_elite(self, state: WaveState) -> bool:
        if not state.is_elite:
            return False
        chance = min(0.30, 0.02 * (state.wave - 5))
        return self.rng.random() < chance

    # -- positions -------------------------------------------------------
    def spawn_point(
        self,
        player_x: float,
        player_y: float,
        half_w: float,
        half_h: float,
        arena_w: float,
        arena_h: float,
        wall: float,
        pillars: Sequence[Pillar],
        radius: float = 24.0,
        tries: int = 30,
    ) -> Tuple[float, float]:
        """Pick a valid spawn position on the ring around the player.

        The ring radius is the diagonal of the viewport (so the enemy is
        off-screen in both axes) and it grows until a valid point is found.
        """
        diagonal = math.hypot(half_w, half_h)
        min_r = max(self.min_player_distance, diagonal)
        max_r = min_r + self.margin + 420.0

        for attempt in range(tries):
            # Bias the first attempts towards the closest valid ring.
            t = attempt / max(1, tries - 1)
            radius_ring = min_r + (max_r - min_r) * (t ** 1.6)
            angle = self.rng.uniform(0.0, math.tau)
            x = player_x + math.cos(angle) * radius_ring
            y = player_y + math.sin(angle) * radius_ring

            if not (wall + radius <= x <= arena_w - wall - radius):
                continue
            if not (wall + radius <= y <= arena_h - wall - radius):
                continue
            if math.hypot(x - player_x, y - player_y) < self.min_player_distance:
                continue
            if pillar_at(pillars, x, y, radius) is not None:
                continue
            return (x, y)

        # Guaranteed fallback: the farthest arena corner from the player.
        corners = [
            (wall + radius, wall + radius),
            (arena_w - wall - radius, wall + radius),
            (wall + radius, arena_h - wall - radius),
            (arena_w - wall - radius, arena_h - wall - radius),
        ]
        return max(corners, key=lambda c: math.hypot(c[0] - player_x, c[1] - player_y))

    def spawn_points(
        self,
        count: int,
        player_x: float,
        player_y: float,
        half_w: float,
        half_h: float,
        arena_w: float,
        arena_h: float,
        wall: float,
        pillars: Sequence[Pillar],
        radius: float = 24.0,
    ) -> List[Tuple[float, float]]:
        points: List[Tuple[float, float]] = []
        for _ in range(count):
            points.append(
                self.spawn_point(
                    player_x, player_y, half_w, half_h, arena_w, arena_h, wall, pillars, radius
                )
            )
        return points


__all__ = ["SpawnDirector"]
