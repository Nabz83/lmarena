"""Integration tests for the application shell (scenes, persistence, input)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from neon_survivor import settings as settings_module
from neon_survivor.app import App
from neon_survivor.settings import Settings


@pytest.fixture()
def profile(tmp_path, monkeypatch):
    """Redirect the save file to a temporary directory for the whole test."""
    path = tmp_path / "neon_survivor.json"
    monkeypatch.setattr(settings_module, "save_path", lambda *_a, **_k: path)
    return path


@pytest.fixture()
def app(pygame_module, profile) -> App:
    """A head-less app with an empty profile and a dummy display."""
    pygame_module.init()  # a previous test may have called pygame.quit()
    instance = App(Settings(), headless=True)
    instance.init_display()
    instance.goto_title()
    yield instance
    instance.audio.shutdown()
    pygame_module.quit()


def key_event(pygame, key: int) -> "object":
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="")


def kill_player(app: App) -> None:
    app.game.player.take_damage(1e6, ignore_invuln=True)


class TestBoot:
    def test_starts_on_the_title_screen(self, app: App):
        assert app.scene_name == "title"
        assert app.screen is not None

    def test_update_and_draw_are_safe(self, app: App):
        for _ in range(10):
            app.update(1 / 60)
            app.draw()

    def test_fullscreen_toggle_round_trip(self, app: App):
        app.toggle_fullscreen(True)
        assert app.fullscreen
        assert app.settings.fullscreen
        app.toggle_fullscreen(False)
        assert not app.fullscreen

    def test_resize_before_a_game_is_safe(self, app: App):
        app._on_resize(800, 600)
        assert app.game is None

    def test_quit_event_stops_the_loop(self, app: App, pygame_module):
        app._handle_event(pygame_module.event.Event(pygame_module.QUIT))
        assert not app.running

    def test_run_loop_terminates(self, pygame_module, profile):
        instance = App(Settings(), headless=True)
        instance.run(max_frames=15)
        assert instance.running is False  # shutdown() ran


class TestSceneFlow:
    def test_start_game(self, app: App):
        app.start_game()
        assert app.scene_name == "game"
        assert app.game is not None
        assert app.game.player.alive

    def test_the_game_advances(self, app: App):
        app.start_game()
        for _ in range(300):
            app.update(1 / 60)
        assert app.game.time > 3.0
        assert app.game.enemies

    def test_pause_freezes_the_simulation(self, app: App):
        app.start_game()
        app.pause_game()
        assert app.scene_name == "pause"
        assert app.pause_screen is not None
        frozen = app.game.time
        for _ in range(30):
            app.update(1 / 60)
        assert app.game.time == frozen

    def test_resume(self, app: App):
        app.start_game()
        app.pause_game()
        app.resume_game()
        assert app.scene_name == "game"
        assert app.pause_screen is None
        app.update(1 / 60)
        assert app.game.time > 0.0

    def test_restart_resets_the_run(self, app: App):
        app.start_game()
        for _ in range(300):
            app.update(1 / 60)
        assert app.game.score.kills or app.game.time > 1.0
        app.restart_game()
        assert app.scene_name == "game"
        assert app.game.time == 0.0
        assert app.game.score.kills == 0
        assert app.game.player.health == app.game.player.max_health

    def test_death_reaches_the_game_over_screen(self, app: App):
        app.start_game()
        kill_player(app)
        for _ in range(5):
            app.update(1 / 60)
        assert app.scene_name == "gameover"
        assert app.game_over_screen is not None
        assert app.game.player.alive is False

    def test_game_over_is_persisted(self, app: App):
        app.start_game()
        app.game.score.score = 4321
        kill_player(app)
        for _ in range(5):
            app.update(1 / 60)
        assert app.settings.high_score == 4321
        assert app.settings.total_runs == 1
        assert app.game_over_screen.is_record is True

    def test_a_second_run_is_not_a_record(self, app: App):
        for score in (1000, 10):
            app.start_game()
            app.game.score.score = score
            kill_player(app)
            for _ in range(5):
                app.update(1 / 60)
        assert app.settings.high_score == 1000
        assert app.settings.total_runs == 2
        assert app.game_over_screen.is_record is False

    def test_back_to_title_clears_the_run(self, app: App):
        app.start_game()
        app.goto_title()
        assert app.scene_name == "title"
        assert app.game is None

    def test_options_open_and_close(self, app: App):
        app.goto_options()
        assert app.scene_name == "options"
        assert app.options_screen is not None
        for _ in range(5):
            app.update(1 / 60)
            app.draw()
        app._options_back()
        assert app.scene_name == "title"

    def test_options_apply_volume_changes(self, app: App):
        app.goto_options()
        app.settings.music_volume = 0.2
        app._options_changed()
        assert app.audio.music_volume == pytest.approx(0.2)

    def test_the_fps_overlay_setting_reaches_the_hud(self, app: App):
        app.start_game()
        app.settings.show_fps = True
        app._options_changed()
        assert app.game.hud.show_fps is True
        app.settings.show_fps = False
        app._options_changed()
        assert app.game.hud.show_fps is False


class TestInput:
    def test_escape_pauses(self, app: App, pygame_module):
        app.start_game()
        app._handle_event(key_event(pygame_module, pygame_module.K_ESCAPE))
        assert app.scene_name == "pause"

    def test_p_resumes(self, app: App, pygame_module):
        app.start_game()
        app._handle_event(key_event(pygame_module, pygame_module.K_p))
        assert app.scene_name == "pause"
        app._handle_event(key_event(pygame_module, pygame_module.K_ESCAPE))
        assert app.scene_name == "game"

    def test_f11_toggles_fullscreen(self, app: App, pygame_module):
        app._handle_event(key_event(pygame_module, pygame_module.K_F11))
        assert app.fullscreen
        app._handle_event(key_event(pygame_module, pygame_module.K_F11))
        assert not app.fullscreen

    def test_mute(self, app: App, pygame_module):
        app.start_game()
        assert app.audio.muted is False
        app._handle_event(key_event(pygame_module, pygame_module.K_m))
        assert app.audio.muted is True
        app._handle_event(key_event(pygame_module, pygame_module.K_m))
        assert app.audio.muted is False

    def test_enter_starts_the_game(self, app: App, pygame_module):
        assert app.title_screen.menu.index == 0  # "JOUER"
        app._handle_event(key_event(pygame_module, pygame_module.K_RETURN))
        assert app.scene_name == "game"

    def test_escape_on_the_title_quits(self, app: App, pygame_module):
        app._handle_event(key_event(pygame_module, pygame_module.K_ESCAPE))
        assert not app.running

    def test_menu_navigation_wraps(self, app: App, pygame_module):
        app._handle_event(key_event(pygame_module, pygame_module.K_DOWN))
        assert app.title_screen.menu.index == 1
        app._handle_event(key_event(pygame_module, pygame_module.K_UP))
        assert app.title_screen.menu.index == 0
        app._handle_event(key_event(pygame_module, pygame_module.K_UP))
        assert app.title_screen.menu.index == 2  # wraps to the last entry

    def test_quit_entry(self, app: App, pygame_module):
        app.title_screen.menu.index = 2  # "QUITTER"
        app._handle_event(key_event(pygame_module, pygame_module.K_RETURN))
        assert not app.running

    def test_options_entry(self, app: App, pygame_module):
        app.title_screen.menu.index = 1  # "OPTIONS"
        app._handle_event(key_event(pygame_module, pygame_module.K_RETURN))
        assert app.scene_name == "options"

    def test_video_resize_event_is_handled(self, app: App, pygame_module):
        app.start_game()
        event = pygame_module.event.Event(
            pygame_module.VIDEORESIZE, w=900, h=500
        )
        app._handle_event(event)
        assert (app.game.camera.view_width, app.game.camera.view_height) == (900.0, 500.0)


class TestPersistence:
    def test_settings_round_trip(self, app: App, profile: Path):
        app.settings.high_score = 999
        app.settings.best_wave = 12
        assert app.settings.save()
        reloaded = Settings.load(profile)
        assert reloaded.high_score == 999
        assert reloaded.best_wave == 12

    def test_the_game_over_run_is_written_to_disk(self, app: App, profile: Path):
        app.start_game()
        app.game.score.score = 777
        kill_player(app)
        for _ in range(5):
            app.update(1 / 60)
        assert profile.exists()
        data = json.loads(profile.read_text(encoding="utf-8"))
        assert data["high_score"] == 777
        assert data["total_runs"] == 1

    def test_a_corrupt_profile_starts_fresh(self, profile: Path):
        profile.write_text("<<<not json>>>", encoding="utf-8")
        assert Settings.load(profile).high_score == 0
