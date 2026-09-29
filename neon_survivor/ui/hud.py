"""In-game HUD: health, weapon, wave, score, combo and minimap."""

from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple

import pygame

from neon_survivor.config import MAX_WEAPON_POWER
from neon_survivor.core.score import ScoreBoard
from neon_survivor.core.world import Arena
from neon_survivor.entities.enemy import Enemy
from neon_survivor.entities.player import Player
from neon_survivor.gfx import draw, fonts
from neon_survivor.ui.theme import Metrics, Palette, health_color, with_alpha

RGB = Tuple[int, int, int]


class Hud:
    """Draws the play HUD.  Stateless apart from cached surfaces."""

    def __init__(self) -> None:
        self.time = 0.0
        self.show_fps = False
        self.fps = 0.0
        self._pulse = 0.0

    def update(self, dt: float) -> None:
        self.time += dt

    # ------------------------------------------------------------------
    def draw(
        self,
        target: pygame.Surface,
        player: Player,
        score: ScoreBoard,
        wave_state,
        fps: float = 0.0,
        enemies_alive: int = 0,
        enemies: Optional[Sequence[Enemy]] = None,
        arena: Optional[Arena] = None,
    ) -> None:
        self.fps = fps
        width, height = target.get_size()

        # --- top bar ------------------------------------------------
        self._draw_top_bar(target, score, wave_state, width, height, enemies_alive)

        # --- bottom-left: health + weapon --------------------------
        self._draw_vitals(target, player, height)

        # --- bottom-right: minimap ----------------------------------
        self._draw_minimap(target, player, width, height, enemies, arena)

        # --- combo pop ----------------------------------------------
        self._draw_combo(target, score, width, height)

        if self.show_fps:
            draw.text(
                target, f"{fps:5.1f} FPS", (width - 12, height - 12),
                fonts.SIZE_TINY, Palette.TEXT_DIM, align="right", valign="bottom",
            )

    # ------------------------------------------------------------------
    def _draw_top_bar(
        self,
        target: pygame.Surface,
        score: ScoreBoard,
        wave_state,
        width: int,
        height: int,
        enemies_alive: int,
    ) -> None:
        bar_h = 54
        overlay = pygame.Surface((width, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (4, 6, 18, 205), overlay.get_rect())
        target.blit(overlay, (0, 0))
        pygame.draw.line(target, with_alpha(Palette.PURPLE, 0.7), (0, bar_h), (width, bar_h), 2)

        # Score.
        draw.text(
            target, draw.format_number(score.score), (18, 8),
            fonts.SIZE_LARGE, Palette.TEXT, valign="top",
        )
        draw.text(
            target, f"SCORE   x{score.combo_multiplier:.2f}", (20, 38),
            fonts.SIZE_TINY, Palette.TEXT_DIM, valign="top",
        )

        # Wave (centre).
        wave = wave_state.wave if wave_state else score.wave
        center = width // 2
        if wave_state and wave_state.is_boss_wave:
            pulse = 0.5 + 0.5 * math.sin(self.time * 5.0)
            color = draw.mix_color(Palette.RED, Palette.MAGENTA, pulse)
        else:
            color = Palette.CYAN
        draw.text(
            target, f"WAVE {wave}", (center, 6), fonts.SIZE_MEDIUM, color,
            align="center", valign="top",
        )
        if wave_state is not None:
            remaining = wave_state.time_to_next_wave
            ratio = 1.0 - (remaining / max(0.001, wave_state.wave_elapsed + remaining))
            bar = pygame.Rect(center - 110, 38, 220, 5)
            draw.gradient_bar(
                target, bar, ratio,
                (Palette.CYAN, Palette.PURPLE, Palette.MAGENTA),
                background=Palette.PANEL, border=None, radius=2,
            )
            draw.text(
                target, f"{int(remaining)}s", (center + 124, 32),
                fonts.SIZE_TINY, Palette.TEXT_DIM, align="left", valign="center",
            )

        # Right: time, kills, enemies.
        draw.text(
            target, score.formatted_time, (width - 18, 8),
            fonts.SIZE_LARGE, Palette.TEXT, align="right", valign="top",
        )
        draw.text(
            target, f"KILLS {score.kills}   ALIVE {enemies_alive}", (width - 20, 38),
            fonts.SIZE_TINY, Palette.TEXT_DIM, align="right", valign="top",
        )

    # ------------------------------------------------------------------
    def _draw_vitals(self, target: pygame.Surface, player: Player, height: int) -> None:
        x = 20
        y = height - 74
        panel_w = 268

        draw.rounded_panel(
            target, pygame.Rect(x, y, panel_w, 56), Palette.PANEL,
            alpha=205, border=Palette.GRID, border_width=1, radius=Metrics.RADIUS,
        )

        # Health bar.
        bar = pygame.Rect(x + 12, y + 10, panel_w - 24, 18)
        ratio = player.health_ratio
        col = health_color(ratio)
        draw.rounded_panel(
            target, bar, (12, 14, 30), alpha=255, border=None, radius=6
        )
        if ratio > 0:
            fill = bar.copy()
            fill.width = max(2, int(bar.width * ratio))
            draw.gradient_bar(target, fill, 1.0, (col, draw.mix_color(col, (255, 255, 255), 0.4)))
        if ratio < 0.35:
            pulse = 0.5 + 0.5 * math.sin(self.time * 8.0)
            pygame.draw.rect(
                target, with_alpha(Palette.RED, 0.35 + 0.4 * pulse), bar, width=2, border_radius=6
            )
        draw.text_outlined(
            target, f"{int(player.health)} / {int(player.max_health)}",
            (bar.centerx, bar.centery), fonts.SIZE_TINY, (255, 255, 255),
            border_color=Palette.VOID, align="center", valign="center", border_width=2,
        )

        # Weapon level pips.
        label_y = y + 38
        draw.text(target, "PWR", (x + 14, label_y), fonts.SIZE_TINY, Palette.TEXT_DIM, valign="center")
        pip_x = x + 46
        for i in range(MAX_WEAPON_POWER):
            filled = i < player.weapon_power
            center = (pip_x + i * 18, label_y)
            color = Palette.CYAN if filled else Palette.GRID
            if filled and i >= player.weapon_power - 1:
                color = draw.mix_color(Palette.CYAN, (255, 255, 255), 0.3)
            pygame.draw.circle(target, color, center, 6 if filled else 4)
        if player.speed_boost > 0.0:
            draw.text(
                target, "OVERDRIVE", (x + panel_w - 12, label_y), fonts.SIZE_TINY,
                Palette.AMBER, align="right", valign="center",
            )
        elif player.shield > 0.0:
            draw.text(
                target, f"SHIELD {int(player.shield)}", (x + panel_w - 12, label_y),
                fonts.SIZE_TINY, Palette.PURPLE, align="right", valign="center",
            )

    # ------------------------------------------------------------------
    def _draw_minimap(
        self,
        target: pygame.Surface,
        player: Player,
        width: int,
        height: int,
        enemies: Optional[Sequence[Enemy]] = None,
        arena: Optional[Arena] = None,
    ) -> None:
        size = 132
        margin = 20
        rect = pygame.Rect(width - size - margin, height - size - margin, size, size)
        draw.rounded_panel(
            target, rect, Palette.PANEL, alpha=190, border=Palette.GRID,
            border_width=1, radius=8,
        )
        inner = rect.inflate(-12, -12)
        world_w = arena.width if arena else 4800.0
        world_h = arena.height if arena else 4800.0

        def to_map(x: float, y: float) -> Tuple[float, float]:
            return (inner.left + x / world_w * inner.width, inner.top + y / world_h * inner.height)

        # Enemy blips first so the player marker stays on top.
        if enemies:
            for enemy in enemies:
                mx, my = to_map(enemy.x, enemy.y)
                if not inner.collidepoint(int(mx), int(my)):
                    continue
                blip = enemy.color if enemy.is_boss else draw.scale_color(enemy.color, 0.8)
                radius = 3 if not enemy.is_boss else 5
                if enemy.is_boss:
                    draw.draw_glow(target, (mx, my), 10, blip, 0.9)
                pygame.draw.circle(target, blip, (int(mx), int(my)), radius)

        px, py = to_map(player.x, player.y)
        # Direction wedge.
        wedge = [
            (px, py),
            (px + math.cos(player.facing - 0.45) * 10, py + math.sin(player.facing - 0.45) * 10),
            (px + math.cos(player.facing + 0.45) * 10, py + math.sin(player.facing + 0.45) * 10),
        ]
        pygame.draw.polygon(target, with_alpha(Palette.CYAN, 0.5), [(int(a), int(b)) for a, b in wedge])
        pygame.draw.circle(target, Palette.VOID, (int(px), int(py)), 5)
        draw.draw_glow(target, (px, py), 12, Palette.CYAN, 0.95)
        pygame.draw.circle(target, (255, 255, 255), (int(px), int(py)), 3)
        draw.text(
            target, "MAP", (rect.centerx, rect.top - 14), fonts.SIZE_TINY,
            Palette.TEXT_FAINT, align="center", valign="center",
        )

    # ------------------------------------------------------------------
    def _draw_combo(
        self, target: pygame.Surface, score: ScoreBoard, width: int, height: int
    ) -> None:
        if score.combo < 2:
            return
        t = score.combo_ratio
        x = width // 2
        y = height - 96
        pulse = 0.5 + 0.5 * math.sin(self.time * 9.0)
        color = draw.mix_color(Palette.AMBER, Palette.MAGENTA, pulse)
        draw.text(
            target, f"COMBO x{score.combo}", (x, y), fonts.SIZE_BODY, color,
            align="center", valign="center",
        )
        bar = pygame.Rect(x - 70, y + 14, 140, 4)
        draw.gradient_bar(
            target, bar, t, (Palette.MAGENTA, Palette.AMBER), background=Palette.PANEL, radius=2
        )


__all__ = ["Hud"]
