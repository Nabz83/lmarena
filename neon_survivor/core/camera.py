"""Camera with smooth follow, world clamping and trauma-based shake."""

from __future__ import annotations

import math
import random
from typing import Tuple

from neon_survivor.core.mathutils import clamp


class Camera:
    """2D camera with easing, bounds and screen shake.

    ``trauma`` is a 0..1 value that decays over time; the actual shake
    offset is ``trauma ** 2`` which feels much nicer than a linear fade.
    """

    def __init__(self, viewport: Tuple[int, int]) -> None:
        self.x = 0.0
        self.y = 0.0
        self.view_width = float(viewport[0])
        self.view_height = float(viewport[1])
        self.zoom = 1.0
        self.trauma = 0.0
        self.shake_scale = 1.0
        self._shake_offset = (0.0, 0.0)
        self._rng = random.Random()

    # -- viewport --------------------------------------------------------
    def set_viewport(self, width: int, height: int) -> None:
        self.view_width = float(width)
        self.view_height = float(height)

    def set_zoom(self, zoom: float) -> None:
        self.zoom = clamp(zoom, 0.5, 2.0)

    @property
    def half_width(self) -> float:
        return self.view_width / (2.0 * self.zoom)

    @property
    def half_height(self) -> float:
        return self.view_height / (2.0 * self.zoom)

    # -- shake -----------------------------------------------------------
    def add_trauma(self, amount: float) -> None:
        self.trauma = clamp(self.trauma + amount, 0.0, 1.0)

    def update(self, dt: float, decay: float = 1.6) -> None:
        self.trauma = max(0.0, self.trauma - decay * dt)
        amount = self.trauma * self.trauma * self.shake_scale
        if amount > 0.0:
            self._shake_offset = (
                self._rng.uniform(-amount, amount) * 26.0,
                self._rng.uniform(-amount, amount) * 26.0,
            )
        else:
            self._shake_offset = (0.0, 0.0)

    @property
    def shake_offset(self) -> Tuple[float, float]:
        return self._shake_offset

    # -- follow ----------------------------------------------------------
    def follow(self, target_x: float, target_y: float, dt: float, smoothing: float = 7.5) -> None:
        goal_x = target_x - self.half_width
        goal_y = target_y - self.half_height
        if smoothing <= 0.0:
            self.x, self.y = goal_x, goal_y
            return
        factor = 1.0 - math.exp(-smoothing * dt)
        self.x += (goal_x - self.x) * factor
        self.y += (goal_y - self.y) * factor

    def clamp_to_world(
        self, world_width: float, world_height: float
    ) -> None:
        """Keep the visible rect inside the arena when it is large enough."""
        view_w = self.half_width * 2.0
        view_h = self.half_height * 2.0
        if view_w >= world_width:
            self.x = (world_width - view_w) * 0.5
        else:
            self.x = clamp(self.x, 0.0, world_width - view_w)
        if view_h >= world_height:
            self.y = (world_height - view_h) * 0.5
        else:
            self.y = clamp(self.y, 0.0, world_height - view_h)

    def snap_to(self, x: float, y: float) -> None:
        self.x = x - self.half_width
        self.y = y - self.half_height

    # -- queries ---------------------------------------------------------
    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.half_width, self.y + self.half_height)

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.half_width * 2.0, self.half_height * 2.0)

    def visible_rect_with_margin(
        self, margin: float = 0.0
    ) -> Tuple[float, float, float, float]:
        return (
            self.x - margin,
            self.y - margin,
            self.half_width * 2.0 + margin * 2.0,
            self.half_height * 2.0 + margin * 2.0,
        )

    def is_visible(self, x: float, y: float, radius: float = 0.0) -> bool:
        return (
            self.x - radius <= x <= self.x + self.half_width * 2.0 + radius
            and self.y - radius <= y <= self.y + self.half_height * 2.0 + radius
        )

    def world_to_screen(self, x: float, y: float) -> Tuple[float, float]:
        cx, cy = self.center
        sx, sy = self._shake_offset
        return ((x - cx) + self.half_width + sx, (y - cy) + self.half_height + sy)

    def screen_to_world(self, x: float, y: float) -> Tuple[float, float]:
        cx, cy = self.center
        sx, sy = self._shake_offset
        return (x - self.half_width - sx + cx, y - self.half_height - sy + cy)


__all__ = ["Camera"]
