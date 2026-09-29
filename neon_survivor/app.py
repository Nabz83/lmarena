"""Application shell: window, scene stack and the main loop.

The app owns everything that is not gameplay: creating the window, handling
window events, switching between the title screen, the game and the
overlays, and persisting settings on exit.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

import pygame

from neon_survivor.audio.manager import AudioManager
from neon_survivor.config import (
    GAME_TITLE,
    RENDERER_PREFERENCE,
    RESIZABLE,
    TARGET_FPS,
    VERSION,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from neon_survivor.game import GameScene
from neon_survivor.settings import Settings
from neon_survivor.ui.screens import (
    GameOverScreen,
    OptionsScreen,
    PauseScreen,
    TitleScreen,
)
from neon_survivor.ui.theme import Palette


def _resolve_base_dir() -> str:
    """Directory that holds bundled data (differs when frozen by PyInstaller)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class App:
    """The windowed application."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        headless: bool = False,
        autoplay: bool = False,
    ) -> None:
        self.settings = settings or Settings.load()
        self.headless = headless
        self.autoplay = autoplay
        self.base_dir = _resolve_base_dir()
        self.running = False
        self.scene_name = "title"
        self.previous_scene = "title"
        self.clock = pygame.time.Clock()
        self.fps = 0.0
        self._fps_smoothed = 60.0

        self.screen: Optional[pygame.Surface] = None
        self.fullscreen = bool(self.settings.fullscreen)

        self.audio = AudioManager(
            master_volume=self.settings.master_volume,
            music_volume=self.settings.music_volume,
            sfx_volume=self.settings.sfx_volume,
        )
        self.game: Optional[GameScene] = None
        self.title_screen: Optional[TitleScreen] = None
        self.options_screen: Optional[OptionsScreen] = None
        self.pause_screen: Optional[PauseScreen] = None
        self.game_over_screen: Optional[GameOverScreen] = None

    # ==================================================================
    # Boot
    # ==================================================================
    def init_display(self) -> None:
        pygame.init()
        flags = pygame.RESIZABLE if RESIZABLE else 0
        if self.fullscreen:
            flags |= pygame.FULLSCREEN
        size = (WINDOW_WIDTH, WINDOW_HEIGHT)
        self.screen = self._create_window(size, flags)
        pygame.display.set_caption(f"{GAME_TITLE} v{VERSION}")
        pygame.key.set_repeat(0)
        self._apply_icon()

    def _create_window(self, size, flags) -> pygame.Surface:
        """Try the preferred renderers, falling back to the default one."""
        candidates = list(RENDERER_PREFERENCE) if not self.headless else ["sdl"]
        for index, _renderer in enumerate(candidates):
            try:
                pygame.display.quit()
                pygame.display.init()
                pygame.display.set_mode(size, flags, index=index, depth=0)
                return pygame.display.get_surface()
            except Exception:  # pragma: no cover - driver dependent
                # This renderer is unavailable on this machine; try the next.
                continue
        # Final fallback: no explicit renderer.
        pygame.display.quit()
        pygame.display.init()
        return pygame.display.set_mode(size, flags)

    def _apply_icon(self) -> None:
        """Build a small procedural window icon (no icon file needed)."""
        try:
            size = 32
            icon = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(icon, Palette.VOID, (size // 2, size // 2), size // 2)
            points = [
                (size // 2 + 11, size // 2),
                (size // 2 - 8, size // 2 - 9),
                (size // 2 - 8, size // 2 + 9),
            ]
            pygame.draw.polygon(icon, Palette.PLAYER, points)
            pygame.display.set_icon(icon)
        except Exception:
            pass

    # ==================================================================
    # Scene management
    # ==================================================================
    def goto_title(self) -> None:
        self.game = None
        self.pause_screen = None
        self.game_over_screen = None
        self.scene_name = "title"
        if self.title_screen is None:
            self.title_screen = TitleScreen(
                self.settings, self.start_game, self.goto_options, self.quit
            )
        else:
            self.title_screen.best = self.settings.high_score
        self.audio.play_music("calm", fade_ms=600)

    def goto_options(self) -> None:
        self.previous_scene = self.scene_name
        self.scene_name = "options"
        self.options_screen = OptionsScreen(
            self.settings, self._options_back, self._options_changed
        )
        self.options_screen.toggle_fullscreen = self.toggle_fullscreen

    def _options_back(self) -> None:
        self.settings.save()
        if self.previous_scene == "title" or self.scene_name == "options":
            self.goto_title()

    def _options_changed(self) -> None:
        self.audio.set_master_volume(self.settings.master_volume)
        self.audio.set_music_volume(self.settings.music_volume)
        self.audio.set_sfx_volume(self.settings.sfx_volume)
        if self.game is not None:
            self.game.camera.shake_scale = self.settings.screen_shake
            self.game.hud.show_fps = self.settings.show_fps

    def start_game(self) -> None:
        self.audio.preload_core()
        self.game = GameScene(self.settings, audio=self.audio)
        if self.screen is not None:
            self.game.resize(*self.screen.get_size())
        self.scene_name = "game"
        self.audio.play_music("calm", fade_ms=400)

    def restart_game(self) -> None:
        self.start_game()

    def pause_game(self) -> None:
        if self.scene_name != "game" or self.game is None:
            return
        self.previous_scene = "game"
        self.scene_name = "pause"
        self.pause_screen = PauseScreen(
            self.resume_game, self.restart_game, self.goto_title, self.settings
        )
        self.audio.pause_music()

    def resume_game(self) -> None:
        self.scene_name = "game"
        self.pause_screen = None
        self.audio.unpause_music()

    def end_game(self) -> None:
        """Persist the run and show the game-over screen."""
        game = self.game
        if game is None:
            self.goto_title()
            return
        survival = game.score.survival_points()
        if survival:
            game.score.add(survival)
        is_record = self.settings.record_run(
            game.score.score, game.wave_state.wave, game.score.elapsed, game.score.kills
        )
        self.settings.save()
        self.game_over_screen = GameOverScreen(
            game.score, self.settings, self.restart_game, self.goto_title
        )
        self.game_over_screen.is_record = is_record
        self.scene_name = "gameover"
        self.audio.stop_music(400)
        self.audio.play("game_over")
        if is_record:
            self.audio.play("record")

    def toggle_fullscreen(self, enabled: bool) -> None:
        self.fullscreen = bool(enabled)
        self.settings.fullscreen = self.fullscreen
        if self.screen is None:
            return
        flags = pygame.RESIZABLE if RESIZABLE else 0
        if self.fullscreen:
            flags |= pygame.FULLSCREEN
        size = (WINDOW_WIDTH, WINDOW_HEIGHT)
        if self.fullscreen:
            size = (0, 0)
        self.screen = pygame.display.set_mode(size, flags)
        self._on_resize(*self.screen.get_size())

    def quit(self) -> None:
        self.running = False

    def shutdown(self) -> None:
        try:
            self.settings.save()
        except Exception:
            pass
        try:
            self.audio.shutdown()
        finally:
            pygame.quit()

    # ==================================================================
    # Events
    # ==================================================================
    def _on_resize(self, width: int, height: int) -> None:
        if self.game is not None:
            self.game.resize(width, height)

    def _handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.quit()
            return

        if event.type == pygame.VIDEORESIZE:
            if not self.fullscreen:
                width = max(640, event.w)
                height = max(360, event.h)
                self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
                self._on_resize(width, height)
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11 or (
                event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT
            ):
                self.toggle_fullscreen(not self.fullscreen)
                return
            if event.key == pygame.K_F3 and event.mod & pygame.KMOD_CTRL:
                self.settings.show_fps = not self.settings.show_fps
                if self.game is not None:
                    self.game.hud.show_fps = self.settings.show_fps
                return

        # --- per-scene ---------------------------------------------------
        if self.scene_name == "title":
            result = self.title_screen.handle_event(event, self.audio)
            if result == "quit":
                self.quit()
        elif self.scene_name == "options":
            result = self.options_screen.handle_event(event, self.audio)
            if result == "back":
                self._options_back()
        elif self.scene_name == "pause":
            self.pause_screen.handle_event(event, self.audio)
        elif self.scene_name == "gameover":
            self.game_over_screen.handle_event(event, self.audio)
        elif self.scene_name == "game" and self.game is not None:
            self._handle_game_event(event)

    def _handle_game_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_p):
                self.pause_game()
            elif event.key == pygame.K_m:
                muted = not self.audio.muted
                self.audio.set_muted(muted)
                self.settings.master_volume = 0.0 if muted else 1.0
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Clicking the window restores focus on some platforms.
            pygame.mouse.get_focused()

    # ==================================================================
    # Loop
    # ==================================================================
    def _current_input(self):
        """Build the input snapshot for the current scene."""
        from neon_survivor.game import InputState

        keys = pygame.key.get_pressed()
        mouse_pos = pygame.mouse.get_pos()
        mouse_buttons = pygame.mouse.get_pressed()
        if self.game is not None:
            world = self.game.camera.screen_to_world(*mouse_pos)
        else:
            world = (float(mouse_pos[0]), float(mouse_pos[1]))
        return InputState.from_keys(keys, mouse_pos, mouse_buttons, world)

    def update(self, dt: float) -> None:
        if self.scene_name in ("title", "options") and self.title_screen:
            self.title_screen.update(dt)
            if self.scene_name == "options" and self.options_screen:
                self.options_screen.update(dt)
        elif self.scene_name == "pause" and self.pause_screen:
            self.pause_screen.update(dt)
        elif self.scene_name == "gameover" and self.game_over_screen:
            self.game_over_screen.update(dt)
        elif self.scene_name == "game" and self.game is not None:
            self.game.set_fps(self._fps_smoothed)
            self.game.update(dt, self._current_input())
            if not self.game.running:
                self.end_game()

    def draw(self) -> None:
        if self.screen is None:
            return
        if self.scene_name == "title" and self.title_screen:
            self.title_screen.draw(self.screen)
        elif self.scene_name == "options" and self.options_screen:
            self.options_screen.draw(self.screen)
        elif self.scene_name == "pause":
            if self.game is not None:
                self.game.draw(self.screen, pygame.mouse.get_pos())
            if self.pause_screen:
                self.pause_screen.draw(self.screen)
        elif self.scene_name == "gameover":
            if self.game is not None:
                self.game.draw(self.screen, pygame.mouse.get_pos())
            if self.game_over_screen:
                self.game_over_screen.draw(self.screen)
        elif self.scene_name == "game" and self.game is not None:
            self.game.draw(self.screen, pygame.mouse.get_pos())
        pygame.display.flip()

    def run(self, max_frames: Optional[int] = None) -> None:
        self.init_display()
        self.goto_title()
        self.running = True
        frames = 0
        try:
            while self.running:
                dt = self.clock.tick(TARGET_FPS) / 1000.0
                self._fps_smoothed = self.clock.get_fps() or self._fps_smoothed
                for event in pygame.event.get():
                    self._handle_event(event)
                    if not self.running:
                        break
                if not self.running:
                    break
                self.update(dt)
                self.draw()
                frames += 1
                if max_frames is not None and frames >= max_frames:
                    break
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            self.shutdown()


__all__ = ["App"]
