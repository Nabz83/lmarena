"""World renderer: arena, entities, pickups and in-world effects.

The renderer never mutates game state — it only reads it.  World coordinates
are converted to screen space through the camera, and anything outside the
visible rect is skipped, which keeps the cost proportional to what is on
screen rather than to the number of live entities.
"""

from __future__ import annotations

import math
import random
from typing import List, Optional, Sequence, Tuple

import pygame

from neon_survivor.core.camera import Camera
from neon_survivor.core.mathutils import clamp
from neon_survivor.core.particles import ParticleSystem
from neon_survivor.core.world import Arena
from neon_survivor.entities.enemy import Enemy
from neon_survivor.entities.pickups import Pickup
from neon_survivor.entities.player import Player
from neon_survivor.entities.projectiles import Bullet
from neon_survivor.gfx import draw, shapes
from neon_survivor.ui.theme import Palette, with_alpha

RGB = Tuple[int, int, int]
CULL_MARGIN = 140.0


class WorldRenderer:
    """Draws the playfield."""

    def __init__(self, arena: Arena, camera: Camera) -> None:
        self.arena = arena
        self.camera = camera
        self._floor_pattern: Optional[pygame.Surface] = None
        self._starfield: List[Tuple[float, float, float]] = []
        self._rng = random.Random(4242)
        self._build_starfield()

    # -- setup -----------------------------------------------------------
    def _build_starfield(self) -> None:
        """A sparse set of background specks so the floor is not flat."""
        count = 420
        for _ in range(count):
            x = self._rng.uniform(0, self.arena.width)
            y = self._rng.uniform(0, self.arena.height)
            brightness = self._rng.uniform(0.18, 0.55)
            self._starfield.append((x, y, brightness))

    def _ensure_floor_pattern(self) -> pygame.Surface:
        """A seamless tile for the arena grid."""
        if self._floor_pattern is not None:
            return self._floor_pattern
        size = max(16, self.arena.grid_size)
        tile = pygame.Surface((size, size), pygame.SRCALPHA)
        tile.fill((Palette.NIGHT[0], Palette.NIGHT[1], Palette.NIGHT[2], 255))
        pygame.draw.line(tile, (*Palette.GRID, 150), (0, 0), (size, 0), 1)
        pygame.draw.line(tile, (*Palette.GRID, 150), (0, 0), (0, size), 1)
        pygame.draw.circle(tile, (*Palette.GRID, 190), (0, 0), 2)
        self._floor_pattern = tile
        return tile

    # -- transforms ------------------------------------------------------
    def to_screen(self, x: float, y: float) -> Tuple[float, float]:
        return self.camera.world_to_screen(x, y)

    def _visible(self, x: float, y: float, radius: float = 0.0) -> bool:
        return self.camera.is_visible(x, y, radius + CULL_MARGIN)

    # -- background ------------------------------------------------------
    def draw_background(self, target: pygame.Surface, time: float) -> None:
        target.fill(Palette.VOID)
        tile = self._ensure_floor_pattern()

        # The grid is drawn in screen space, offset by the camera.
        width, height = target.get_size()
        ox, oy = self.camera.x, self.camera.y
        start_x = int(-(ox % self.arena.grid_size))
        start_y = int(-(oy % self.arena.grid_size))
        for gy in range(start_y, height + self.arena.grid_size, self.arena.grid_size):
            for gx in range(start_x, width + self.arena.grid_size, self.arena.grid_size):
                target.blit(tile, (gx, gy))

        # Specks.
        for x, y, brightness in self._starfield:
            if not self._visible(x, y, 4):
                continue
            sx, sy = self.to_screen(x, y)
            shade = int(40 + brightness * 90)
            pygame.draw.circle(target, (shade, shade + 8, shade + 30), (int(sx), int(sy)), 1)

    def draw_walls(self, target: pygame.Surface, time: float) -> None:
        arena = self.arena
        w = arena.wall
        pulse = 0.5 + 0.5 * math.sin(time * 1.6)
        edge = draw.mix_color(Palette.WALL_EDGE, Palette.MAGENTA, pulse * 0.4)

        x0, y0 = self.to_screen(0, 0)
        x1, y1 = self.to_screen(arena.width, arena.height)
        rect = pygame.Rect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))
        if (
            rect.right < 0
            or rect.bottom < 0
            or rect.left > target.get_width()
            or rect.top > target.get_height()
        ):
            return

        # Solid wall band with an inner neon frame.
        pygame.draw.rect(target, Palette.WALL, rect, width=max(1, int(w)))
        inner = rect.inflate(-w * 2, -w * 2)
        if inner.width > 4 and inner.height > 4:
            pygame.draw.rect(target, draw.scale_color(edge, 0.55), inner, width=3)
            # Hazard ticks along the frame.
            step = 54
            for x in range(inner.left, inner.right, step):
                pygame.draw.line(
                    target, draw.scale_color(edge, 0.8), (x, inner.top), (x, inner.top + 12), 2
                )
                pygame.draw.line(
                    target,
                    draw.scale_color(edge, 0.8),
                    (x, inner.bottom - 12),
                    (x, inner.bottom),
                    2,
                )
            for y in range(inner.top, inner.bottom, step):
                pygame.draw.line(
                    target, draw.scale_color(edge, 0.8), (inner.left, y), (inner.left + 12, y), 2
                )
                pygame.draw.line(
                    target,
                    draw.scale_color(edge, 0.8),
                    (inner.right - 12, y),
                    (inner.right, y),
                    2,
                )
        pygame.draw.rect(target, edge, rect, width=3)

    def draw_pillars(self, target: pygame.Surface, time: float) -> None:
        for index, (px, py, pr) in enumerate(self.arena.pillars):
            if not self._visible(px, py, pr):
                continue
            sx, sy = self.to_screen(px, py)
            variant = self.arena.pillar_variants[index] if index < len(self.arena.pillar_variants) else 0
            draw.draw_glow(target, (sx, sy), pr * 1.2, Palette.PURPLE, 0.4)
            pygame.draw.circle(target, Palette.PANEL_LIGHT, (int(sx), int(sy)), int(pr))
            pygame.draw.circle(target, Palette.WALL, (int(sx), int(sy)), int(pr), 2)
            pygame.draw.circle(
                target, draw.mix_color(Palette.PURPLE, Palette.CYAN, 0.4), (int(sx), int(sy)), int(pr), 4
            )
            # Inner detail varies per pillar for visual interest.
            if variant == 0:
                pygame.draw.circle(target, Palette.PANEL, (int(sx), int(sy)), int(pr * 0.55), 2)
            elif variant == 1:
                angle = time * 0.4 + index
                pts = shapes.rotate_points(
                    shapes.regular_polygon(6, pr * 0.62, 0.0), angle
                )
                pygame.draw.polygon(
                    target, Palette.PANEL, [(int(sx + a), int(sy + b)) for a, b in pts], 2
                )
            else:
                pygame.draw.line(
                    target, Palette.PANEL, (int(sx - pr * 0.6), int(sy)), (int(sx + pr * 0.6), int(sy)), 2
                )
                pygame.draw.line(
                    target, Palette.PANEL, (int(sx), int(sy - pr * 0.6)), (int(sx), int(sy + pr * 0.6)), 2
                )

    # -- pickups ---------------------------------------------------------
    def draw_pickups(self, target: pygame.Surface, pickups: Sequence[Pickup], time: float) -> None:
        for pickup in pickups:
            if not self._visible(pickup.x, pickup.y, pickup.radius):
                continue
            # Blink out when about to expire.
            if pickup.blinking and int(pickup.life * 9) % 2 == 0:
                continue
            sx, sy = self.to_screen(pickup.x, pickup.y)
            bob = pickup.bob
            ptype = pickup.type
            pulse = 1.0 + 0.12 * math.sin(pickup.age * 4.0)
            radius = pickup.radius * pulse

            draw.draw_glow(target, (sx, sy + bob), radius * 2.2, ptype.color, 0.8)
            # Hexagonal capsule.
            ring_pts = shapes.rotate_points(
                shapes.regular_polygon(6, radius, time * 1.2), time * 0.9
            )
            pts = [(int(sx + a), int(sy + bob + b)) for a, b in ring_pts]
            pygame.draw.polygon(target, draw.scale_color(ptype.color, 0.35), pts)
            pygame.draw.polygon(target, ptype.color, pts, 2)
            # Icon glyph.
            glyph = radius * 0.44
            pygame.draw.line(
                target, ptype.accent, (int(sx - glyph), int(sy + bob)), (int(sx + glyph), int(sy + bob)), 3
            )
            pygame.draw.line(
                target, ptype.accent, (int(sx), int(sy + bob - glyph)), (int(sx), int(sy + bob + glyph)), 3
            )

    # -- bullets ---------------------------------------------------------
    def draw_bullets(self, target: pygame.Surface, bullets: Sequence[Bullet]) -> None:
        for bullet in bullets:
            if not self._visible(bullet.x, bullet.y, bullet.radius):
                continue
            sx, sy = self.to_screen(bullet.x, bullet.y)
            color = bullet.color
            # Motion trail.
            if len(bullet.trail) > 1:
                pts = [self.to_screen(px, py) for px, py in bullet.trail]
                draw.polyline(target, pts, draw.scale_color(color, 0.45), max(2, int(bullet.radius)))
            draw.draw_glow(target, (sx, sy), bullet.radius * 3.4, color, 0.95)
            pygame.draw.circle(target, color, (int(sx), int(sy)), int(bullet.radius))
            pygame.draw.circle(target, bullet.core, (int(sx), int(sy)), max(1, int(bullet.radius * 0.45)))

    # -- player ----------------------------------------------------------
    def draw_player(
        self,
        target: pygame.Surface,
        player: Player,
        time: float,
        particles: ParticleSystem,
    ) -> None:
        if not player.alive and player.health <= 0.0:
            return
        # Blink while invulnerable.
        if player.is_invulnerable and int(player.invuln_timer * 22) % 2 == 0:
            return

        sx, sy = self.to_screen(player.x, player.y)
        angle = player.facing
        radius = player.radius

        boost = player.speed_boost > 0.0
        base_color = Palette.PLAYER if not player.hit_flash else Palette.PLAYER_DAMAGE
        if player.hit_flash > 0.0:
            base_color = draw.mix_color(Palette.PLAYER, Palette.PLAYER_DAMAGE, player.hit_flash)
        if boost:
            base_color = draw.mix_color(base_color, Palette.AMBER, 0.45)

        draw.draw_glow(target, (sx, sy), radius * 3.0, base_color, 1.0)

        # Ground ring: guarantees the player is always locatable in a crowd.
        draw.ring(
            target,
            (sx, sy),
            radius + 7.0,
            with_alpha(base_color, 0.55 + 0.18 * math.sin(time * 2.5)),
            0,
            360,
            2,
        )

        # Engine trail.
        trail_angle = angle + math.pi
        for i in range(3):
            offset = radius * (0.9 + i * 0.45)
            flicker = 0.7 + 0.3 * math.sin(time * 24.0 + i)
            tx = sx + math.cos(trail_angle) * offset
            ty = sy + math.sin(trail_angle) * offset
            draw.draw_glow(
                target,
                (tx, ty),
                radius * (0.75 - i * 0.16) * flicker,
                Palette.CYAN,
                0.75 - i * 0.18,
            )

        # Hull.
        body = shapes.rotate_points(shapes.player_shape(radius), angle)
        pts = [(int(sx + a), int(sy + b)) for a, b in body]
        recoil = player.recoil * 3.0
        ox = -math.cos(angle) * recoil
        oy = -math.sin(angle) * recoil
        pts = [(int(px + ox), int(py + oy)) for px, py in pts]
        pygame.draw.polygon(target, draw.scale_color(base_color, 0.85), pts)
        pygame.draw.polygon(target, base_color, pts, 3)
        pygame.draw.polygon(target, Palette.PLAYER_CORE, pts, 1)

        # Weapon barrel, pointing at the cursor.
        muzzle = radius * 1.25
        mx = sx + math.cos(angle) * muzzle
        my = sy + math.sin(angle) * muzzle
        pygame.draw.line(
            target,
            Palette.PLAYER_CORE,
            (int(sx + math.cos(angle) * radius * 0.4), int(sy + math.sin(angle) * radius * 0.4)),
            (int(mx), int(my)),
            4,
        )
        if player.can_fire:
            draw.draw_glow(target, (mx, my), 11.0, Palette.BULLET, 0.85)

        # Core.
        draw.draw_glow(target, (sx, sy), radius * 1.1, Palette.PLAYER_CORE, 0.9)
        pygame.draw.circle(target, Palette.PLAYER_CORE, (int(sx), int(sy)), max(3, int(radius * 0.34)))

        # Shield bubble.
        if player.shield > 0.0:
            shield_r = radius + 9.0 + 2.0 * math.sin(time * 5.0)
            draw.ring(target, (sx, sy), shield_r, with_alpha(Palette.PURPLE, 0.75), 0, 360, 2)

        # Overdrive aura.
        if boost:
            aura = radius + 16.0 + 4.0 * math.sin(time * 9.0)
            draw.ring(target, (sx, sy), aura, with_alpha(Palette.AMBER, 0.6), 0, 360, 2)

    # -- enemies ---------------------------------------------------------
    def draw_enemy(self, target: pygame.Surface, enemy: Enemy, time: float) -> None:
        if not self._visible(enemy.x, enemy.y, enemy.radius):
            return
        # Spawn-in blink.
        if enemy.spawn_grace > 0.0 and int(enemy.spawn_grace * 20) % 2 == 0:
            return

        sx, sy = self.to_screen(enemy.x, enemy.y)
        radius = enemy.radius
        color = enemy.color
        if enemy.hit_flash > 0.0:
            color = draw.mix_color(color, Palette.TEXT, enemy.hit_flash * 0.85)

        arch = enemy.archetype

        # Telegraph the charger before it dashes.
        if enemy.behavior == "charger" and enemy.state == "windup":
            progress = 1.0 - clamp(enemy.state_timer / max(0.01, arch.charge_windup), 0.0, 1.0)
            draw.draw_glow(target, (sx, sy), radius * (2.0 + progress * 2.2), Palette.RED, 0.35 + progress * 0.5)
            draw.ring(
                target,
                (sx, sy),
                radius * (2.6 - progress * 1.0),
                with_alpha(Palette.RED, 0.35 + progress * 0.6),
                0,
                360,
                3,
            )

        glow_intensity = 0.7
        if enemy.is_boss:
            glow_intensity = 0.85 + 0.12 * math.sin(time * 3.0)
        draw.draw_glow(target, (sx, sy), radius * (1.35 + arch.glow * 0.05), color, glow_intensity)

        # Dash streak.
        if enemy.behavior == "charger" and enemy.state == "dash":
            tail = 5
            for i in range(1, tail):
                tx = sx - enemy.dash_dir[0] * radius * i * 0.8
                ty = sy - enemy.dash_dir[1] * radius * i * 0.8
                pygame.draw.circle(
                    target,
                    draw.scale_color(color, 0.5 - i * 0.08),
                    (int(tx), int(ty)),
                    max(1, int(radius * (1.0 - i * 0.16))),
                )

        # Body.
        angle = enemy.face_angle if enemy.is_boss or enemy.behavior != "chase" else math.atan2(
            enemy.vy + enemy.ky, enemy.vx + enemy.kx
        )
        if not (enemy.vx or enemy.vy or enemy.kx or enemy.ky):
            angle = enemy.face_angle
        body = shapes.rotate_points(shapes.enemy_shape(enemy.kind, radius), angle)
        pts = [(int(sx + a), int(sy + b)) for a, b in body]
        pygame.draw.polygon(target, draw.scale_color(color, 0.40), pts)
        pygame.draw.polygon(target, color, pts, 3 if not enemy.is_boss else 4)

        # Inner marking, per behaviour, so types are readable in a crowd.
        inner = radius * 0.46
        if enemy.behavior == "shooter":
            pts2 = [(int(sx + a), int(sy + b)) for a, b in shapes.rotate_points(shapes.hexagon(inner), -angle + time)]
            pygame.draw.polygon(target, enemy.accent, pts2, 2)
        elif enemy.behavior == "weaver":
            pts2 = [(int(sx + a), int(sy + b)) for a, b in shapes.rotate_points(shapes.diamond(inner, 1.2), time * 1.5)]
            pygame.draw.polygon(target, enemy.accent, pts2, 2)
        elif enemy.behavior == "charger":
            pygame.draw.circle(target, enemy.accent, (int(sx), int(sy)), max(1, int(inner * 0.42)))
        elif enemy.kind == "splitter":
            for k in (-1, 0, 1):
                kx = sx + math.cos(time * 2.0 + k * 2.09) * inner * 0.62
                ky = sy + math.sin(time * 2.0 + k * 2.09) * inner * 0.62
                pygame.draw.circle(target, enemy.accent, (int(kx), int(ky)), max(1, int(inner * 0.28)))
        elif enemy.is_boss:
            # Rotating armour ring + core.
            draw.ring(target, (sx, sy), radius * 0.78, with_alpha(enemy.accent, 0.7), 0, 360, 3)
            for i in range(6):
                a = time * 1.1 + i * math.tau / 6
                px = sx + math.cos(a) * radius * 0.78
                py = sy + math.sin(a) * radius * 0.78
                pygame.draw.circle(target, enemy.accent, (int(px), int(py)), max(2, int(radius * 0.10)))
            pygame.draw.circle(target, enemy.accent, (int(sx), int(sy)), max(2, int(radius * 0.20)))
        else:
            pygame.draw.circle(target, enemy.accent, (int(sx), int(sy)), max(1, int(inner * 0.45)))

        # Elite marker.
        if enemy.elite:
            draw.ring(target, (sx, sy), radius * 1.32, with_alpha(Palette.GOLD, 0.85), 0, 360, 2)

        # Health bar for the tough ones.
        if enemy.max_health > 70 and enemy.health_ratio < 1.0:
            self._draw_mini_health_bar(target, sx, sy - radius - 12, radius * 1.6, enemy.health_ratio, color)

    def _draw_mini_health_bar(
        self, target: pygame.Surface, cx: float, cy: float, width: float, ratio: float, color: RGB
    ) -> None:
        rect = pygame.Rect(0, 0, int(width), 4)
        rect.midtop = (int(cx), int(cy))
        pygame.draw.rect(target, Palette.VOID, rect.inflate(2, 2), border_radius=2)
        filled = rect.copy()
        filled.width = max(1, int(rect.width * clamp(ratio, 0.0, 1.0)))
        bar_color = Palette.RED if ratio < 0.35 else draw.mix_color(Palette.AMBER, color, ratio)
        pygame.draw.rect(target, bar_color, filled, border_radius=2)

    # -- composition -----------------------------------------------------
    def draw_world(
        self,
        target: pygame.Surface,
        time: float,
        player: Player,
        enemies: Sequence[Enemy],
        bullets: Sequence[Bullet],
        pickups: Sequence[Pickup],
        particles: ParticleSystem,
        aim: Optional[Tuple[float, float]] = None,
    ) -> None:
        self.draw_pickups(target, pickups, time)
        self.draw_pillars(target, time)
        if aim is not None and player.alive:
            self.draw_aim_guide(target, player, aim[0], aim[1], time, enemies)
        self.draw_bullets(target, bullets)
        for enemy in enemies:
            self.draw_enemy(target, enemy, time)
        self.draw_player(target, player, time, particles)

    # -- aim helpers -----------------------------------------------------
    def draw_aim_guide(
        self,
        target: pygame.Surface,
        player: Player,
        aim_x: float,
        aim_y: float,
        time: float,
        enemies: Sequence[Enemy] = (),
        max_range: float = 700.0,
    ) -> None:
        """A dotted line from the player towards the aim point.

        It stops at the first enemy it meets, which doubles as a subtle
        range readout and makes the mouse-aim feel precise.
        """
        dx, dy = aim_x - player.x, aim_y - player.y
        length = math.hypot(dx, dy)
        if length < 1e-3:
            return
        ux, uy = dx / length, dy / length

        stop = min(length, max_range)
        # Clip against the closest enemy along the ray.
        closest = stop
        for enemy in enemies:
            ex, ey = enemy.x - player.x, enemy.y - player.y
            proj = ex * ux + ey * uy
            if proj <= 0.0 or proj >= closest:
                continue
            perp_sq = ex * ex + ey * ey - proj * proj
            if perp_sq <= enemy.radius * enemy.radius:
                closest = proj

        step = 16.0
        count = int(closest / step)
        # Animate the dashes scrolling outwards.
        offset = (time * 90.0) % (step * 2.0)
        for i in range(count):
            dist = i * step * 2.0 + offset
            if dist > closest:
                break
            fade = 1.0 - (dist / max(1.0, closest)) * 0.75
            sx = player.x + ux * dist
            sy = player.y + uy * dist
            sxs, sys_ = self.to_screen(sx, sy)
            if not self._visible(sx, sy, 8):
                continue
            pygame.draw.circle(
                target,
                with_alpha(Palette.CYAN, 0.10 + 0.26 * fade),
                (int(sxs), int(sys_)),
                2,
            )

    def draw_cursor(self, target: pygame.Surface, mouse_pos: Tuple[int, int], time: float) -> None:
        """A crosshair on the aim direction."""
        mx, my = mouse_pos
        pulse = 0.5 + 0.5 * math.sin(time * 4.0)
        radius = 13 + pulse * 2
        color = Palette.CYAN
        draw.ring(target, (mx, my), radius, with_alpha(color, 0.75), 0, 360, 2)
        for i in range(4):
            angle = i * math.tau / 4 + math.pi / 4
            x0 = mx + math.cos(angle) * (radius - 5)
            y0 = my + math.sin(angle) * (radius - 5)
            x1 = mx + math.cos(angle) * (radius + 5)
            y1 = my + math.sin(angle) * (radius + 5)
            pygame.draw.line(target, color, (int(x0), int(y0)), (int(x1), int(y1)), 2)
        pygame.draw.circle(target, Palette.PLAYER_CORE, (mx, my), 2)

    def draw_nuke_wave(
        self, target: pygame.Surface, cx: float, cy: float, radius: float, color: RGB
    ) -> None:
        """An expanding shock ring — drawn as a ring, not a filled disc.

        The wave can grow to the arena diagonal, so it must never build a
        surface proportional to its own radius.
        """
        if radius <= 1.0:
            return
        sx, sy = self.to_screen(cx, cy)
        # Keep the halo within a sane surface size and stretch it instead.
        halo = min(radius, 260.0)
        stretch = halo / max(1.0, min(radius, 260.0))
        draw.draw_glow(
            target, (sx, sy), min(220.0, max(24.0, radius * 0.18)),
            color, 0.85, scale=max(1.0, stretch),
        )
        pygame.draw.circle(
            target, with_alpha(color, 0.9), (int(sx), int(sy)), int(radius), 6
        )
        pygame.draw.circle(
            target, with_alpha(Palette.PLAYER_CORE, 0.75), (int(sx), int(sy)), int(radius * 0.94), 2
        )


__all__ = ["WorldRenderer", "CULL_MARGIN"]
