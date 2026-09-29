"""The player character: movement, aiming, weapon and health."""

from __future__ import annotations

import math
from typing import Tuple

from neon_survivor.config import (
    BULLET_DAMAGE,
    BULLET_SPEED,
    MAX_WEAPON_POWER,
    PLAYER_ACCEL,
    PLAYER_FRICTION,
    PLAYER_INVULN_TIME,
    PLAYER_MAX_HEALTH,
    PLAYER_RADIUS,
    PLAYER_REGEN_DELAY,
    PLAYER_REGEN_RATE,
    PLAYER_SPEED,
    WEAPON_DAMAGE_STEP,
    WEAPON_FIRE_RATE,
    WEAPON_FIRE_RATE_STEP,
    WEAPON_SPREAD_DEGREES,
    WEAPON_SPREAD_TABLE,
)
from neon_survivor.core.mathutils import clamp, from_angle, limit_length


class Player:
    """Player state.  Pure logic: no pygame, no rendering."""

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.radius = PLAYER_RADIUS

        self.health = float(PLAYER_MAX_HEALTH)
        self.max_health = float(PLAYER_MAX_HEALTH)
        self.alive = True

        self.facing = -math.pi / 2
        self.move_dir: Tuple[float, float] = (0.0, 0.0)
        self.moving = False

        # -- weapon ------------------------------------------------------
        self.weapon_power = 1
        self.fire_cooldown = 0.0
        self.recoil = 0.0

        # -- damage feedback --------------------------------------------
        self.invuln_timer = 0.0
        self.hit_flash = 0.0
        self.time_since_damage = 0.0
        self.damage_taken = 0.0

        # -- pickups ------------------------------------------------------
        self.speed_boost = 0.0
        self.shield = 0.0

    # -- queries ---------------------------------------------------------
    @property
    def health_ratio(self) -> float:
        if self.max_health <= 0:
            return 0.0
        return clamp(self.health / self.max_health, 0.0, 1.0)

    @property
    def is_invulnerable(self) -> bool:
        return self.invuln_timer > 0.0

    @property
    def can_fire(self) -> bool:
        return self.alive and self.fire_cooldown <= 0.0

    @property
    def fire_rate(self) -> float:
        return WEAPON_FIRE_RATE * (1.0 + WEAPON_FIRE_RATE_STEP * (self.weapon_power - 1))

    @property
    def damage(self) -> float:
        return BULLET_DAMAGE * (1.0 + WEAPON_DAMAGE_STEP * (self.weapon_power - 1))

    @property
    def bullet_count(self) -> int:
        index = clamp(self.weapon_power - 1, 0, len(WEAPON_SPREAD_TABLE) - 1)
        return WEAPON_SPREAD_TABLE[index]

    @property
    def effective_speed(self) -> float:
        return PLAYER_SPEED * (1.25 if self.speed_boost > 0.0 else 1.0)

    # -- movement --------------------------------------------------------
    def update_movement(
        self,
        move_x: float,
        move_y: float,
        dt: float,
        friction: float = PLAYER_FRICTION,
    ) -> None:
        """Accelerate towards the normalised input direction."""
        # Diagonal normalisation keeps the speed constant.
        mag = math.hypot(move_x, move_y)
        if mag > 1e-6:
            self.move_dir = (move_x / mag, move_y / mag)
            self.moving = True
        else:
            self.move_dir = (0.0, 0.0)
            self.moving = False

        target_speed = self.effective_speed
        desired_vx = self.move_dir[0] * target_speed
        desired_vy = self.move_dir[1] * target_speed

        accel = PLAYER_ACCEL * dt
        self.vx += clamp(desired_vx - self.vx, -accel, accel)
        self.vy += clamp(desired_vy - self.vy, -accel, accel)

        if not self.moving:
            damp = math.exp(-friction * dt)
            self.vx *= damp
            self.vy *= damp

        self.vx, self.vy = limit_length(self.vx, self.vy, target_speed)
        self.x += self.vx * dt
        self.y += self.vy * dt

    def apply_knockback(self, nx: float, ny: float, strength: float) -> None:
        self.vx += nx * strength
        self.vy += ny * strength
        self.vx, self.vy = limit_length(self.vx, self.vy, self.effective_speed * 1.6)

    def aim_at(self, world_x: float, world_y: float) -> float:
        """Point the weapon at a world position; returns the angle."""
        self.facing = math.atan2(world_y - self.y, world_x - self.x)
        return self.facing

    # -- weapon ----------------------------------------------------------
    def tick_weapon(self, dt: float) -> None:
        self.fire_cooldown -= dt
        if self.fire_cooldown < 0.0:
            self.fire_cooldown = 0.0

    def begin_recoil(self) -> None:
        self.recoil = min(1.0, self.recoil + 0.35)

    def shot_angles(self) -> list:
        """Angles of every bullet in the current shot."""
        count = self.bullet_count
        if count <= 1:
            return [self.facing]
        spread = math.radians(WEAPON_SPREAD_DEGREES)
        step = spread / (count - 1)
        start = self.facing - spread * 0.5
        return [start + step * i for i in range(count)]

    def fire(self) -> list:
        """Emit the bullets of one shot and reset the cooldown."""
        if not self.can_fire:
            return []
        muzzle = self.radius + 10.0
        bullets = []
        for angle in self.shot_angles():
            vx, vy = from_angle(angle, BULLET_SPEED)
            bullets.append((self.x + vx / BULLET_SPEED * muzzle, self.y + vy / BULLET_SPEED * muzzle, vx, vy))
        self.fire_cooldown = 1.0 / self.fire_rate
        self.begin_recoil()
        return bullets

    def upgrade_weapon(self, amount: int = 1) -> int:
        """Increase the weapon level; returns the number of levels gained."""
        before = self.weapon_power
        self.weapon_power = min(MAX_WEAPON_POWER, self.weapon_power + amount)
        return self.weapon_power - before

    # -- health ----------------------------------------------------------
    def heal(self, amount: float) -> float:
        before = self.health
        self.health = min(self.max_health, self.health + amount)
        return self.health - before

    def take_damage(self, amount: float, ignore_invuln: bool = False) -> bool:
        """Apply damage.  Returns ``True`` when it actually applied."""
        if not self.alive:
            return False
        if self.invuln_timer > 0.0 and not ignore_invuln:
            return False
        if self.shield > 0.0:
            self.shield = max(0.0, self.shield - amount)
            self.hit_flash = max(self.hit_flash, 0.12)
            self.time_since_damage = 0.0
            return True

        self.health -= amount
        self.damage_taken += amount
        self.invuln_timer = PLAYER_INVULN_TIME
        self.hit_flash = 1.0
        self.time_since_damage = 0.0
        if self.health <= 0.0:
            self.health = 0.0
            self.alive = False
        return True

    # -- per-frame -------------------------------------------------------
    def update(self, dt: float) -> None:
        if self.invuln_timer > 0.0:
            self.invuln_timer = max(0.0, self.invuln_timer - dt)
        if self.hit_flash > 0.0:
            self.hit_flash = max(0.0, self.hit_flash - dt * 4.0)
        if self.recoil > 0.0:
            self.recoil = max(0.0, self.recoil - dt * 6.0)
        if self.speed_boost > 0.0:
            self.speed_boost = max(0.0, self.speed_boost - dt)
        if self.shield > 0.0:
            self.shield = max(0.0, self.shield - dt * 0.35)

        self.time_since_damage += dt
        if self.alive and self.time_since_damage >= PLAYER_REGEN_DELAY:
            if self.health < self.max_health:
                self.health = min(self.max_health, self.health + PLAYER_REGEN_RATE * dt)

        self.tick_weapon(dt)

    def reset(self, x: float, y: float) -> None:
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.health = self.max_health
        self.alive = True
        self.weapon_power = 1
        self.fire_cooldown = 0.0
        self.recoil = 0.0
        self.invuln_timer = 0.0
        self.hit_flash = 0.0
        self.time_since_damage = 0.0
        self.damage_taken = 0.0
        self.speed_boost = 0.0
        self.shield = 0.0


__all__ = ["Player"]
