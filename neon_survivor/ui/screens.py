"""Full-screen scenes: title, options, pause and game over.

Each screen is a small class with the same three hooks — ``handle_event``,
``update`` and ``draw`` — so :class:`neon_survivor.app.App` can swap them
without knowing what they do.
"""

from __future__ import annotations

import math
import random
from typing import List, Optional, Tuple

import pygame

from neon_survivor.config import GAME_TITLE, VERSION
from neon_survivor.core.score import ScoreBoard
from neon_survivor.gfx import draw, fonts, fx
from neon_survivor.settings import Settings
from neon_survivor.ui.theme import Metrics, Palette, with_alpha
from neon_survivor.ui.widgets import Menu, MenuItem, draw_logo

RGB = Tuple[int, int, int]


class Backdrop:
    """Animated star field + grid used behind every menu."""

    def __init__(self) -> None:
        self.time = 0.0
        self.stars: List[Tuple[float, float, float, float]] = []
        self._rng = random.Random(9001)
        for _ in range(160):
            self.stars.append(
                (
                    self._rng.random(),           # x 0..1
                    self._rng.random(),           # y 0..1
                    self._rng.uniform(0.4, 2.2),   # radius
                    self._rng.uniform(0.1, 1.0),   # brightness
                )
            )

    def update(self, dt: float) -> None:
        self.time += dt

    def draw(self, target: pygame.Surface) -> None:
        width, height = target.get_size()
        target.fill(Palette.VOID)

        # Perspective grid.
        horizon = height * 0.74
        for i in range(14):
            t = i / 13.0
            y = horizon + (height - horizon) * (t ** 2.2)
            if y >= height:
                break
            alpha = int(70 * (1.0 - t * 0.6))
            pygame.draw.line(target, (*Palette.GRID, alpha), (0, int(y)), (width, int(y)), 1)
        scroll = (self.time * 26.0) % 90
        for i in range(-2, 20):
            x = int(i * 90 - scroll)
            pygame.draw.line(
                target, (*Palette.GRID, 40), (x, int(horizon)), (width // 2, height), 1
            )

        # Sky glow above the horizon.
        for i in range(40):
            t = i / 40.0
            y = int(horizon * (1.0 - t))
            pygame.draw.line(
                target,
                (Palette.PURPLE[0] // 3, Palette.PURPLE[1] // 4, Palette.PURPLE[2] // 2, int(28 * (1.0 - t))),
                (0, y), (width, y), 1,
            )

        # Retro sun, kept dim so the menu stays readable on top of it.
        sun_r = 96
        sun_cx, sun_cy = width // 2, int(horizon - sun_r * 0.34)
        for i in range(9, 0, -1):
            t = i / 9.0
            color = draw.mix_color(
                draw.mix_color(Palette.MAGENTA, Palette.AMBER, 1.0 - t), Palette.VOID, 0.55
            )
            pygame.draw.circle(target, color, (sun_cx, sun_cy), int(sun_r * t))
        for i in range(6):
            y = sun_cy + int(i * 11) - 14
            pygame.draw.line(target, Palette.VOID, (0, y), (width, y), 2 + i // 2)

        # Stars.
        for x, y, r, b in self.stars:
            sy = int((y * 0.74 + self.time * 0.004 * b) % 0.74 * height)
            shade = int(60 + 150 * b)
            pygame.draw.circle(target, (shade, shade, min(255, shade + 30)), (int(x * width), sy), max(1, int(r)))


# ==========================================================================
# Title screen
# ==========================================================================
class TitleScreen:
    """Main menu: play, options, quit."""

    def __init__(self, settings: Settings, on_start, on_options, on_quit) -> None:
        self.settings = settings
        self.on_start = on_start
        self.on_options = on_options
        self.on_quit = on_quit
        self.backdrop = Backdrop()
        self.time = 0.0
        self.best = settings.high_score

        self.menu = Menu(
            [
                MenuItem("JOUER", action="play", hint="Entrée / clic"),
                MenuItem("OPTIONS", action="options", hint="Volume, plein écran"),
                MenuItem("QUITTER", action="quit", hint="Échap"),
            ],
            on_activate=self._activate,
        )

    def _activate(self, item: MenuItem) -> None:
        if item.action == "play":
            self.on_start()
        elif item.action == "options":
            self.on_options()
        elif item.action == "quit":
            self.on_quit()

    # -- lifecycle -------------------------------------------------------
    def handle_event(self, event: pygame.event.Event, audio=None) -> Optional[str]:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w, pygame.K_z):
                self.menu.move_up()
                if audio:
                    audio.play("ui_move")
            elif event.key in (pygame.K_DOWN, pygame.K_s, pygame.K_RIGHT):
                self.menu.move_down()
                if audio:
                    audio.play("ui_move")
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                if audio:
                    audio.play("ui_select")
                self.menu.activate()
            elif event.key == pygame.K_ESCAPE:
                if audio:
                    audio.play("ui_back")
                return "quit"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            item = self.menu.handle_event(event)
            if item is not None:
                if audio:
                    audio.play("ui_select")
                self.menu.activate()
        else:
            self.menu.handle_event(event)
        return None

    def update(self, dt: float) -> None:
        self.time += dt
        self.backdrop.update(dt)

    def draw(self, target: pygame.Surface) -> None:
        width, height = target.get_size()
        self.backdrop.draw(target)

        # Scrim behind the interactive area keeps the text legible over the
        # animated backdrop whatever the resolution.
        scrim = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(scrim, (4, 6, 18, 150), scrim.get_rect())
        target.blit(scrim, (0, 0))
        fx.draw_vignette(target, 0.6)

        draw_logo(target, width // 2, int(height * 0.24), self.time)
        draw.text(
            target, "SURVIVE  THE  SWARM", (width // 2, int(height * 0.34)),
            fonts.SIZE_BODY, Palette.CYAN, align="center", valign="center",
        )

        self.menu.draw(target, width // 2, int(height * 0.56), 380, row_height=48)

        # Best score + version.
        draw.text(
            target, f"MEILLEUR SCORE   {draw.format_number(self.best)}",
            (width // 2, height - 58), fonts.SIZE_BODY, Palette.GOLD, align="center", valign="center",
        )
        draw.text(
            target, f"{GAME_TITLE}  v{VERSION}  —  ZQSD / WASD + flèches · souris pour viser",
            (width // 2, height - 28), fonts.SIZE_TINY, Palette.TEXT_FAINT,
            align="center", valign="center",
        )


# ==========================================================================
# Options
# ==========================================================================
class OptionsScreen:
    """Volume sliders, fullscreen toggle and back to the title."""

    def __init__(self, settings: Settings, on_back, on_change=None) -> None:
        self.settings = settings
        self.on_back = on_back
        self.on_change = on_change
        self.time = 0.0
        self.backdrop = Backdrop()
        self.toggle_fullscreen = None
        self._build()

    def _build(self) -> None:
        s = self.settings
        pct = lambda v: f"{int(round(v * 100))}%"  # noqa: E731
        self.menu = Menu(
            [
                MenuItem("MUSIQUE", action="music", value_provider=lambda: pct(s.music_volume),
                         bar_provider=lambda: s.music_volume),
                MenuItem("EFFETS", action="sfx", value_provider=lambda: pct(s.sfx_volume),
                         bar_provider=lambda: s.sfx_volume),
                MenuItem("MASTER", action="master", value_provider=lambda: pct(s.master_volume),
                         bar_provider=lambda: s.master_volume),
                MenuItem("PLEIN ÉCRAN", action="fullscreen",
                         value_provider=lambda: "OUI" if s.fullscreen else "NON"),
                MenuItem("SECOUSSEUR", action="shake",
                         value_provider=lambda: pct(s.screen_shake),
                         bar_provider=lambda: s.screen_shake),
                MenuItem("COMPTEUR FPS", action="fps",
                         value_provider=lambda: "OUI" if s.show_fps else "NON"),
                MenuItem("RETOUR", action="back"),
            ],
            on_activate=self._activate,
        )

    def _activate(self, item: MenuItem) -> None:
        s = self.settings
        if item.action == "fullscreen":
            s.fullscreen = not s.fullscreen
            if self.toggle_fullscreen is not None:
                self.toggle_fullscreen(s.fullscreen)
        elif item.action == "fps":
            s.show_fps = not s.show_fps
        elif item.action == "back":
            self.on_back()
        self._build()
        if self.on_change is not None:
            self.on_change()

    def _adjust(self, direction: int) -> None:
        s = self.settings
        step = 0.1 * direction
        item = self.menu.current
        if item is None:
            return
        if item.action == "music":
            s.music_volume += step
        elif item.action == "sfx":
            s.sfx_volume += step
        elif item.action == "master":
            s.master_volume += step
        elif item.action == "shake":
            s.screen_shake += step
        s.sanitize()
        self._build()
        if self.on_change is not None:
            self.on_change()

    def handle_event(self, event: pygame.event.Event, audio=None) -> Optional[str]:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w, pygame.K_z):
                self.menu.move_up()
                if audio:
                    audio.play("ui_move")
            elif event.key in (pygame.K_DOWN, pygame.K_s, pygame.K_RIGHT):
                self.menu.move_down()
                if audio:
                    audio.play("ui_move")
            elif event.key in (pygame.K_LEFT, pygame.K_a, pygame.K_q):
                self._adjust(-1)
                if audio:
                    audio.play("ui_move")
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                current = self.menu.current
                if current is not None and current.bar_provider is not None:
                    self._adjust(1)
                else:
                    self.menu.move_down()
                if audio:
                    audio.play("ui_move")
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                if audio:
                    audio.play("ui_select")
                self.menu.activate()
            elif event.key == pygame.K_ESCAPE:
                if audio:
                    audio.play("ui_back")
                return "back"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            item = self.menu.handle_event(event)
            if item is not None:
                if audio:
                    audio.play("ui_select")
                self.menu.activate()
        return None

    def update(self, dt: float) -> None:
        self.time += dt
        self.backdrop.update(dt)

    def draw(self, target: pygame.Surface) -> None:
        width, height = target.get_size()
        self.backdrop.draw(target)
        scrim = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(scrim, (4, 6, 18, 165), scrim.get_rect())
        target.blit(scrim, (0, 0))
        fx.draw_vignette(target, 0.65)
        draw.text(
            target, "OPTIONS", (width // 2, int(height * 0.14)),
            fonts.SIZE_HUGE, Palette.TEXT, align="center", valign="center",
        )
        self.menu.draw(target, width // 2, int(height * 0.50), 460, row_height=44)
        draw.text(
            target, "< / > pour régler les volumes",
            (width // 2, height - 46), fonts.SIZE_TINY, Palette.TEXT_DIM,
            align="center", valign="center",
        )


# ==========================================================================
# Pause
# ==========================================================================
class PauseScreen:
    def __init__(self, on_resume, on_restart, on_menu, settings: Optional[Settings] = None) -> None:
        self.on_resume = on_resume
        self.on_restart = on_restart
        self.on_menu = on_menu
        self.settings = settings
        self.time = 0.0
        self.menu = Menu(
            [
                MenuItem("REPRENDRE", action="resume", hint="Échap / P"),
                MenuItem("RECOMMENCER", action="restart"),
                MenuItem("MENU PRINCIPAL", action="menu"),
            ],
            on_activate=self._activate,
        )

    def _activate(self, item: MenuItem) -> None:
        if item.action == "resume":
            self.on_resume()
        elif item.action == "restart":
            self.on_restart()
        elif item.action == "menu":
            self.on_menu()

    def handle_event(self, event: pygame.event.Event, audio=None) -> Optional[str]:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_p):
                if audio:
                    audio.play("ui_back")
                self.on_resume()
            elif event.key in (pygame.K_UP, pygame.K_w, pygame.K_z):
                self.menu.move_up()
                if audio:
                    audio.play("ui_move")
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.menu.move_down()
                if audio:
                    audio.play("ui_move")
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                if audio:
                    audio.play("ui_select")
                self.menu.activate()
            elif event.key == pygame.K_r:
                self.on_restart()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            item = self.menu.handle_event(event)
            if item is not None:
                if audio:
                    audio.play("ui_select")
                self.menu.activate()
        return None

    def update(self, dt: float) -> None:
        self.time += dt

    def draw(self, target: pygame.Surface) -> None:
        width, height = target.get_size()
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((4, 6, 18, 190))
        target.blit(overlay, (0, 0))
        draw.text(
            target, "PAUSE", (width // 2, int(height * 0.28)),
            fonts.SIZE_HUGE, Palette.CYAN, align="center", valign="center",
        )
        self.menu.draw(target, width // 2, int(height * 0.58), 360, row_height=48)
        if self.settings is not None:
            draw.text(
                target,
                f"MEILLEUR  {draw.format_number(self.settings.high_score)}",
                (width // 2, height - 52), fonts.SIZE_BODY, Palette.GOLD,
                align="center", valign="center",
            )


# ==========================================================================
# Game over
# ==========================================================================
class GameOverScreen:
    def __init__(self, score: ScoreBoard, settings: Settings, on_restart, on_menu) -> None:
        self.score = score
        self.settings = settings
        self.on_restart = on_restart
        self.on_menu = on_menu
        self.time = 0.0
        self.is_record = False
        self.reveal = 0.0
        self.menu = Menu(
            [
                MenuItem("REJOUER", action="restart", hint="Entrée / R"),
                MenuItem("MENU PRINCIPAL", action="menu", hint="Échap"),
            ],
            on_activate=self._activate,
        )

    def _activate(self, item: MenuItem) -> None:
        if item.action == "restart":
            self.on_restart()
        elif item.action == "menu":
            self.on_menu()

    def handle_event(self, event: pygame.event.Event, audio=None) -> Optional[str]:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_r):
                if audio:
                    audio.play("ui_select")
                self.on_restart()
            elif event.key == pygame.K_ESCAPE:
                if audio:
                    audio.play("ui_back")
                self.on_menu()
            elif event.key in (pygame.K_UP, pygame.K_DOWN):
                self.menu.move_up()
                if audio:
                    audio.play("ui_move")
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            item = self.menu.handle_event(event)
            if item is not None:
                if audio:
                    audio.play("ui_select")
                self.menu.activate()
        return None

    def update(self, dt: float) -> None:
        self.time += dt
        self.reveal = min(1.0, self.reveal + dt * 1.6)

    def draw(self, target: pygame.Surface) -> None:
        width, height = target.get_size()
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((4, 6, 18, int(205 * min(1.0, self.reveal * 2))))
        target.blit(overlay, (0, 0))
        fx.draw_vignette(target, 0.8 * self.reveal)

        t = self.reveal
        y = int(height * 0.20)
        draw.text_outlined(
            target, "GAME OVER", (width // 2, y), fonts.SIZE_HUGE,
            Palette.RED, Palette.VOID, border_width=3,
        )

        if self.is_record:
            pulse = 0.5 + 0.5 * math.sin(self.time * 6.0)
            color = draw.mix_color(Palette.GOLD, Palette.AMBER, pulse)
            draw.text(
                target, ">>  NOUVEAU RECORD  <<", (width // 2, y + 52),
                fonts.SIZE_BODY, color, align="center", valign="center",
            )

        # Stats panel.
        panel_w, panel_h = 520, 224
        panel = pygame.Rect(0, 0, panel_w, panel_h)
        panel.center = (width // 2, int(height * 0.52))
        draw.rounded_panel(
            target, panel, Palette.PANEL, alpha=int(235 * t),
            border=with_alpha(Palette.PURPLE, t), border_width=2, radius=Metrics.RADIUS_LG,
        )

        rows = [
            ("SCORE", draw.format_number(self.score.score)),
            ("MEILLEUR", draw.format_number(self.settings.high_score)),
            ("VAGUE ATTEINTE", str(self.score.wave)),
            ("TEMPS", self.score.formatted_time),
            ("ÉLIMINATIONS", str(self.score.kills)),
            ("PRÉCISION", f"{int(self.score.accuracy() * 100)} %"),
        ]
        for i, (label, value) in enumerate(rows):
            # Rows appear one after the other.
            row_t = max(0.0, min(1.0, t * 1.6 - i * 0.09))
            if row_t <= 0.01:
                continue
            y_row = panel.top + 22 + i * 32
            draw.text(
                target, label, (panel.left + 28, y_row), fonts.SIZE_SMALL,
                with_alpha(Palette.TEXT_DIM, row_t), valign="center",
            )
            draw.text(
                target, value, (panel.right - 28, y_row), fonts.SIZE_MEDIUM,
                with_alpha(Palette.TEXT, row_t), align="right", valign="center",
            )

        if t > 0.75:
            self.menu.draw(target, width // 2, int(height * 0.82), 340, row_height=46)


__all__ = ["Backdrop", "TitleScreen", "OptionsScreen", "PauseScreen", "GameOverScreen"]
