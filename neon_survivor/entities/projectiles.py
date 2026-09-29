"""Projectiles: player bullets and enemy shots.

Both share one lightweight class; the ``hostile`` flag decides which side a
bullet damages and which sprite palette it uses.
"""

from __future__ import annotations

import math
from typing import List

from neon_survivor.core.mathutils import distance_sq

# --- shared palettes -----------------------------------------------------
PLAYER_BULLET_COLOR = (150, 240, 255)
PLAYER_BULLET_CORE = (255, 255, 255)
ENEMY_BULLET_COLOR = (255, 108, 150)
ENEMY_BULLET_CORE = (255, 226, 236)


class Bullet:
    """A single travelling projectile."""

    __slots__ = (
        "x",
        "y",
        "vx",
        "vy",
        "damage",
        "radius",
        "life",
        "max_life",
        "hostile",
        "pierce",
        "color",
        "core",
        "trail",
        "angle",
        "owner",
        "alive",
        "knockback",
    )

    def __init__(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        damage: float,
        radius: float = 5.0,
        life: float = 1.6,
        hostile: bool = False,
        pierce: int = 0,
        color: tuple = PLAYER_BULLET_COLOR,
        core: tuple = PLAYER_BULLET_CORE,
        knockback: float = 150.0,
        owner=None,
    ) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.damage = damage
        self.radius = radius
        self.life = life
        self.max_life = life
        self.hostile = hostile
        self.pierce = pierce
        self.color = color
        self.core = core
        self.trail: List[tuple] = []
        self.knockback = knockback
        self.angle = math.atan2(vy, vx)
        self.owner = owner
        self.alive = True

    @property
    def speed(self) -> float:
        return math.hypot(self.vx, self.vy)

    @property
    def life_ratio(self) -> float:
        return max(0.0, min(1.0, self.life / self.max_life)) if self.max_life > 0 else 0.0

    def hit(self) -> bool:
        """Register a hit; returns ``True`` while the bullet survives."""
        self.pierce -= 1
        if self.pierce < 0:
            self.alive = False
            return False
        return True

    def update(self, dt: float, pillar_normal=None) -> None:
        if not self.alive:
            return
        self.life -= dt
        if self.life <= 0.0:
            self.alive = False
            return
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.trail.append((self.x, self.y))
        if len(self.trail) > 6:
            del self.trail[0]


class ProjectilePool:
    """Reusable list of bullets with cheap bulk updates."""

    def __init__(self) -> None:
        self.bullets: List[Bullet] = []

    def clear(self) -> None:
        self.bullets.clear()

    def spawn(self, *args, **kwargs) -> Bullet:
        bullet = Bullet(*args, **kwargs)
        self.bullets.append(bullet)
        return bullet

    def __len__(self) -> int:
        return len(self.bullets)

    def update(self, dt: float, arena, pillars=None) -> None:
        """Move every bullet and kill the ones leaving the arena/pillars."""
        from neon_survivor.core.collision import resolve_pillars

        alive: List[Bullet] = []
        for bullet in self.bullets:
            if not bullet.alive:
                continue
            bullet.update(dt)
            if not bullet.alive:
                continue

            pos = [bullet.x, bullet.y]
            local = arena.nearby_pillars(*pos, bullet.radius)
            bounce = resolve_pillars(pos, bullet.radius, local, bounce=0.0)
            bullet.x, bullet.y = pos

            if not arena.contains(bullet.x, bullet.y, -bullet.radius):
                bullet.alive = False
                continue
            if bounce is not None:
                # Reflect off the pillar so shots glance instead of sticking.
                nx, ny = bounce
                if nx or ny:
                    length = math.hypot(nx, ny)
                    if length > 1e-6:
                        ux, uy = nx / length, ny / length
                        dot = bullet.vx * ux + bullet.vy * uy
                        bullet.vx = bullet.vx - 2.0 * dot * ux
                        bullet.vy = bullet.vy - 2.0 * dot * uy
                        bullet.x += ux * 2.0
                        bullet.y += uy * 2.0
                bullet.life = min(bullet.life, 0.12)
            alive.append(bullet)
        self.bullets = alive

    def for_each_player_bullet(self):
        return (b for b in self.bullets if not b.hostile)

    def for_each_hostile_bullet(self):
        return (b for b in self.bullets if b.hostile)


def bullet_hits_circle(
    bullet: Bullet, cx: float, cy: float, radius: float
) -> bool:
    """Point-in-expanded-circle test against a bullet's position."""
    total = bullet.radius + radius
    return distance_sq(bullet.x, bullet.y, cx, cy) <= total * total


__all__ = [
    "Bullet",
    "ProjectilePool",
    "bullet_hits_circle",
    "PLAYER_BULLET_COLOR",
    "ENEMY_BULLET_COLOR",
]
