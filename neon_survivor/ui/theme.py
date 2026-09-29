"""Colour palette, typography helpers and shared UI metrics.

The game uses a single "synthwave" palette so every screen stays coherent.
"""

from __future__ import annotations

from typing import Tuple

RGB = Tuple[int, int, int]
RGBA = Tuple[int, int, int, int]


class Palette:
    # -- background ------------------------------------------------------
    VOID = (6, 8, 20)
    NIGHT = (10, 12, 30)
    PANEL = (16, 20, 44)
    PANEL_LIGHT = (24, 30, 62)
    GRID = (26, 34, 70)
    WALL = (58, 32, 104)
    WALL_EDGE = (150, 92, 255)

    # -- text ------------------------------------------------------------
    TEXT = (232, 240, 255)
    TEXT_DIM = (146, 158, 196)
    TEXT_FAINT = (92, 102, 138)

    # -- accents ---------------------------------------------------------
    CYAN = (86, 226, 255)
    MAGENTA = (255, 74, 166)
    PURPLE = (150, 110, 255)
    LIME = (110, 245, 150)
    AMBER = (255, 206, 84)
    RED = (255, 84, 96)
    GOLD = (255, 232, 128)

    # -- gameplay --------------------------------------------------------
    PLAYER = (120, 245, 255)
    PLAYER_CORE = (255, 255, 255)
    PLAYER_DAMAGE = (255, 110, 120)
    BULLET = (170, 245, 255)
    HOSTILE_BULLET = (255, 108, 150)
    HP_HIGH = (110, 245, 150)
    HP_LOW = (255, 96, 110)

    # -- misc ------------------------------------------------------------
    ACCENT = CYAN
    ACCENT_2 = MAGENTA
    SHADOW = (0, 0, 0)


class Metrics:
    """Spacing / sizing tokens used across the UI."""

    PAD_SM = 8
    PAD = 16
    PAD_LG = 28
    RADIUS = 10
    RADIUS_LG = 18
    BORDER = 2
    HUD_HEIGHT = 96
    BANNER_TIME = 2.6


#: Gradient stops used by titles and bars.
GRADIENT_ACCENT: Tuple[RGB, ...] = (
    Palette.CYAN,
    Palette.PURPLE,
    Palette.MAGENTA,
)

GRADIENT_HP: Tuple[RGB, ...] = (Palette.HP_LOW, Palette.AMBER, Palette.HP_HIGH)


def lerp_color(a: RGB, b: RGB, t: float) -> RGB:
    t = max(0.0, min(1.0, t))
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def sample_gradient(stops, t: float) -> RGB:
    """Sample a multi-stop gradient at position ``t`` in ``[0, 1]``."""
    if not stops:
        return (255, 255, 255)
    t = max(0.0, min(1.0, t))
    if len(stops) == 1:
        return stops[0]
    scaled = t * (len(stops) - 1)
    index = int(scaled)
    if index >= len(stops) - 1:
        return stops[-1]
    return lerp_color(stops[index], stops[index + 1], scaled - index)


def with_alpha(color: RGB, alpha: float) -> RGBA:
    a = int(max(0.0, min(1.0, alpha)) * 255)
    return (color[0], color[1], color[2], a)


def mix(color: RGB, other: RGB, t: float) -> RGB:
    return lerp_color(color, other, t)


def health_color(ratio: float) -> RGB:
    """Red when low, green when healthy."""
    if ratio <= 0.5:
        return lerp_color(Palette.HP_LOW, Palette.AMBER, ratio / 0.5)
    return lerp_color(Palette.AMBER, Palette.HP_HIGH, (ratio - 0.5) / 0.5)


__all__ = [
    "Palette",
    "Metrics",
    "GRADIENT_ACCENT",
    "GRADIENT_HP",
    "lerp_color",
    "sample_gradient",
    "with_alpha",
    "mix",
    "health_color",
]
