"""Pooled particle system used for impacts, trails, explosions and pickups.

A single flat list keeps the update loop tight; particles die by shrinking
their remaining life.  The system is rendering-agnostic (it only stores
numbers) so it can be unit tested.
"""

from __future__ import annotations

import math
import random
from typing import List, Sequence, Tuple


class Particle:
    __slots__ = (
        "x",
        "y",
        "vx",
        "vy",
        "life",
        "max_life",
        "size",
        "end_size",
        "drag",
        "color",
        "color_end",
        "glow",
        "shape",
        "spin",
        "angle",
    )

    def __init__(self) -> None:
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.life = 0.0
        self.max_life = 1.0
        self.size = 1.0
        self.end_size = 0.0
        self.drag = 2.0
        self.color = (255, 255, 255)
        self.color_end = (255, 255, 255)
        self.glow = True
        self.shape = "circle"  # circle | square | spark
        self.spin = 0.0
        self.angle = 0.0

    @property
    def alive(self) -> bool:
        return self.life > 0.0

    @property
    def life_ratio(self) -> float:
        if self.max_life <= 0.0:
            return 0.0
        return max(0.0, min(1.0, self.life / self.max_life))


class ParticleSystem:
    """Fixed-capacity particle pool."""

    def __init__(self, capacity: int = 1400) -> None:
        self.capacity = capacity
        self._particles: List[Particle] = []
        self._rng = random.Random()

    # -- management ------------------------------------------------------
    def clear(self) -> None:
        self._particles.clear()

    def __len__(self) -> int:
        return len(self._particles)

    @property
    def particles(self) -> Sequence[Particle]:
        return self._particles

    def _acquire(self) -> Particle | None:
        if len(self._particles) >= self.capacity:
            # Recycle the oldest slot rather than dropping the new effect.
            oldest = min(self._particles, key=lambda p: p.life)
            self._particles.remove(oldest)
        particle = Particle()
        self._particles.append(particle)
        return particle

    # -- spawning --------------------------------------------------------
    def spawn(
        self,
        x: float,
        y: float,
        vx: float = 0.0,
        vy: float = 0.0,
        life: float = 0.5,
        size: float = 3.0,
        end_size: float = 0.0,
        color: Tuple[int, int, int] = (255, 255, 255),
        color_end: Tuple[int, int, int] | None = None,
        drag: float = 2.0,
        glow: bool = True,
        shape: str = "circle",
    ) -> Particle | None:
        p = self._acquire()
        if p is None:
            return None
        p.x, p.y = x, y
        p.vx, p.vy = vx, vy
        p.life = life
        p.max_life = life
        p.size = size
        p.end_size = end_size
        p.color = color
        p.color_end = color_end if color_end is not None else color
        p.drag = drag
        p.glow = glow
        p.shape = shape
        p.angle = self._rng.uniform(0.0, math.tau)
        p.spin = self._rng.uniform(-6.0, 6.0)
        return p

    def burst(
        self,
        x: float,
        y: float,
        count: int,
        speed: Tuple[float, float],
        life: Tuple[float, float] = (0.25, 0.6),
        size: Tuple[float, float] = (2.0, 4.5),
        color: Tuple[int, int, int] = (255, 255, 255),
        color_end: Tuple[int, int, int] | None = None,
        drag: float = 3.0,
        shape: str = "circle",
        glow: bool = True,
    ) -> None:
        rng = self._rng
        for _ in range(count):
            angle = rng.uniform(0.0, math.tau)
            magnitude = rng.uniform(*speed)
            self.spawn(
                x,
                y,
                math.cos(angle) * magnitude,
                math.sin(angle) * magnitude,
                life=rng.uniform(*life),
                size=rng.uniform(*size),
                color=color,
                color_end=color_end,
                drag=drag,
                shape=shape,
                glow=glow,
            )

    def ring(
        self,
        x: float,
        y: float,
        count: int,
        radius: float,
        speed: Tuple[float, float],
        **kwargs,
    ) -> None:
        """Emit particles evenly spaced on a circle, moving outward."""
        rng = self._rng
        for i in range(count):
            angle = math.tau * (i / max(1, count)) + rng.uniform(-0.08, 0.08)
            magnitude = rng.uniform(*speed)
            self.spawn(
                x + math.cos(angle) * radius,
                y + math.sin(angle) * radius,
                math.cos(angle) * magnitude,
                math.sin(angle) * magnitude,
                life=rng.uniform(*kwargs.get("life", (0.3, 0.7))),
                size=rng.uniform(*kwargs.get("size", (2.0, 4.0))),
                color=kwargs.get("color", (255, 255, 255)),
                color_end=kwargs.get("color_end"),
                drag=kwargs.get("drag", 2.5),
                shape=kwargs.get("shape", "circle"),
                glow=kwargs.get("glow", True),
            )

    def trail(self, x: float, y: float, color: Tuple[int, int, int], life: float = 0.22, size: float = 3.0) -> None:
        self.spawn(x, y, 0.0, 0.0, life=life, size=size, color=color, drag=6.0)

    # -- simulation ------------------------------------------------------
    def update(self, dt: float) -> None:
        alive: List[Particle] = []
        for p in self._particles:
            p.life -= dt
            if p.life <= 0.0:
                continue
            damping = math.exp(-p.drag * dt)
            p.vx *= damping
            p.vy *= damping
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.angle += p.spin * dt
            alive.append(p)
        self._particles = alive

    def update_visual(self, dt: float) -> None:
        """Advance purely cosmetic fields (used between simulation steps)."""
        for p in self._particles:
            p.spin += dt


__all__ = ["Particle", "ParticleSystem"]
