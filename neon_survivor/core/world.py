"""The arena: walls, decorative floor and static pillars."""

from __future__ import annotations

import math
import random
from typing import List, Sequence, Tuple

from neon_survivor.config import (
    FLOOR_GRID_SIZE,
    PILLAR_BORDER_MARGIN,
    PILLAR_COUNT,
    PILLAR_MAX_RADIUS,
    PILLAR_MIN_RADIUS,
    WALL_THICKNESS,
    WORLD_HEIGHT,
    WORLD_WIDTH,
)

Pillar = Tuple[float, float, float]  # x, y, radius


def _overlaps(candidate: Pillar, placed: Sequence[Pillar], gap: float) -> bool:
    for px, py, pr in placed:
        d = math.hypot(candidate[0] - px, candidate[1] - py)
        if d < candidate[2] + pr + gap:
            return True
    return False


def generate_pillars(
    count: int = PILLAR_COUNT,
    width: float = WORLD_WIDTH,
    height: float = WORLD_HEIGHT,
    margin: float = PILLAR_BORDER_MARGIN,
    seed: int | None = 1337,
) -> List[Pillar]:
    """Place *count* non-overlapping pillars with a deterministic layout."""
    rng = random.Random(seed)
    placed: List[Pillar] = []
    lo_x, hi_x = margin, width - margin
    lo_y, hi_y = margin, height - margin
    if hi_x <= lo_x or hi_y <= lo_y:
        return placed

    attempts = 0
    max_attempts = count * 80
    while len(placed) < count and attempts < max_attempts:
        attempts += 1
        radius = rng.uniform(PILLAR_MIN_RADIUS, PILLAR_MAX_RADIUS)
        candidate = (rng.uniform(lo_x, hi_x), rng.uniform(lo_y, hi_y), radius)
        if not _overlaps(candidate, placed, gap=170.0):
            placed.append(candidate)
    return placed


def pillar_at(
    pillars: Sequence[Pillar], x: float, y: float, extra: float = 0.0
) -> Pillar | None:
    """Return the first pillar overlapping the point, if any."""
    for pillar in pillars:
        px, py, pr = pillar
        if math.hypot(x - px, y - py) <= pr + extra:
            return pillar
    return None


def find_free_position(
    rng: random.Random,
    pillars: Sequence[Pillar],
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    radius: float,
    tries: int = 24,
) -> Tuple[float, float]:
    """Sample a point inside the arena that is not inside a pillar."""
    for _ in range(tries):
        x = rng.uniform(min_x, max_x)
        y = rng.uniform(min_y, max_y)
        if pillar_at(pillars, x, y, radius) is None:
            return (x, y)
    # Fallback: the arena center is reserved and always free.
    return ((min_x + max_x) * 0.5, (min_y + max_y) * 0.5)


class Arena:
    """Container describing the playable area."""

    #: Size of the broad-phase cells used by :meth:`nearby_pillars`.
    PILLAR_CELL = 256.0

    def __init__(
        self,
        width: float = WORLD_WIDTH,
        height: float = WORLD_HEIGHT,
        wall: float = WALL_THICKNESS,
        pillar_count: int = PILLAR_COUNT,
        seed: int | None = 1337,
    ) -> None:
        self.width = width
        self.height = height
        self.wall = wall
        self.pillars: List[Pillar] = generate_pillars(
            count=pillar_count, width=width, height=height, seed=seed
        )
        #: Pillar display variant (0/1) for visual variety.
        self.pillar_variants: List[int] = [
            (i * 7 + 3) % 3 for i in range(len(self.pillars))
        ]
        self.grid_size = FLOOR_GRID_SIZE
        self._pillar_cells = self._build_pillar_grid()

    # -- pillar broad-phase ---------------------------------------------
    def _build_pillar_grid(self) -> dict:
        """Bucket the static pillars so collision tests stay O(1)-ish.

        Pillars never move, so the grid is built once; without it every
        entity tested against all 44 pillars every frame, which dominated
        the update cost.
        """
        cell = self.PILLAR_CELL
        cells: dict = {}
        for px, py, pr in self.pillars:
            min_cx = int((px - pr) // cell)
            max_cx = int((px + pr) // cell)
            min_cy = int((py - pr) // cell)
            max_cy = int((py + pr) // cell)
            for cx in range(min_cx, max_cx + 1):
                for cy in range(min_cy, max_cy + 1):
                    cells.setdefault((cx, cy), []).append((px, py, pr))
        return {key: tuple(value) for key, value in cells.items()}

    def nearby_pillars(
        self, x: float, y: float, radius: float = 0.0
    ) -> Sequence[Pillar]:
        """Pillars that could overlap a circle at ``(x, y)`` with *radius*."""
        cell = self.PILLAR_CELL
        min_cx = int((x - radius) // cell)
        max_cx = int((x + radius) // cell)
        min_cy = int((y - radius) // cell)
        max_cy = int((y + radius) // cell)
        if min_cx == max_cx and min_cy == max_cy:
            # Common case: a single cell, returned without allocating.
            return self._pillar_cells.get((min_cx, min_cy), ())
        found: List[Pillar] = []
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                found.extend(self._pillar_cells.get((cx, cy), ()))
        return found

    # -- bounds ----------------------------------------------------------
    @property
    def inner_bounds(self) -> Tuple[float, float, float, float]:
        w = self.wall
        return (w, w, self.width - w * 2.0, self.height - w * 2.0)

    def contains(self, x: float, y: float, radius: float = 0.0) -> bool:
        return (
            self.wall + radius <= x <= self.width - self.wall - radius
            and self.wall + radius <= y <= self.height - self.wall - radius
        )

    def clamp_position(self, pos: List[float], radius: float) -> None:
        w = self.wall + radius
        pos[0] = min(max(pos[0], w), self.width - w)
        pos[1] = min(max(pos[1], w), self.height - w)

    @property
    def center(self) -> Tuple[float, float]:
        return (self.width * 0.5, self.height * 0.5)

    def is_near_wall(self, x: float, y: float, margin: float) -> bool:
        return (
            x < self.wall + margin
            or y < self.wall + margin
            or x > self.width - self.wall - margin
            or y > self.height - self.wall - margin
        )


__all__ = ["Arena", "Pillar", "generate_pillars", "pillar_at", "find_free_position"]
