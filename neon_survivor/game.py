"""The play scene: owns the simulation and composes the final frame.

``GameScene`` is deliberately free of windowing concerns — it receives
``dt`` and input, and draws into whatever surface it is given.  That makes
the whole gameplay loop runnable head-less, which the tests rely on.
"""

from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple

import pygame

from neon_survivor.config import (
    ENEMY_HARD_CAP,
    ENEMY_KNOCKBACK,
    HIT_STOP_ON_BOSS_DEATH,
    LOW_HEALTH_VIGNETTE,
    NUKE_WAVE_SPEED,
    PICKUP_DROP_CHANCE,
    SCREEN_SHAKE_DECAY,
    SCREEN_SHAKE_ON_BOSS,
    SCREEN_SHAKE_ON_HIT,
)
from neon_survivor.core.camera import Camera
from neon_survivor.core.collision import SpatialHash, resolve_pillars
from neon_survivor.core.difficulty import DifficultyCurve, WaveState
from neon_survivor.core.mathutils import distance_sq, normalize
from neon_survivor.core.particles import ParticleSystem
from neon_survivor.core.score import ScoreBoard
from neon_survivor.core.spawner import SpawnDirector
from neon_survivor.core.world import Arena
from neon_survivor.entities.enemy import Enemy
from neon_survivor.entities.enemy_types import BOSS_ESCORTS
from neon_survivor.entities.pickups import Pickup, apply_pickup, roll_pickup
from neon_survivor.entities.player import Player
from neon_survivor.entities.projectiles import ProjectilePool
from neon_survivor.gfx import fx
from neon_survivor.gfx.renderer import WorldRenderer
from neon_survivor.settings import Settings
from neon_survivor.ui.hud import Hud
from neon_survivor.ui.theme import Palette
from neon_survivor.ui.widgets import Banner

RGB = Tuple[int, int, int]

#: Input actions the scene understands.
KEY_LEFT = (pygame.K_LEFT, pygame.K_a, pygame.K_q)
KEY_RIGHT = (pygame.K_RIGHT, pygame.K_d)
KEY_UP = (pygame.K_UP, pygame.K_w, pygame.K_z)
KEY_DOWN = (pygame.K_DOWN, pygame.K_s)


class InputState:
    """Keyboard/mouse snapshot for one frame."""

    def __init__(self) -> None:
        self.move_x = 0.0
        self.move_y = 0.0
        self.firing = False
        self.mouse_pos: Tuple[int, int] = (0, 0)
        self.mouse_world: Tuple[float, float] = (0.0, 0.0)

    @classmethod
    def from_keys(
        cls,
        keys,
        mouse_pos: Tuple[int, int],
        mouse_buttons,
        mouse_world: Tuple[float, float],
    ) -> "InputState":
        """Build a snapshot from a ``pygame.key.get_pressed()`` style object."""
        state = cls()
        state.move_x = (1.0 if any(keys[k] for k in KEY_RIGHT) else 0.0) - (
            1.0 if any(keys[k] for k in KEY_LEFT) else 0.0
        )
        state.move_y = (1.0 if any(keys[k] for k in KEY_DOWN) else 0.0) - (
            1.0 if any(keys[k] for k in KEY_UP) else 0.0
        )
        # ``mouse_buttons`` is the (left, middle, right, wheel, extra) tuple.
        state.firing = bool(mouse_buttons[0]) if len(mouse_buttons) else False
        state.mouse_pos = mouse_pos
        state.mouse_world = mouse_world
        return state


class GameScene:
    """One complete run of the game."""

    def __init__(
        self,
        settings: Settings,
        audio=None,
        arena: Optional[Arena] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.settings = settings
        self.audio = audio
        self.rng = random.Random(seed)

        self.arena = arena or Arena(seed=seed)
        self.camera = Camera((1280, 720))
        self.renderer = WorldRenderer(self.arena, self.camera)
        self.curve = DifficultyCurve()
        self.spawner = SpawnDirector(self.curve, seed=seed)
        self.hud = Hud()
        self.banner = Banner()
        self.particles = ParticleSystem()
        self.floaters = fx.FloatingTextManager()
        self.bullets = ProjectilePool()
        self.score = ScoreBoard()

        self.player = Player(*self.arena.center)
        self.enemies: List[Enemy] = []
        self.pickups: List[Pickup] = []

        self.time = 0.0
        self.running = True
        self.finished = False
        self.hit_stop = 0.0
        self.damage_flash = 0.0
        self.nuke_wave_radius = 0.0
        self.nuke_origin: Optional[Tuple[float, float]] = None
        self.magnet_timer = 0.0
        self.wave_state: WaveState = self.curve.state_for_time(0.0)
        self.last_wave = 1
        self.bosses_spawned = 0
        self.music_key = "action"
        self._magnet_pulse = 0.0

        self.camera.shake_scale = settings.screen_shake
        self.hud.show_fps = settings.show_fps
        self._pending_shots: List[tuple] = []
        self._apply_camera()

    # ==================================================================
    # Lifecycle
    # ==================================================================
    def _apply_camera(self) -> None:
        self.camera.set_viewport(*self._viewport)
        self.camera.snap_to(self.player.x, self.player.y)
        self.camera.clamp_to_world(self.arena.width, self.arena.height)

    @property
    def _viewport(self) -> Tuple[int, int]:
        return (max(1, int(self.camera.view_width)), max(1, int(self.camera.view_height)))

    def resize(self, width: int, height: int) -> None:
        self.camera.set_viewport(width, height)
        self.camera.clamp_to_world(self.arena.width, self.arena.height)

    def start_wave(self, wave: int, is_boss: bool) -> None:
        """Announce a new wave and spawn its boss if needed."""
        if wave <= self.last_wave:
            return
        self.last_wave = wave
        if is_boss and self.bosses_spawned < self.wave_state.boss_count:
            self.bosses_spawned += 1
            self._spawn_boss()
        self.banner.show(
            f"WAVE {wave}",
            "BOSS" if is_boss else "",
            Palette.MAGENTA if is_boss else Palette.CYAN,
        )
        if self.audio:
            if is_boss:
                self.audio.play("boss_spawn")
            else:
                self.audio.play("wave_start")

    def _spawn_boss(self) -> None:
        x, y = self.spawner.spawn_point(
            self.player.x, self.player.y,
            self.camera.half_width, self.camera.half_height,
            self.arena.width, self.arena.height, self.arena.wall,
            self.arena.pillars, radius=64.0,
        )
        boss = Enemy(
            "boss", x, y,
            self.wave_state.hp_multiplier * (1.0 + 0.12 * (self.last_wave // 5)),
            self.wave_state.speed_multiplier,
            self.wave_state.damage_multiplier,
        )
        self.enemies.append(boss)
        self.camera.add_trauma(SCREEN_SHAKE_ON_BOSS * 0.6)
        self.particles.ring(x, y, 40, boss.radius, (80, 260), color=boss.color, life=(0.5, 1.0))
        self._set_music("boss")

    # ==================================================================
    # Update
    # ==================================================================
    def update(self, dt: float, input_state: Optional[InputState] = None) -> None:
        if not self.running:
            return
        # Hit-stop briefly freezes the simulation on big impacts.
        if self.hit_stop > 0.0:
            self.hit_stop = max(0.0, self.hit_stop - dt)
            return

        dt = min(dt, 0.05)  # never simulate a huge step after a stall
        self.time += dt
        self.wave_state = self.curve.state_for_time(self.time)

        if self.wave_state.wave > self.last_wave:
            self.start_wave(self.wave_state.wave, self.wave_state.is_boss_wave)
        elif self.wave_state.is_boss_wave and self.bosses_spawned < self.wave_state.boss_count:
            # First wave is handled by start_wave; catch a skipped boss wave.
            self.bosses_spawned += 1
            self._spawn_boss()

        self._update_player(dt, input_state)
        self._update_spawning(dt)
        self._update_enemies(dt)
        self._update_bullets(dt)
        self._update_pickups(dt)
        self._update_nuke(dt)

        self.particles.update(dt)
        self.floaters.update(dt)
        self.banner.update(dt)
        self.hud.update(dt)
        self.score.update(dt)
        self._update_camera(dt)
        self._cleanup()
        self._update_music()

        if not self.player.alive:
            self.running = False
            self.finished = True

    # -- player ----------------------------------------------------------
    def _update_player(self, dt: float, input_state: Optional[InputState]) -> None:
        player = self.player
        if input_state is not None:
            player.aim_at(*input_state.mouse_world)

        move_x = input_state.move_x if input_state else 0.0
        move_y = input_state.move_y if input_state else 0.0
        player.update_movement(move_x, move_y, dt)

        pos = [player.x, player.y]
        self.arena.clamp_position(pos, player.radius)
        resolve_pillars(pos, player.radius, self.arena.nearby_pillars(*pos, player.radius))
        player.x, player.y = pos

        player.update(dt)

        if input_state is not None and input_state.firing:
            self._fire()

        # Engine trail.
        if player.moving:
            back = player.facing + math.pi
            for _ in range(2):
                self.particles.spawn(
                    player.x + math.cos(back) * player.radius * 1.1,
                    player.y + math.sin(back) * player.radius * 1.1,
                    math.cos(back) * 60.0, math.sin(back) * 60.0,
                    life=0.26, size=3.2,
                    color=Palette.CYAN if player.speed_boost <= 0 else Palette.AMBER,
                    drag=4.0,
                )

    def _fire(self) -> None:
        player = self.player
        if not player.can_fire:
            return
        shots = player.fire()
        if not shots:
            return
        self.score.register_shot()
        for bx, by, vx, vy in shots:
            self.bullets.spawn(
                bx, by, vx, vy, player.damage, 5.0, 1.6, False, 0,
                knockback=ENEMY_KNOCKBACK * 0.55, owner=player,
            )
        self.particles.burst(
            player.x + math.cos(player.facing) * player.radius,
            player.y + math.sin(player.facing) * player.radius,
            3, (40, 120), life=(0.08, 0.16), size=(1.5, 3.0),
            color=Palette.BULLET, drag=8.0,
        )
        if self.audio:
            self.audio.play(
                "shoot_heavy" if player.weapon_power >= 4 else "shoot",
                volume=0.8, pitch=1.0 - 0.05 * player.weapon_power,
            )

    # -- spawning --------------------------------------------------------
    def _update_spawning(self, dt: float) -> None:
        # ``min`` also enforces the absolute cap, which the wave curve does
        # not know about (split children bypass the director).
        alive = min(len(self.enemies), ENEMY_HARD_CAP)
        count = self.spawner.pending_spawns(self.wave_state, alive, dt)
        if count <= 0:
            return
        radius = 30.0
        points = self.spawner.spawn_points(
            count, self.player.x, self.player.y,
            self.camera.half_width, self.camera.half_height,
            self.arena.width, self.arena.height, self.arena.wall,
            self.arena.pillars, radius,
        )
        for (x, y) in points:
            kind = self.spawner.pick_type(self.wave_state)
            if not kind:
                continue
            self.spawner.record_spawn(kind)
            enemy = Enemy(
                kind, x, y,
                self.wave_state.hp_multiplier,
                self.wave_state.speed_multiplier,
                self.wave_state.damage_multiplier,
                self.spawner.pick_elite(self.wave_state),
            )
            self.enemies.append(enemy)
            self.particles.ring(x, y, 10, enemy.radius, (20, 90),
                                color=enemy.color, life=(0.25, 0.5))

    # -- enemies ---------------------------------------------------------
    def _update_enemies(self, dt: float) -> None:
        player = self.player
        self._pending_shots = []

        # Broad-phase grid so separation stays O(n) in practice.
        grid = SpatialHash(160.0)
        for enemy in self.enemies:
            grid.insert(enemy.x, enemy.y, enemy.radius * 2.0, enemy)
        for enemy in self.enemies:
            for other in grid.query(enemy.x, enemy.y, enemy.radius * 2.0):
                if other is not enemy:
                    enemy.separate(other)
                    break

        for enemy in self.enemies:
            enemy.update(dt, player.x, player.y, self._pending_shots)

        for sx, sy, vx, vy, damage, radius in self._pending_shots:
            self.bullets.spawn(sx, sy, vx, vy, damage, radius, 4.0, True)

        for enemy in self.enemies:
            pos = [enemy.x, enemy.y]
            bounce = resolve_pillars(
                pos, enemy.radius,
                self.arena.nearby_pillars(*pos, enemy.radius), bounce=0.0,
            )
            self.arena.clamp_position(pos, enemy.radius)
            enemy.x, enemy.y = pos
            if bounce is not None and (bounce[0] or bounce[1]):
                # Chargers bounce off pillars and lose the dash.
                if enemy.state == "dash":
                    enemy.state = "recover"
                    enemy.state_timer = 0.5

    # -- bullets ---------------------------------------------------------
    def _update_bullets(self, dt: float) -> None:
        self.bullets.update(dt, self.arena)
        player = self.player

        for bullet in self.bullets.bullets:
            if not bullet.alive:
                continue
            if bullet.hostile:
                total = bullet.radius + player.radius
                if distance_sq(bullet.x, bullet.y, player.x, player.y) <= total * total:
                    bullet.alive = False
                    if player.take_damage(bullet.damage):
                        self._on_player_hit(bullet.x, bullet.y)
                    continue
                continue

            for enemy in self.enemies:
                total = bullet.radius + enemy.radius
                if distance_sq(bullet.x, bullet.y, enemy.x, enemy.y) > total * total:
                    continue
                nx, ny = normalize(bullet.x - enemy.x, bullet.y - enemy.y)
                died = enemy.take_damage(bullet.damage, bullet.knockback, nx, ny)
                self.score.register_hit()
                self._impact(bullet.x, bullet.y, enemy.color, nx, ny)
                if self.audio:
                    self.audio.play("hit", volume=0.35, pitch=self.rng.uniform(0.92, 1.12))
                if died:
                    self._on_enemy_killed(enemy)
                if not bullet.hit():
                    break

    def _impact(self, x: float, y: float, color, nx: float, ny: float) -> None:
        self.particles.burst(
            x, y, 4, (60, 190), life=(0.1, 0.26), size=(1.5, 3.0),
            color=color, color_end=Palette.TEXT, drag=6.0, shape="spark",
        )

    def _on_enemy_killed(self, enemy: Enemy) -> None:
        big = enemy.is_boss
        points = self.score.register_kill(
            enemy.kind, enemy.score, self.wave_state.score_multiplier
        )
        color = enemy.color
        count = 34 if big else 12
        self.particles.burst(
            enemy.x, enemy.y, count, (70, 320) if big else (50, 200),
            life=(0.3, 0.8) if big else (0.2, 0.5),
            size=(2.0, 6.0) if big else (1.8, 3.6),
            color=color, color_end=Palette.TEXT, drag=3.0,
        )
        if big:
            self.particles.ring(enemy.x, enemy.y, 46, enemy.radius, (120, 340),
                                color=color, life=(0.5, 1.1), size=(3.0, 6.0))
            self.camera.add_trauma(SCREEN_SHAKE_ON_BOSS)
            self.hit_stop = HIT_STOP_ON_BOSS_DEATH
            if self.audio:
                self.audio.play("enemy_die_big")
            self._spawn_boss_escorts(enemy)
            self._set_music("action")
        else:
            self.particles.ring(enemy.x, enemy.y, 8, enemy.radius * 0.7, (30, 120),
                                color=color, life=(0.2, 0.45), size=(1.5, 3.0))
            if self.audio:
                self.audio.play("enemy_die", volume=0.45, pitch=self.rng.uniform(0.9, 1.15))

        if enemy.can_split:
            self._split(enemy)

        self.floaters.add(enemy.x, enemy.y - enemy.radius, f"+{points}",
                          Palette.GOLD if big else Palette.TEXT, size=18 if big else 15)
        self._maybe_drop(enemy)

    def _split(self, parent: Enemy) -> None:
        """Release the children of a splitter, if it may still reproduce."""
        if not parent.can_split:
            return
        arch = parent.archetype
        depth = parent.split_depth + 1
        for _ in range(arch.split_into):
            angle = self.rng.uniform(0, math.tau)
            pos = [
                parent.x + math.cos(angle) * parent.radius * 1.3,
                parent.y + math.sin(angle) * parent.radius * 1.3,
            ]
            radius = parent.radius * arch.split_radius_scale
            resolve_pillars(pos, radius, self.arena.nearby_pillars(*pos, radius))
            self.arena.clamp_position(pos, radius)
            child = Enemy(
                parent.kind, pos[0], pos[1],
                hp_multiplier=arch.split_health_scale * self.wave_state.hp_multiplier,
                speed_multiplier=self.wave_state.speed_multiplier,
                damage_multiplier=self.wave_state.damage_multiplier,
                split_depth=depth,
            )
            child.radius = radius
            child.max_health = child.health = arch.scaled_health(
                arch.split_health_scale * self.wave_state.hp_multiplier
            )
            child.spawn_grace = 0.2
            child.vx = math.cos(angle) * 140.0
            child.vy = math.sin(angle) * 140.0
            self.enemies.append(child)
            self.particles.burst(
                child.x, child.y, 5, (30, 110), life=(0.2, 0.4),
                size=(1.5, 3.0), color=child.color, drag=4.0,
            )

    def _spawn_boss_escorts(self, boss: Enemy) -> None:
        for _ in range(2):
            kind = BOSS_ESCORTS[self.rng.randrange(len(BOSS_ESCORTS))]
            angle = self.rng.uniform(0, math.tau)
            x = boss.x + math.cos(angle) * 120.0
            y = boss.y + math.sin(angle) * 120.0
            pos = [x, y]
            self.arena.clamp_position(pos, 20.0)
            self.enemies.append(
                Enemy(kind, pos[0], pos[1],
                      self.wave_state.hp_multiplier, self.wave_state.speed_multiplier,
                      self.wave_state.damage_multiplier)
            )

    def _maybe_drop(self, enemy: Enemy) -> None:
        if enemy.is_boss:
            for i in range(4):
                self._spawn_pickup("health" if i < 2 else "power", enemy, spread=90.0)
            return
        if self.rng.random() > PICKUP_DROP_CHANCE + 0.03 * self.wave_state.wave:
            return
        if self.rng.random() < 0.22:
            self._spawn_pickup("gem", enemy)
            return
        kind = roll_pickup(self.rng)
        if kind:
            self._spawn_pickup(kind, enemy)

    def _spawn_pickup(self, kind: str, source, spread: float = 40.0) -> None:
        angle = self.rng.uniform(0, math.tau)
        x = source.x + math.cos(angle) * self.rng.uniform(0.0, spread)
        y = source.y + math.sin(angle) * self.rng.uniform(0.0, spread)
        pos = [x, y]
        resolve_pillars(pos, 14.0, self.arena.nearby_pillars(*pos, 14.0))
        self.arena.clamp_position(pos, 14.0)
        self.pickups.append(Pickup(kind, pos[0], pos[1]))

    # -- player damage ---------------------------------------------------
    def _on_player_hit(self, source_x: float, source_y: float) -> None:
        self.damage_flash = 1.0
        self.camera.add_trauma(SCREEN_SHAKE_ON_HIT)
        nx, ny = normalize(self.player.x - source_x, self.player.y - source_y)
        self.player.apply_knockback(nx, ny, 260.0)
        self.particles.burst(
            self.player.x, self.player.y, 16, (80, 260),
            life=(0.2, 0.5), size=(2.0, 4.0),
            color=Palette.PLAYER_DAMAGE, color_end=Palette.RED, drag=3.0,
        )
        self.score.break_combo()
        if self.audio:
            self.audio.play("player_hurt")

    def _damage_player_from_enemy(self, enemy: Enemy) -> None:
        if enemy.spawn_grace > 0.0 or not enemy.alive or not self.player.alive:
            return
        if not self.player.take_damage(enemy.contact_damage):
            return
        nx, ny = normalize(self.player.x - enemy.x, self.player.y - enemy.y)
        self.player.apply_knockback(nx, ny, 300.0)
        self.score.register_damage(enemy.contact_damage)
        self.damage_flash = 1.0
        self.camera.add_trauma(SCREEN_SHAKE_ON_HIT)
        self.particles.burst(
            self.player.x, self.player.y, 14, (70, 240),
            life=(0.2, 0.45), size=(2.0, 4.0),
            color=Palette.RED, color_end=Palette.AMBER, drag=3.0,
        )
        self.score.break_combo()
        if self.audio:
            self.audio.play("player_hurt", volume=0.9, pitch=self.rng.uniform(0.95, 1.05))

    # -- pickups ---------------------------------------------------------
    def _update_pickups(self, dt: float) -> None:
        player = self.player
        for pickup in self.pickups:
            pickup.update(dt, player.x, player.y, player.alive)
        collected = []
        for pickup in self.pickups:
            if player.alive:
                total = pickup.radius + player.radius
                if distance_sq(pickup.x, pickup.y, player.x, player.y) <= total * total:
                    collected.append(pickup)
        for pickup in collected:
            self._collect(pickup)
        self.pickups = [p for p in self.pickups if not p.should_despawn() and p not in collected]

    def _collect(self, pickup: Pickup) -> None:
        result = apply_pickup(pickup, self.player, self)
        if result.score:
            self.score.add(result.score)
        self.score.register_pickup()
        self.floaters.add(
            pickup.x, pickup.y - 10, result.label, result.color, size=17, life=1.1
        )
        self.particles.ring(pickup.x, pickup.y, 12, 4, (40, 150),
                            color=pickup.type.color, life=(0.25, 0.5), size=(1.5, 3.0))
        if self.audio:
            name = {
                "health": "pickup_health",
                "power": "pickup_power",
                "nuke": "pickup_nuke",
            }.get(pickup.type.key, "pickup")
            self.audio.play(name, volume=0.7)

    def trigger_nuke(self, pickup: Pickup) -> None:
        self.nuke_wave_radius = 0.0
        self.nuke_origin = (pickup.x, pickup.y)
        self.camera.add_trauma(0.55)
        if self.audio:
            self.audio.play("nuke_wave")

    def trigger_magnet(self, pickup: Pickup) -> None:
        for other in self.pickups:
            if other is not pickup:
                other.pulled = True

    def _update_nuke(self, dt: float) -> None:
        if self.nuke_origin is None:
            return
        previous = self.nuke_wave_radius
        self.nuke_wave_radius += NUKE_WAVE_SPEED * dt
        if previous <= 0.0 and self.nuke_wave_radius > 0.0:
            self.particles.ring(self.nuke_origin[0], self.nuke_origin[1], 60, 10,
                                (200, 520), color=Palette.RED, life=(0.4, 0.9), size=(3, 7))
        # The radius only grows, so "distance <= radius" catches everything the
        # wave has already reached.  A moving band (previous <= d <= radius)
        # would let a fast enemy slip through the front between two frames.
        for enemy in self.enemies:
            dist = math.hypot(enemy.x - self.nuke_origin[0], enemy.y - self.nuke_origin[1])
            if dist <= self.nuke_wave_radius:
                died = enemy.take_damage(enemy.max_health * 0.6 + 50.0, 420.0, 0.0, -1.0)
                self._impact(enemy.x, enemy.y, enemy.color, 0.0, -1.0)
                if died:
                    self._on_enemy_killed(enemy)
        # Stop once the wave has swept the whole arena.
        if self.nuke_wave_radius >= self._nuke_reach:
            self.nuke_origin = None
            self.nuke_wave_radius = 0.0

    @property
    def _nuke_reach(self) -> float:
        """Farthest the wave must travel to cover the arena from its origin."""
        x, y = self.nuke_origin or self.arena.center
        w, h = self.arena.width, self.arena.height
        return max(
            math.hypot(x, y), math.hypot(x - w, y),
            math.hypot(x, y - h), math.hypot(x - w, y - h),
        )

    # -- feedback / housekeeping ----------------------------------------
    def _update_camera(self, dt: float) -> None:
        self.camera.follow(self.player.x, self.player.y, dt, smoothing=8.0)
        self.camera.clamp_to_world(self.arena.width, self.arena.height)
        self.camera.update(dt, SCREEN_SHAKE_DECAY)
        if self.damage_flash > 0.0:
            self.damage_flash = max(0.0, self.damage_flash - dt * 2.4)

    def _cleanup(self) -> None:
        if any(not e.alive for e in self.enemies):
            self.enemies = [e for e in self.enemies if e.alive]
        # Contact damage.
        for enemy in self.enemies:
            if not self.player.alive:
                break
            total = enemy.radius + self.player.radius
            if distance_sq(enemy.x, enemy.y, self.player.x, self.player.y) <= total * total:
                self._damage_player_from_enemy(enemy)

    def _set_music(self, key: str) -> None:
        if key == self.music_key or self.audio is None:
            return
        self.music_key = key
        self.audio.play_music(key, fade_ms=700)

    def _update_music(self) -> None:
        if self.audio is None:
            return
        # Calm track for the first two waves, then the action loop.
        if self.wave_state.wave <= 1 and self.music_key != "calm":
            self._set_music("calm")
        elif self.wave_state.wave >= 2 and self.music_key == "calm":
            self._set_music("action")

    # ==================================================================
    # Rendering
    # ==================================================================
    def draw(self, target: pygame.Surface, mouse_pos: Tuple[int, int] = (0, 0)) -> None:
        aim = self.camera.screen_to_world(*mouse_pos) if mouse_pos != (0, 0) else None
        self.renderer.draw_background(target, self.time)
        self.renderer.draw_walls(target, self.time)
        if self.nuke_origin is not None:
            self.renderer.draw_nuke_wave(
                target, self.nuke_origin[0], self.nuke_origin[1],
                self.nuke_wave_radius, Palette.RED,
            )
        self.renderer.draw_world(
            target, self.time, self.player, self.enemies,
            self.bullets.bullets, self.pickups, self.particles, aim,
        )
        fx.draw_particles(target, self.particles, self.renderer.to_screen)
        self.floaters.draw(target, self.renderer.to_screen)

        # Screen-space post effects.
        if self.damage_flash > 0.0:
            fx.draw_fullscreen_color(target, Palette.RED, self.damage_flash * 0.16)
        if self.player.health_ratio < LOW_HEALTH_VIGNETTE and self.player.alive:
            pulse = 0.5 + 0.5 * math.sin(self.time * 7.0)
            strength = (1.0 - self.player.health_ratio / LOW_HEALTH_VIGNETTE) * (0.5 + 0.3 * pulse)
            fx.draw_vignette(target, 0.45 + strength * 0.35)
        else:
            fx.draw_vignette(target, 0.4)
        fx.draw_border_pulse(
            target, Palette.RED,
            (0.35 + 0.35 * math.sin(self.time * 7.0)) if self.player.health_ratio < LOW_HEALTH_VIGNETTE else 0.0,
        )

        if aim is not None:
            self.renderer.draw_cursor(target, mouse_pos, self.time)

        self.banner.draw(target)
        self.hud.draw(
            target, self.player, self.score, self.wave_state,
            fps=self._fps, enemies_alive=len(self.enemies),
            enemies=self.enemies, arena=self.arena,
        )

    _fps: float = 0.0

    def set_fps(self, fps: float) -> None:
        self._fps = fps


__all__ = ["GameScene", "InputState"]
