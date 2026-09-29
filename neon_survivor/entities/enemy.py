"""Enemies and their AI behaviours.

Each archetype is instantiated from :mod:`neon_survivor.entities.enemy_types`
and its behaviour is selected by a string, which keeps a single ``update``
loop instead of a deep class hierarchy.

Behaviours
----------
``chase``    straight pursuit (with optional sine weaving)
``shooter``  keeps a preferred distance, fires projectiles
``charger``  wind-up, then a fast straight-line dash
``weaver``   lateral weaving + opportunistic shots
``boss``     pursuit, radial bullet patterns, rage at low health
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

from neon_survivor.core.mathutils import (
    angle_between,
    clamp,
    from_angle,
    normalize,
)
from neon_survivor.entities.enemy_types import (
    CHARGER_DASH_DAMAGE_MULTIPLIER,
    EnemyArchetype,
    MAX_SPLIT_DEPTH,
    get_archetype,
)


class Enemy:
    """A single enemy instance."""

    __slots__ = (
        "archetype",
        "kind",
        "behavior",
        "x",
        "y",
        "vx",
        "vy",
        "kx",
        "ky",
        "radius",
        "health",
        "max_health",
        "speed",
        "touch_damage",
        "score",
        "mass",
        "color",
        "accent",
        "alive",
        "elite",
        "spawn_grace",
        "hit_flash",
        "age",
        "phase",
        "state",
        "state_timer",
        "shoot_timer",
        "dash_dir",
        "rage",
        "wobble_seed",
        "face_angle",
        "knockback_resistance",
        "boss_spawned_escorts",
        "aggro",
        "split_depth",
    )

    def __init__(
        self,
        kind: str,
        x: float,
        y: float,
        hp_multiplier: float = 1.0,
        speed_multiplier: float = 1.0,
        damage_multiplier: float = 1.0,
        elite: bool = False,
        split_depth: int = 0,
    ) -> None:
        arch: EnemyArchetype = get_archetype(kind)
        self.archetype = arch
        self.kind = kind
        self.behavior = arch.behavior
        self.x = x
        self.y = y
        #: Steering velocity, fully owned by the AI.
        self.vx = 0.0
        self.vy = 0.0
        #: Impulse velocity from hits, decays on its own.
        self.kx = 0.0
        self.ky = 0.0
        self.radius = arch.radius
        self.elite = elite

        if elite:
            self.max_health = arch.scaled_health(hp_multiplier) * 1.85
            self.speed = arch.scaled_speed(speed_multiplier) * 1.12
            self.touch_damage = arch.touch_damage * damage_multiplier * 1.3
            self.score = int(arch.score * 2.0)
            self.radius = arch.radius * 1.14
            self.color = (255, 236, 120)
            self.accent = (255, 255, 232)
        else:
            self.max_health = arch.scaled_health(hp_multiplier)
            self.speed = arch.scaled_speed(speed_multiplier)
            self.touch_damage = arch.touch_damage * damage_multiplier
            self.score = arch.score
            self.color = arch.color
            self.accent = arch.accent

        self.health = self.max_health
        self.mass = arch.mass
        self.alive = True
        self.spawn_grace = 0.55
        self.hit_flash = 0.0
        self.age = 0.0
        self.phase = 0.0
        self.state = "idle"
        self.state_timer = 0.0
        self.shoot_timer = arch.shoot_interval * (0.35 if elite else 0.6)
        self.dash_dir: Tuple[float, float] = (0.0, 0.0)
        self.rage = 0.0
        self.wobble_seed = (x * 0.013 + y * 0.021) % math.tau
        self.face_angle = 0.0
        self.knockback_resistance = 1.0 / max(0.35, arch.mass)
        self.boss_spawned_escorts = False
        self.aggro = False
        #: How many times this lineage has already split (see MAX_SPLIT_DEPTH).
        self.split_depth = split_depth

    # -- helpers ---------------------------------------------------------
    @property
    def is_boss(self) -> bool:
        return self.archetype.is_boss

    @property
    def health_ratio(self) -> float:
        if self.max_health <= 0:
            return 0.0
        return clamp(self.health / self.max_health, 0.0, 1.0)

    @property
    def can_split(self) -> bool:
        """Splitters reproduce only up to :data:`MAX_SPLIT_DEPTH` generations.

        Without this guard a splitter child — itself a splitter — would
        split again, doubling the population forever.
        """
        return (
            self.archetype.split_into > 0
            and self.split_depth < MAX_SPLIT_DEPTH
        )

    @property
    def is_damaging(self) -> bool:
        """Every archetype hurts on contact (a charger hurts harder)."""
        return True

    @property
    def contact_damage(self) -> float:
        """Damage dealt on touch, before the invulnerability check."""
        if self.behavior == "charger" and self.state == "dash":
            # The dash is the whole point of the archetype.
            return self.touch_damage * CHARGER_DASH_DAMAGE_MULTIPLIER
        return self.touch_damage

    def distance_to(self, px: float, py: float) -> float:
        return math.hypot(px - self.x, py - self.y)

    # -- damage ----------------------------------------------------------
    def take_damage(self, amount: float, knockback: float = 0.0, nx: float = 0.0, ny: float = 0.0) -> bool:
        """Returns ``True`` when the hit killed the enemy."""
        if not self.alive or self.spawn_grace > 0.0:
            return False
        self.health -= amount
        self.hit_flash = 1.0
        self.aggro = True
        if knockback > 0.0:
            strength = knockback * self.knockback_resistance
            self.kx += nx * strength
            self.ky += ny * strength
        if self.health <= 0.0:
            self.health = 0.0
            self.alive = False
            return True
        return False

    def separate(self, other: "Enemy") -> bool:
        """Push apart from another enemy to avoid stacking."""
        dx = self.x - other.x
        dy = self.y - other.y
        min_dist = self.radius + other.radius
        dist_sq = dx * dx + dy * dy
        if dist_sq >= min_dist * min_dist:
            return False
        if dist_sq <= 1e-9:
            # Coincident centres: start from a deterministic unit offset so
            # the separation maths stays finite and lands on ``min_dist``.
            dx, dy = 1.0, 0.0
            dist = 1.0
            self.x += dx
            self.y += dy
        else:
            dist = math.sqrt(dist_sq)
        overlap = (min_dist - dist) * 0.5
        ux, uy = dx / dist, dy / dist
        # The heavier entity is pushed less.
        total = self.mass + other.mass
        self_share = other.mass / total
        other_share = 1.0 - self_share
        self.x += ux * overlap * 2.0 * self_share
        self.y += uy * overlap * 2.0 * self_share
        other.x -= ux * overlap * 2.0 * other_share
        other.y -= uy * overlap * 2.0 * other_share
        return True

    # -- AI --------------------------------------------------------------
    def update(
        self,
        dt: float,
        player_x: float,
        player_y: float,
        shots: Optional[list] = None,
    ) -> None:
        """Advance the AI by *dt*.  ``shots`` collects requested projectiles."""
        if not self.alive:
            return
        self.age += dt
        if self.spawn_grace > 0.0:
            self.spawn_grace = max(0.0, self.spawn_grace - dt)
        if self.hit_flash > 0.0:
            self.hit_flash = max(0.0, self.hit_flash - dt * 5.0)
        self.phase += dt

        handler = {
            "chase": self._behave_chase,
            "shooter": self._behave_shooter,
            "charger": self._behave_charger,
            "weaver": self._behave_weaver,
            "boss": self._behave_boss,
        }.get(self.behavior, self._behave_chase)
        handler(dt, player_x, player_y, shots)

        self._integrate(dt)

    # -- integration -----------------------------------------------------
    def _integrate(self, dt: float) -> None:
        self.x += (self.vx + self.kx) * dt
        self.y += (self.vy + self.ky) * dt
        # Knockback bleeds off quickly and never fights the AI.
        damp = math.exp(-7.0 * dt)
        self.kx *= damp
        self.ky *= damp

    def _steer_towards(
        self, dt: float, target_x: float, target_y: float, speed: float, turn: float = 9.0
    ) -> None:
        """Rotate the heading towards the target at *turn* rad/s.

        The AI owns ``vx/vy`` outright, so the enemy always travels at
        *speed* along a smoothly turning heading.  Knockback lives in
        ``kx/ky`` and simply adds on top.
        """
        ux, uy = normalize(target_x - self.x, target_y - self.y)
        if ux == 0.0 and uy == 0.0:
            self.vx = self.vy = 0.0
            return
        cx, cy = normalize(self.vx, self.vy)
        if cx == 0.0 and cy == 0.0:
            nx, ny = ux, uy
        else:
            blend = clamp(turn * dt, 0.0, 1.0)
            nx, ny = normalize(cx + (ux - cx) * blend, cy + (uy - cy) * blend)
            if nx == 0.0 and ny == 0.0:
                nx, ny = ux, uy
        self.vx, self.vy = from_angle(math.atan2(ny, nx), speed)

    def _steer_away(
        self, dt: float, target_x: float, target_y: float, speed: float, turn: float = 7.0
    ) -> None:
        """Steer directly away from *target*."""
        self._steer_towards(
            dt, self.x * 2.0 - target_x, self.y * 2.0 - target_y, speed, turn
        )

    def _freeze(self) -> None:
        """Stop steering (wind-up, recovery...)."""
        self.vx = 0.0
        self.vy = 0.0

    # -- behaviours ------------------------------------------------------
    def _behave_chase(self, dt, px, py, shots) -> None:
        arch = self.archetype
        target_x, target_y = px, py
        if arch.weave_amplitude > 0.0:
            # Offset the pursuit point along the perpendicular axis.
            angle = angle_between(self.x, self.y, px, py)
            offset = math.sin(self.phase * arch.weave_frequency + self.wobble_seed) * arch.weave_amplitude
            target_x = px - math.sin(angle) * offset
            target_y = py + math.cos(angle) * offset
        self._steer_towards(dt, target_x, target_y, self.speed)
        self.face_angle = math.atan2(py - self.y, px - self.x)

    def _behave_shooter(self, dt, px, py, shots) -> None:
        arch = self.archetype
        dist = self.distance_to(px, py)
        desired = arch.preferred_range

        if dist > desired * 1.15:
            self._steer_towards(dt, px, py, self.speed)
        elif dist < desired * 0.75:
            self._steer_away(dt, px, py, self.speed * 0.9)
        else:
            # Strafe sideways to stay dangerous but avoid contact.
            side = 1.0 if (self.wobble_seed > math.pi) else -1.0
            self._steer_towards(
                dt,
                self.x - (py - self.y) * side,
                self.y + (px - self.x) * side,
                self.speed * 0.8,
            )

        self.face_angle = math.atan2(py - self.y, px - self.x)
        self._maybe_shoot(dt, px, py, shots)

    def _behave_weaver(self, dt, px, py, shots) -> None:
        arch = self.archetype
        angle = angle_between(self.x, self.y, px, py)
        offset = math.sin(self.phase * arch.weave_frequency + self.wobble_seed) * arch.weave_amplitude
        target_x = px - math.sin(angle) * offset
        target_y = py + math.cos(angle) * offset
        self._steer_towards(dt, target_x, target_y, self.speed)
        self.face_angle = angle
        self._maybe_shoot(dt, px, py, shots)

    def _behave_charger(self, dt, px, py, shots) -> None:
        arch = self.archetype
        self.state_timer -= dt
        dist = self.distance_to(px, py)

        if self.state == "idle":
            self._steer_towards(dt, px, py, self.speed)
            self.face_angle = math.atan2(py - self.y, px - self.x)
            if dist < 460.0 and self.age > 0.5:
                self.state = "windup"
                self.state_timer = arch.charge_windup
        elif self.state == "windup":
            # Freeze and telegraph the dash direction.
            self._freeze()
            self.face_angle = math.atan2(py - self.y, px - self.x)
            if self.state_timer <= 0.0:
                self.state = "dash"
                self.state_timer = arch.charge_duration
                dx, dy = normalize(px - self.x, py - self.y)
                self.dash_dir = (dx, dy)
        elif self.state == "dash":
            self.vx, self.vy = from_angle(math.atan2(self.dash_dir[1], self.dash_dir[0]), arch.charge_speed)
            if self.state_timer <= 0.0:
                self.state = "recover"
                self.state_timer = arch.charge_cooldown
        else:  # recover
            self._steer_towards(dt, px, py, self.speed * 0.5, turn=5.0)
            if self.state_timer <= 0.0:
                self.state = "idle"

    def _behave_boss(self, dt, px, py, shots) -> None:
        arch = self.archetype
        # Enrage progressively when hurt.
        target_rage = 1.0 - self.health_ratio
        self.rage += (target_rage - self.rage) * clamp(dt * 1.5, 0.0, 1.0)
        speed = self.speed + (arch.boss_rage_speed - self.speed) * self.rage

        dist = self.distance_to(px, py)
        if dist > arch.preferred_range * 1.4:
            self._steer_towards(dt, px, py, speed, turn=4.5)
        elif dist < arch.preferred_range * 0.65:
            self._steer_away(dt, px, py, speed * 0.85)
        else:
            side = 1.0 if (self.wobble_seed > math.pi) else -1.0
            self._steer_towards(
                dt,
                self.x - (py - self.y) * side,
                self.y + (px - self.x) * side,
                speed * 0.85,
            )
        self.face_angle = math.atan2(py - self.y, px - self.x)

        interval = arch.shoot_interval * (1.0 - 0.35 * self.rage)
        self.shoot_timer -= dt
        if self.shoot_timer <= 0.0:
            self.shoot_timer = interval
            if shots is not None:
                self._emit_boss_pattern(px, py, shots)

    # -- shooting --------------------------------------------------------
    def _maybe_shoot(self, dt, px, py, shots) -> None:
        arch = self.archetype
        if arch.shoot_interval <= 0.0 or shots is None:
            return
        self.shoot_timer -= dt
        if self.shoot_timer > 0.0:
            return
        self.shoot_timer = arch.shoot_interval
        dx, dy = normalize(px - self.x, py - self.y)
        # Small aim jitter so the player can dodge reliably.
        spread = (self.wobble_seed % 1.0 - 0.5) * 0.14
        angle = math.atan2(dy, dx) + spread
        vx, vy = from_angle(angle, arch.shoot_speed)
        shots.append(
            (self.x + dx * (self.radius + 6.0), self.y + dy * (self.radius + 6.0), vx, vy,
             arch.shoot_damage, arch.radius * 0.5)
        )

    def _emit_boss_pattern(self, px, py, shots) -> None:
        arch = self.archetype
        base = math.atan2(py - self.y, px - self.x)
        count = arch.boss_radial_bullets
        speed = arch.shoot_speed * (1.0 + 0.25 * self.rage)
        # Radial ring...
        for i in range(count):
            angle = math.tau * i / count + self.phase * 0.6
            vx, vy = from_angle(angle, speed)
            shots.append(
                (self.x + vx / speed * (self.radius + 8.0),
                 self.y + vy / speed * (self.radius + 8.0),
                 vx, vy, arch.shoot_damage, 8.0)
            )
        # ...plus a fast aimed volley that gets denser with rage.
        aimed = 3 + int(self.rage * 3)
        for i in range(aimed):
            angle = base + (i - (aimed - 1) / 2.0) * 0.18
            vx, vy = from_angle(angle, speed * 1.35)
            shots.append(
                (self.x + vx / speed * (self.radius + 10.0),
                 self.y + vy / speed * (self.radius + 10.0),
                 vx, vy, arch.shoot_damage, 7.0)
            )

    # -- knockback helper ------------------------------------------------
    def knockback_from(self, src_x: float, src_y: float, strength: float) -> Tuple[float, float]:
        nx, ny = normalize(self.x - src_x, self.y - src_y)
        return (nx * strength, ny * strength)


__all__ = ["Enemy"]
