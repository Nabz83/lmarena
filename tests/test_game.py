"""Integration tests: the full game loop, head-less.

These exercise the real :class:`GameScene` (simulation + rendering) and the
real :class:`App` scene flow, which is where integration bugs actually live.
"""

from __future__ import annotations

import math

import pytest

from neon_survivor.config import NUKE_WAVE_SPEED
from neon_survivor.entities.enemy import Enemy
from neon_survivor.entities.pickups import Pickup
from neon_survivor.game import GameScene, InputState
from neon_survivor.settings import Settings


def idle_input() -> InputState:
    return InputState()


def firing_input(x: float, y: float) -> InputState:
    state = InputState()
    state.firing = True
    state.mouse_world = (x, y)
    state.mouse_pos = (100, 100)
    return state


def run(scene: GameScene, frames: int, input_state=None) -> None:
    for _ in range(frames):
        scene.update(1 / 60, input_state)


def freeze_spawns(scene: GameScene) -> None:
    """Stop the director so a test can observe a stable field."""
    scene.enemies.clear()
    scene.spawner.pending_spawns = lambda *args, **kwargs: 0


class TestSceneSetup:
    def test_starts_healthy(self, game_scene: GameScene):
        assert game_scene.player.alive
        assert game_scene.player.health == game_scene.player.max_health
        assert game_scene.time == 0.0
        assert game_scene.wave_state.wave == 1

    def test_player_is_inside_the_arena(self, game_scene: GameScene):
        assert game_scene.arena.contains(game_scene.player.x, game_scene.player.y, 20)

    def test_arena_center_is_free(self, game_scene: GameScene):
        from neon_survivor.core.world import pillar_at

        assert pillar_at(game_scene.arena.pillars, *game_scene.arena.center, 40.0) is None


class TestSimulation:
    def test_time_advances(self, game_scene: GameScene):
        run(game_scene, 60)
        assert game_scene.time == pytest.approx(1.0, abs=0.02)

    def test_large_dt_is_clamped(self, game_scene: GameScene):
        # A long stall must not teleport entities across the arena.
        before = game_scene.player.x
        for _ in range(10):
            game_scene.update(5.0, idle_input())
        assert abs(game_scene.player.x - before) < 500

    def test_enemies_spawn_over_time(self, game_scene: GameScene):
        run(game_scene, 600)
        assert game_scene.enemies

    def test_enemies_never_escape_the_arena(self, game_scene: GameScene):
        run(game_scene, 1800)
        for enemy in game_scene.enemies:
            assert game_scene.arena.contains(enemy.x, enemy.y, -2), enemy.kind

    def test_enemies_never_spawn_on_top_of_the_player(self, game_scene: GameScene):
        """Every enemy must appear far away, off the player's screen."""
        minimum = float("inf")
        for _ in range(1200):
            before = {id(e) for e in game_scene.enemies}
            game_scene.update(1 / 60, idle_input())
            for enemy in game_scene.enemies:
                if id(enemy) in before:
                    continue  # not a fresh spawn
                distance = math.hypot(
                    enemy.x - game_scene.player.x, enemy.y - game_scene.player.y
                )
                minimum = min(minimum, distance)
        assert minimum > 400.0, f"an enemy spawned {minimum:.0f}px away"

    def test_enemy_count_stays_bounded(self, game_scene: GameScene):
        from neon_survivor.config import ENEMY_HARD_CAP

        game_scene.player.max_health = game_scene.player.health = 1e9
        game_scene.time = 900.0
        run(game_scene, 1800)
        assert len(game_scene.enemies) <= ENEMY_HARD_CAP

    def test_waves_advance(self, game_scene: GameScene):
        # The player must survive long enough to reach wave 3.
        game_scene.player.max_health = game_scene.player.health = 1e9
        run(game_scene, 3700)  # a little over 60 s = three waves
        assert game_scene.wave_state.wave >= 3

    def test_boss_spawns_on_a_boss_wave(self, game_scene: GameScene):
        game_scene.player.max_health = game_scene.player.health = 1e9
        game_scene.time = 130.0
        game_scene.last_wave = game_scene.curve.wave_for_time(130.0) - 1
        run(game_scene, 60)
        assert any(e.is_boss for e in game_scene.enemies)

    def test_player_takes_contact_damage(self, game_scene: GameScene):
        enemy = Enemy("grunt", game_scene.player.x, game_scene.player.y)
        enemy.spawn_grace = 0.0
        game_scene.enemies.append(enemy)
        before = game_scene.player.health
        run(game_scene, 3)
        assert game_scene.player.health < before

    def test_player_invulnerability_prevents_a_streak(self, game_scene: GameScene):
        for _ in range(3):
            enemy = Enemy("grunt", game_scene.player.x, game_scene.player.y)
            enemy.spawn_grace = 0.0
            game_scene.enemies.append(enemy)
        run(game_scene, 2)
        # One hit, then the i-frames: at most one grunt's worth of damage.
        assert game_scene.player.health > game_scene.player.max_health - 40.0

    def test_death_ends_the_run(self, game_scene: GameScene):
        game_scene.player.take_damage(1e6, ignore_invuln=True)
        run(game_scene, 2)
        assert not game_scene.running
        assert game_scene.finished

    def test_update_is_a_noop_after_death(self, game_scene: GameScene):
        game_scene.player.take_damage(1e6, ignore_invuln=True)
        run(game_scene, 1)
        frozen = game_scene.time
        run(game_scene, 10)
        assert game_scene.time == frozen


class TestCombat:
    def test_bullets_damage_enemies(self, game_scene: GameScene):
        enemy = Enemy("grunt", game_scene.player.x + 120, game_scene.player.y)
        enemy.spawn_grace = 0.0
        game_scene.enemies.append(enemy)
        before = enemy.health
        for _ in range(30):
            game_scene.update(1 / 60, firing_input(enemy.x, enemy.y))
        assert enemy.health < before

    def test_killing_an_enemy_scores(self, game_scene: GameScene):
        enemy = Enemy("grunt", game_scene.player.x + 60, game_scene.player.y)
        enemy.spawn_grace = 0.0
        game_scene.enemies.append(enemy)
        for _ in range(60):
            game_scene.update(1 / 60, firing_input(enemy.x, enemy.y))
        assert game_scene.score.kills >= 1
        assert game_scene.score.score > 0

    def test_dead_enemies_are_removed(self, game_scene: GameScene):
        enemy = Enemy("grunt", game_scene.player.x + 40, game_scene.player.y)
        enemy.spawn_grace = 0.0
        game_scene.enemies.append(enemy)
        for _ in range(90):
            game_scene.update(1 / 60, firing_input(enemy.x, enemy.y))
        assert enemy not in game_scene.enemies

    def test_hostile_bullets_damage_the_player(self, game_scene: GameScene):
        game_scene.bullets.spawn(
            game_scene.player.x, game_scene.player.y, 0.0, 0.0, 5.0, 5.0, 3.0, True
        )
        before = game_scene.player.health
        game_scene.update(1 / 60, idle_input())
        assert game_scene.player.health < before

    def test_splitter_lineage_is_bounded(self, game_scene: GameScene):
        """A splitter spawns children, but the children never split again."""
        game_scene.time = 300.0
        parent = Enemy("splitter", game_scene.player.x + 80, game_scene.player.y)
        parent.spawn_grace = 0.0
        game_scene.enemies.append(parent)

        game_scene._on_enemy_killed(parent)
        children = [e for e in game_scene.enemies if e is not parent]
        assert len(children) == parent.archetype.split_into
        assert all(c.split_depth == 1 for c in children)
        assert not any(c.can_split for c in children)

        # Killing the children must not create a third generation.
        for child in children:
            child.spawn_grace = 0.0
            game_scene._on_enemy_killed(child)
        assert len(game_scene.enemies) == 1 + parent.archetype.split_into

    def test_nuke_clears_the_field(self, game_scene: GameScene):
        freeze_spawns(game_scene)
        for i in range(10):
            enemy = Enemy("grunt", game_scene.player.x + 40 + i * 10, game_scene.player.y)
            enemy.spawn_grace = 0.0
            game_scene.enemies.append(enemy)
        pickup = Pickup("nuke", game_scene.player.x + 50, game_scene.player.y)
        game_scene.trigger_nuke(pickup)
        # Long enough for the wave to sweep the whole arena.
        run(game_scene, 300)
        assert game_scene.nuke_origin is None
        assert len(game_scene.enemies) == 0

    def test_nuke_wave_radius_grows(self, game_scene: GameScene):
        game_scene.trigger_nuke(Pickup("nuke", game_scene.player.x, game_scene.player.y))
        run(game_scene, 10)
        assert game_scene.nuke_wave_radius > NUKE_WAVE_SPEED * 0.1


class TestPickups:
    def test_collecting_heals(self, game_scene: GameScene):
        game_scene.player.health = 40.0
        pickup = Pickup("health", game_scene.player.x, game_scene.player.y)
        game_scene.pickups.append(pickup)
        game_scene.update(1 / 60, idle_input())
        assert game_scene.player.health > 40.0
        assert pickup not in game_scene.pickups

    def test_collecting_upgrades_the_weapon(self, game_scene: GameScene):
        game_scene.pickups.append(Pickup("power", game_scene.player.x, game_scene.player.y))
        game_scene.update(1 / 60, idle_input())
        assert game_scene.player.weapon_power == 2

    def test_expired_pickups_disappear(self, game_scene: GameScene):
        pickup = Pickup("health", game_scene.player.x + 300, game_scene.player.y)
        pickup.life = 0.01
        game_scene.pickups.append(pickup)
        game_scene.update(1 / 60, idle_input())
        assert pickup not in game_scene.pickups

    def test_killing_an_enemy_can_drop_a_pickup(self, game_scene: GameScene):
        enemy = Enemy("grunt", game_scene.player.x + 50, game_scene.player.y)
        enemy.spawn_grace = 0.0
        for _ in range(50):
            game_scene._on_enemy_killed(enemy)
        assert game_scene.pickups


class TestDeterminism:
    def test_two_scenes_with_the_same_seed_match(self, pygame_module):
        def simulate(seed: int):
            scene = GameScene(Settings(), audio=None, seed=seed)
            scene.resize(640, 360)
            for _ in range(300):
                scene.update(1 / 60, idle_input())
            return (
                round(scene.score.kills),
                len(scene.enemies),
                round(scene.player.x, 3),
                round(scene.player.y, 3),
            )

        assert simulate(4242) == simulate(4242)

    def test_different_seeds_diverge(self, pygame_module):
        def simulate(seed: int):
            scene = GameScene(Settings(), audio=None, seed=seed)
            scene.resize(640, 360)
            for _ in range(300):
                scene.update(1 / 60, idle_input())
            return sorted(
                (round(e.x, 2), round(e.y, 2)) for e in scene.enemies
            )

        assert simulate(1) != simulate(2)


class TestRendering:
    def test_draw_produces_visual_change(self, game_scene: GameScene, display):
        display.fill((0, 0, 0))
        game_scene.draw(display, (320, 180))
        assert display.get_at((5, 5)) != (0, 0, 0)

    def test_draw_is_stable_across_resizes(self, game_scene: GameScene, pygame_module):
        for size in [(320, 180), (800, 600), (1280, 720)]:
            surface = pygame_module.Surface(size)
            game_scene.resize(*size)
            game_scene.draw(surface, (10, 10))  # must not raise

    def test_particles_are_updated_and_die(self, game_scene: GameScene):
        freeze_spawns(game_scene)
        game_scene.particles.clear()
        game_scene.particles.burst(0.0, 0.0, 40, (50, 200))
        assert len(game_scene.particles) > 0
        run(game_scene, 180)
        assert len(game_scene.particles) == 0

    def test_particle_pool_is_bounded(self, game_scene: GameScene):
        for _ in range(200):
            game_scene.particles.burst(0.0, 0.0, 50, (50, 200))
        assert len(game_scene.particles) <= game_scene.particles.capacity

    def test_floating_text_expires(self, game_scene: GameScene):
        from neon_survivor.ui.theme import Palette

        game_scene.floaters.add(0.0, 0.0, "+10", Palette.TEXT)
        run(game_scene, 120)
        assert len(game_scene.floaters) == 0


class TestCamera:
    def test_camera_follows_the_player(self, game_scene: GameScene):
        game_scene.player.x += 300
        game_scene.player.y += 200
        for _ in range(60):
            game_scene._update_camera(1 / 60)
        cx, cy = game_scene.camera.center
        assert abs(cx - game_scene.player.x) < 5.0
        assert abs(cy - game_scene.player.y) < 5.0

    def test_camera_stays_inside_the_arena(self, game_scene: GameScene):
        game_scene.player.x = 0.0
        game_scene.player.y = 0.0
        for _ in range(60):
            game_scene._update_camera(1 / 60)
        assert game_scene.camera.x >= -1.0
        assert game_scene.camera.y >= -1.0

    def test_screen_to_world_round_trip(self, game_scene: GameScene):
        for point in [(0, 0), (320, 180), (639, 359)]:
            wx, wy = game_scene.camera.screen_to_world(*point)
            sx, sy = game_scene.camera.world_to_screen(wx, wy)
            assert sx == pytest.approx(point[0], abs=1.0)
            assert sy == pytest.approx(point[1], abs=1.0)

    def test_trauma_decays(self, game_scene: GameScene):
        game_scene.camera.add_trauma(1.0)
        for _ in range(300):
            game_scene.camera.update(1 / 60, 1.6)
        assert game_scene.camera.trauma == pytest.approx(0.0, abs=0.01)


class TestWaveProgression:
    def test_banner_appears_on_a_new_wave(self, game_scene: GameScene):
        game_scene.time = 29.0
        game_scene.update(1 / 60, idle_input())
        game_scene.time = 31.0
        game_scene.update(1 / 60, idle_input())
        assert game_scene.banner.active
        assert "WAVE 2" in game_scene.banner.text

    def test_banner_expires(self, game_scene: GameScene):
        game_scene.banner.show("TEST", duration=0.2)
        for _ in range(30):
            game_scene.banner.update(1 / 60)
        assert not game_scene.banner.active

    def test_hit_stop_freezes_the_simulation(self, game_scene: GameScene):
        run(game_scene, 60)
        game_scene.hit_stop = 0.5
        frozen = game_scene.time
        game_scene.update(1 / 60, idle_input())
        assert game_scene.time == frozen
