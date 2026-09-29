"""Collision helpers: circles, arena bounds and pillar resolution.

All functions operate on plain tuples so they can be tested without pygame.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from neon_survivor.core.mathutils import clamp, distance_sq

Rect = Tuple[float, float, float, float]


# --------------------------------------------------------------------------
# Circle / circle
# --------------------------------------------------------------------------
def circles_overlap(
    ax: float, ay: float, ar: float, bx: float, by: float, br: float
) -> bool:
    """True when two circles intersect."""
    radii = ar + br
    return distance_sq(ax, ay, bx, by) <= radii * radii


def resolve_circle_collision(
    pos: List[float], radius: float, other_x: float, other_y: float, other_r: float
) -> bool:
    """Push ``pos`` (a mutable ``[x, y]``) out of another circle.

    Returns ``True`` when an overlap was resolved.  The lighter circle is
    expected to be the movable one, which is the case in this game.
    """
    dx = pos[0] - other_x
    dy = pos[1] - other_y
    min_dist = radius + other_r
    dist_sq = dx * dx + dy * dy
    if dist_sq >= min_dist * min_dist:
        return False
    if dist_sq <= 1e-9:
        # Perfectly stacked: move to a deterministic offset first so the
        # separation has a well-defined direction *and* start distance.
        dx, dy = 1.0, 0.0
        dist = 1.0
        pos[0] += dx
        pos[1] += dy
    else:
        dist = dist_sq ** 0.5
    overlap = min_dist - dist
    pos[0] += (dx / dist) * overlap
    pos[1] += (dy / dist) * overlap
    return True


# --------------------------------------------------------------------------
# Arena bounds
# --------------------------------------------------------------------------
def clamp_to_bounds(
    pos: List[float], radius: float, min_x: float, min_y: float, max_x: float, max_y: float
) -> bool:
    """Keep a circle of *radius* inside the given rectangle.

    Returns ``True`` if the position had to be corrected.
    """
    original_x, original_y = pos[0], pos[1]
    pos[0] = clamp(pos[0], min_x + radius, max_x - radius)
    pos[1] = clamp(pos[1], min_y + radius, max_y - radius)
    return pos[0] != original_x or pos[1] != original_y


# --------------------------------------------------------------------------
# Pillars (static circles)
# --------------------------------------------------------------------------
def resolve_pillars(
    pos: List[float],
    radius: float,
    pillars: Sequence[Tuple[float, float, float]],
    bounce: float = 0.0,
) -> Optional[Tuple[float, float]]:
    """Push a circle out of every overlapping pillar.

    When *bounce* > 0 the inward normal is returned (scaled by *bounce*) so
    the caller can reflect a velocity.  The returned tuple is ``(nx, ny)``
    of the *last* resolved pillar, which is enough for simple bounces.
    """
    normal: Optional[Tuple[float, float]] = None
    for px, py, pr in pillars:
        dx = pos[0] - px
        dy = pos[1] - py
        min_dist = radius + pr
        dist_sq = dx * dx + dy * dy
        if dist_sq >= min_dist * min_dist:
            continue
        if dist_sq <= 1e-9:
            # Coincident centres: start from a deterministic unit offset.
            dx, dy = 1.0, 0.0
            dist = 1.0
            pos[0] += dx
            pos[1] += dy
        else:
            dist = dist_sq ** 0.5
        overlap = min_dist - dist
        nx = dx / dist
        ny = dy / dist
        pos[0] += nx * overlap
        pos[1] += ny * overlap
        normal = (nx * bounce, ny * bounce)
    return normal


def line_blocked_by_pillars(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    pillars: Sequence[Tuple[float, float, float]],
) -> bool:
    """Crude segment-vs-pillar test used for line-of-sight checks."""
    from neon_survivor.core.mathutils import segment_intersects_circle

    for px, py, pr in pillars:
        if segment_intersects_circle(x1, y1, x2, y2, px, py, pr):
            return True
    return False


# --------------------------------------------------------------------------
# Spatial hash — used to avoid O(n^2) enemy separation
# --------------------------------------------------------------------------
class SpatialHash:
    """Uniform grid bucketing of circular entities.

    ``insert``/``query`` operate on ``(x, y, radius)`` tuples.  The grid is
    rebuilt every frame which keeps the implementation simple and fast enough
    for the few hundred entities this game handles.
    """

    __slots__ = ("cell_size", "_cells")

    def __init__(self, cell_size: float = 128.0) -> None:
        self.cell_size = max(1.0, cell_size)
        self._cells: dict = {}

    def clear(self) -> None:
        self._cells.clear()

    def _range(self, x: float, y: float, radius: float):
        cs = self.cell_size
        min_cx = int((x - radius) // cs)
        max_cx = int((x + radius) // cs)
        min_cy = int((y - radius) // cs)
        max_cy = int((y + radius) // cs)
        return min_cx, max_cx, min_cy, max_cy

    def insert(self, x: float, y: float, radius: float, payload) -> None:
        min_cx, max_cx, min_cy, max_cy = self._range(x, y, radius)
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                self._cells.setdefault((cx, cy), []).append(payload)

    def query(self, x: float, y: float, radius: float) -> List:
        results: List = []
        min_cx, max_cx, min_cy, max_cy = self._range(x, y, radius)
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                bucket = self._cells.get((cx, cy))
                if bucket:
                    results.extend(bucket)
        return results


__all__ = [
    "SpatialHash",
    "circles_overlap",
    "resolve_circle_collision",
    "clamp_to_bounds",
    "resolve_pillars",
    "line_blocked_by_pillars",
]
