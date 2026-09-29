"""Small, dependency-free 2D math helpers.

Kept free of pygame so the tests can exercise them on a headless machine.
"""

from __future__ import annotations

import math
import random
from typing import Iterable, Sequence, Tuple

Vec2 = Tuple[float, float]

_TAU = math.tau


def clamp(value: float, low: float, high: float) -> float:
    """Clamp *value* into ``[low, high]``."""
    if value < low:
        return low
    if value > high:
        return high
    return value


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between *a* and *b*."""
    return a + (b - a) * t


def inverse_lerp(a: float, b: float, value: float) -> float:
    """Return where *value* sits between *a* and *b*, as a 0..1 ratio."""
    if a == b:
        return 0.0
    return (value - a) / (b - a)


def approach(current: float, target: float, max_delta: float) -> float:
    """Move *current* toward *target* by at most *max_delta*."""
    if current < target:
        return min(current + max_delta, target)
    if current > target:
        return max(current - max_delta, target)
    return target


def damp(current: float, target: float, smoothing: float, dt: float) -> float:
    """Frame-rate independent exponential smoothing."""
    if smoothing <= 0.0:
        return target
    return lerp(target, current, math.exp(-smoothing * dt))


def length_sq(x: float, y: float) -> float:
    return x * x + y * y


def length(x: float, y: float) -> float:
    return math.hypot(x, y)


def normalize(x: float, y: float) -> Vec2:
    """Return a unit vector; ``(0, 0)`` maps to ``(0, 0)``."""
    mag = math.hypot(x, y)
    if mag <= 1e-9:
        return (0.0, 0.0)
    return (x / mag, y / mag)


def from_angle(angle: float, magnitude: float = 1.0) -> Vec2:
    return (math.cos(angle) * magnitude, math.sin(angle) * magnitude)


def angle_between(x1: float, y1: float, x2: float, y2: float) -> float:
    """Angle (radians) pointing from point 1 towards point 2."""
    return math.atan2(y2 - y1, x2 - x1)


def angle_difference(a: float, b: float) -> float:
    """Smallest signed delta from angle *a* to angle *b*, in ``[-pi, pi]``."""
    return (b - a + math.pi) % _TAU - math.pi


def rotate_towards(current: float, target: float, max_step: float) -> float:
    """Rotate *current* towards *target* by at most *max_step* radians."""
    diff = angle_difference(current, target)
    if abs(diff) <= max_step:
        return target
    return current + math.copysign(max_step, diff)


def distance(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(bx - ax, by - ay)


def distance_sq(ax: float, ay: float, bx: float, by: float) -> float:
    dx = bx - ax
    dy = by - ay
    return dx * dx + dy * dy


def limit_length(x: float, y: float, maximum: float) -> Vec2:
    """Shorten ``(x, y)`` so that its magnitude does not exceed *maximum*."""
    mag_sq = x * x + y * y
    if mag_sq <= maximum * maximum or mag_sq <= 1e-12:
        return (x, y)
    scale = maximum / math.sqrt(mag_sq)
    return (x * scale, y * scale)


def random_unit_vector(rng: random.Random | None = None) -> Vec2:
    rng = rng or random
    return from_angle(rng.uniform(0.0, _TAU))


def point_in_rect(px: float, py: float, rect: Sequence[float]) -> bool:
    x, y, w, h = rect
    return x <= px <= x + w and y <= py <= y + h


def circle_intersects_rect(
    cx: float, cy: float, radius: float, rect: Sequence[float]
) -> bool:
    """True when a circle overlaps an axis-aligned rect."""
    x, y, w, h = rect
    closest_x = clamp(cx, x, x + w)
    closest_y = clamp(cy, y, y + h)
    return distance_sq(cx, cy, closest_x, closest_y) <= radius * radius


def segment_intersects_circle(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    cx: float,
    cy: float,
    radius: float,
) -> bool:
    """True when segment ``(x1,y1)-(x2,y2)`` hits the circle."""
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 1e-12:
        return distance_sq(x1, y1, cx, cy) <= radius * radius
    t = clamp(((cx - x1) * dx + (cy - y1) * dy) / seg_len_sq, 0.0, 1.0)
    px = x1 + dx * t
    py = y1 + dy * t
    return distance_sq(px, py, cx, cy) <= radius * radius


def sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def average(values: Iterable[float]) -> float:
    total = 0.0
    count = 0
    for value in values:
        total += value
        count += 1
    return total / count if count else 0.0


__all__ = [
    "Vec2",
    "clamp",
    "lerp",
    "inverse_lerp",
    "approach",
    "damp",
    "length",
    "length_sq",
    "normalize",
    "from_angle",
    "angle_between",
    "angle_difference",
    "rotate_towards",
    "distance",
    "distance_sq",
    "limit_length",
    "random_unit_vector",
    "point_in_rect",
    "circle_intersects_rect",
    "segment_intersects_circle",
    "sign",
    "average",
]
