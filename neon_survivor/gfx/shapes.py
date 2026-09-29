"""Polygon generators for the entities.

Pure geometry (no pygame) so the shapes can be unit tested: every generator
returns a list of ``(x, y)`` points in *local* space, where the entity
"faces" along +X (angle 0).  The renderer rotates them as needed.
"""

from __future__ import annotations

import math
from typing import List, Sequence, Tuple

Point = Tuple[float, float]


def regular_polygon(sides: int, radius: float, rotation: float = 0.0) -> List[Point]:
    """A regular polygon centred on the origin."""
    if sides < 3:
        sides = 3
    step = math.tau / sides
    return [
        (
            math.cos(rotation + i * step) * radius,
            math.sin(rotation + i * step) * radius,
        )
        for i in range(sides)
    ]


def star(points: int, outer: float, inner: float, rotation: float = 0.0) -> List[Point]:
    """A classic star polygon."""
    points = max(3, points)
    result: List[Point] = []
    step = math.pi / points
    for i in range(points * 2):
        radius = outer if i % 2 == 0 else inner
        angle = rotation + i * step
        result.append((math.cos(angle) * radius, math.sin(angle) * radius))
    return result


def rounded_polygon(
    points: Sequence[Point], radius_ratio: float = 0.28
) -> List[Point]:
    """Replace the sharp corners of *points* by quadratic fillets."""
    count = len(points)
    if count < 3:
        return list(points)
    result: List[Point] = []
    ratio = max(0.0, min(0.49, radius_ratio))
    for i in range(count):
        prev = points[(i - 1) % count]
        cur = points[i]
        nxt = points[(i + 1) % count]
        v1 = (prev[0] - cur[0], prev[1] - cur[1])
        v2 = (nxt[0] - cur[0], nxt[1] - cur[1])
        l1 = math.hypot(*v1) or 1.0
        l2 = math.hypot(*v2) or 1.0
        cut = min(ratio, 0.45)
        p1 = (cur[0] + v1[0] / l1 * l1 * cut, cur[1] + v1[1] / l1 * l1 * cut)
        p2 = (cur[0] + v2[0] / l2 * l2 * cut, cur[1] + v2[1] / l2 * l2 * cut)
        # Quadratic Bezier between p1 and p2, through the corner.
        for step in range(4):
            t = step / 3.0
            inv = 1.0 - t
            result.append(
                (
                    inv * inv * p1[0] + 2 * inv * t * cur[0] + t * t * p2[0],
                    inv * inv * p1[1] + 2 * inv * t * cur[1] + t * t * p2[1],
                )
            )
    return result


def triangle(radius: float, rotation: float = 0.0) -> List[Point]:
    """An arrow head pointing along +X."""
    return [
        (radius, 0.0),
        (-radius * 0.75, -radius * 0.78),
        (-radius * 0.42, 0.0),
        (-radius * 0.75, radius * 0.78),
    ]


def diamond(radius: float, stretch: float = 1.0) -> List[Point]:
    return [
        (radius, 0.0),
        (0.0, radius * stretch * 0.72),
        (-radius, 0.0),
        (0.0, -radius * stretch * 0.72),
    ]


def hexagon(radius: float, rotation: float = 0.0) -> List[Point]:
    return regular_polygon(6, radius, rotation)


def octagon(radius: float, rotation: float = math.pi / 8) -> List[Point]:
    return regular_polygon(8, radius, rotation)


def lobed_circle(radius: float, lobes: int = 3, depth: float = 0.18) -> List[Point]:
    """A circle whose radius ripples — used by the splitter."""
    steps = max(24, lobes * 10)
    points: List[Point] = []
    for i in range(steps):
        angle = math.tau * i / steps
        r = radius * (1.0 + depth * math.cos(angle * lobes))
        points.append((math.cos(angle) * r, math.sin(angle) * r))
    return points


def ellipse(radius: float, aspect: float, steps: int = 28) -> List[Point]:
    points: List[Point] = []
    for i in range(steps):
        angle = math.tau * i / steps
        points.append((math.cos(angle) * radius, math.sin(angle) * radius * aspect))
    return points


def boss_shape(radius: float) -> List[Point]:
    """A wide, angular hull for the boss."""
    return [
        (radius, 0.0),
        (radius * 0.62, radius * 0.60),
        (0.0, radius * 0.86),
        (-radius * 0.58, radius * 0.72),
        (-radius * 0.92, 0.0),
        (-radius * 0.58, -radius * 0.72),
        (0.0, -radius * 0.86),
        (radius * 0.62, -radius * 0.60),
    ]


def player_shape(radius: float) -> List[Point]:
    """The player hull: a sleek forward-pointing craft."""
    return [
        (radius * 1.18, 0.0),
        (radius * 0.28, radius * 0.74),
        (-radius * 0.55, radius * 0.60),
        (-radius * 0.86, 0.0),
        (-radius * 0.55, -radius * 0.60),
        (radius * 0.28, -radius * 0.74),
    ]


#: Per-archetype body outline, in local space facing +X.
ENEMY_SHAPES = {
    "grunt": lambda r: rounded_polygon(regular_polygon(4, r * 0.98, math.pi / 4), 0.30),
    "runner": lambda r: triangle(r * 1.20),
    "shooter": lambda r: rounded_polygon(hexagon(r * 1.02), 0.26),
    "tank": lambda r: rounded_polygon(octagon(r * 0.98), 0.22),
    "charger": lambda r: [
        (r * 1.35, 0.0),
        (r * 0.30, r * 0.70),
        (-r * 0.85, r * 0.52),
        (-r * 0.55, 0.0),
        (-r * 0.85, -r * 0.52),
        (r * 0.30, -r * 0.70),
    ],
    "splitter": lambda r: lobed_circle(r * 1.02, lobes=3, depth=0.16),
    "weaver": lambda r: diamond(r * 1.15, stretch=1.25),
    "boss": boss_shape,
}


def normalize_to_radius(points: Sequence[Point], radius: float) -> List[Point]:
    """Scale a polygon so its furthest vertex sits exactly at *radius*.

    Rounded corners shrink the silhouette, which would otherwise make the
    drawn body noticeably smaller than the (circular) hitbox.
    """
    if not points or radius <= 0:
        return list(points)
    longest = max(math.hypot(x, y) for x, y in points)
    if longest <= 1e-6:
        return list(points)
    factor = radius / longest
    return [(x * factor, y * factor) for x, y in points]


def enemy_shape(kind: str, radius: float) -> List[Point]:
    """Body outline of *kind*, scaled to *radius*."""
    factory = ENEMY_SHAPES.get(kind)
    if factory is None:
        factory = ENEMY_SHAPES["grunt"]
    return normalize_to_radius(factory(radius), radius)


def rotate_points(points: Sequence[Point], angle: float) -> List[Point]:
    """Rotate *points* around the origin."""
    if not points:
        return []
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return [(x * cos_a - y * sin_a, x * sin_a + y * cos_a) for x, y in points]


def scale_points(points: Sequence[Point], factor: float) -> List[Point]:
    return [(x * factor, y * factor) for x, y in points]


def translate_points(points: Sequence[Point], dx: float, dy: float) -> List[Point]:
    return [(x + dx, y + dy) for x, y in points]


def bounds(points: Sequence[Point]) -> Tuple[float, float, float, float]:
    """``(min_x, min_y, max_x, max_y)`` of a point cloud."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def point_in_polygon(x: float, y: float, points: Sequence[Point]) -> bool:
    """Ray-casting point-in-polygon test."""
    inside = False
    count = len(points)
    j = count - 1
    for i in range(count):
        xi, yi = points[i]
        xj, yj = points[j]
        if (yi > y) != (yj > y):
            if x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
        j = i
    return inside


__all__ = [
    "Point",
    "regular_polygon",
    "star",
    "rounded_polygon",
    "triangle",
    "diamond",
    "hexagon",
    "octagon",
    "lobed_circle",
    "ellipse",
    "boss_shape",
    "player_shape",
    "ENEMY_SHAPES",
    "enemy_shape",
    "normalize_to_radius",
    "rotate_points",
    "scale_points",
    "translate_points",
    "bounds",
    "point_in_polygon",
]
