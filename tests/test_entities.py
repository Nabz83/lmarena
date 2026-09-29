"""Tests for the player, enemies, projectiles and pickups."""

from __future__ import annotations

import math

import pytest

from neon_survivor.config import (
    MAX_WEAPON_POWER,
    PLAYER_MAX_HEALTH,
    WEAPON_SPREAD_TABLE,
)
from neon_survivor.core.world import Arena
from neon_survivor.entities.enemy import Enemy
from neon_survivor.entities.enemy_types import ARCHETYPES, MAX_SPLIT_DEPTH, get_archetype
from neon_survivor.entities.pickups import PICKUP_TYPES, Pickup, apply_pickup, roll_pickup
from neon_survivor.entities.player import Player
from neon_survivor.entities.projectiles import Bullet, ProjectilePool, bullet_hits_circle


class TestPlayerMovement:
    def test_accelerates_towards_input(self):
        player = Player()
        for _ in range(60):
            player.update_movement(1.0, 0.0, 1 / 60)
        assert player.x > 100
        assert player.vx == pytest.approx(player.effective_speed, rel=0.05)

    def test_diagonal_is_not_faster(self):
        player = Player()
        for _ in range(60):
            player.update_movement(1.0, 1.0, 1 / 60)
        assert math.hypot(player.vx, player.vy) <= player.effective_speed + 1e-6

    def test_friction_stops_the_player(self):
        player = Player()
        for _ in range(30):
            player.update_movement(1.0, 0.0, 1 / 60)
        for _ in range(120):
            player.update_movement(0.0, 0.0, 1 / 60)
        assert math.hypot(player.vx, player.vy) < 1.0

    def test_speed_boost_increases_speed(self):
        player = Player()
        base = player.effective_speed
        player.speed_boost = 5.0
        assert player.effective_speed > base


class TestPlayerWeapon:
    def test_fire_respects_cooldown(self):
        player = Player()
        shots = player.fire()
        assert shots and len(shots) == WEAPON_SPREAD_TABLE[0]
        assert not player.can_fire
        assert player.fire() == []

    def test_cooldown_expires(self):
        player = Player()
        player.fire()
        for _ in range(120):
            player.tick_weapon(1 / 60)
        assert player.can_fire

    def test_weapon_levels_add_bullets(self):
        player = Player()
        counts = []
        for level in range(1, MAX_WEAPON_POWER + 1):
            player.weapon_power = level
            player.fire_cooldown = 0.0
            counts.append(len(player.fire()))
        assert counts == list(WEAPON_SPREAD_TABLE[:MAX_WEAPON_POWER])
        assert counts == sorted(counts)

    def test_upgrade_is_capped(self):
        player = Player()
        player.weapon_power = MAX_WEAPON_POWER
        assert player.upgrade_weapon(5) == 0
        assert player.weapon_power == MAX_WEAPON_POWER

    def test_damage_grows_with_power(self):
        player = Player()
        low = player.damage
        player.weapon_power = 5
        assert player.damage > low

    def test_shot_angles_are_symmetric(self):
        player = Player()
        player.weapon_power = 3
        player.facing = 0.0
        angles = player.shot_angles()
        assert len(angles) == 2
        assert angles[0] < 0 < angles[1]
        assert abs(angles[0] + angles[1]) < 1e-9


class TestPlayerHealth:
    def test_damage_reduces_health(self):
        player = Player()
        assert player.take_damage(25.0)
        assert player.health == pytest.approx(PLAYER_MAX_HEALTH - 25.0)

    def test_invulnerability_blocks_a_second_hit(self):
        player = Player()
        player.take_damage(10.0)
        assert not player.take_damage(10.0)
        assert player.health == pytest.approx(PLAYER_MAX_HEALTH - 10.0)

    def test_invulnerability_expires(self):
        player = Player()
        player.take_damage(10.0)
        player.invuln_timer = 0.0
        assert player.take_damage(10.0)

    def test_death(self):
        player = Player()
        player.take_damage(1e6, ignore_invuln=True)
        assert not player.alive
        assert player.health == 0.0

    def test_shield_absorbs_damage(self):
        player = Player()
        player.shield = 50.0
        player.take_damage(20.0)
        assert player.health == pytest.approx(PLAYER_MAX_HEALTH)
        assert player.shield == pytest.approx(30.0)

    def test_heal_is_capped(self):
        player = Player()
        player.health = 90.0
        player.heal(1000.0)
        assert player.health == pytest.approx(PLAYER_MAX_HEALTH)

    def test_regeneration_after_delay(self):
        from neon_survivor.config import PLAYER_REGEN_DELAY

        player = Player()
        player.take_damage(40.0)
        player.invuln_timer = 0.0
        for _ in range(int(PLAYER_REGEN_DELAY * 60) + 120):
            player.update(1 / 60)
        assert player.health > PLAYER_MAX_HEALTH - 40.0

    def test_reset(self):
        player = Player()
        player.take_damage(50.0)
        player.weapon_power = 5
        player.reset(10.0, 20.0)
        assert player.health == player.max_health
        assert player.weapon_power == 1
        assert (player.x, player.y) == (10.0, 20.0)


class TestEnemyArchetypes:
    @pytest.mark.parametrize("kind", sorted(ARCHETYPES.keys()))
    def test_every_archetype_is_constructible(self, kind):
        enemy = Enemy(kind, 0.0, 0.0)
        assert enemy.alive
        assert enemy.max_health > 0
        assert enemy.radius > 0
        assert enemy.archetype.key == kind

    def test_unknown_archetype_raises(self):
        with pytest.raises(KeyError):
            get_archetype("does-not-exist")

    def test_wave_scaling(self):
        weak = Enemy("grunt", 0, 0, hp_multiplier=1.0)
        strong = Enemy("grunt", 0, 0, hp_multiplier=3.0)
        assert strong.max_health > weak.max_health * 2.9

    def test_elite_is_tougher(self):
        normal = Enemy("grunt", 0, 0)
        elite = Enemy("grunt", 0, 0, elite=True)
        assert elite.max_health > normal.max_health
        assert elite.score > normal.score
        assert elite.radius > normal.radius

    def test_spawn_grace_blocks_damage(self):
        enemy = Enemy("grunt", 0, 0)
        assert not enemy.take_damage(1000.0)
        enemy.spawn_grace = 0.0
        assert enemy.take_damage(1000.0)

    def test_splitters_stop_reproducing(self):
        parent = Enemy("splitter", 0, 0)
        assert parent.can_split
        child = Enemy("splitter", 0, 0, split_depth=MAX_SPLIT_DEPTH)
        assert not child.can_split

    def test_non_splitters_never_split(self):
        for kind in ARCHETYPES:
            if kind != "splitter":
                assert not Enemy(kind, 0, 0).can_split


class TestEnemyAI:
    def test_chaser_closes_in(self):
        enemy = Enemy("grunt", 0.0, 0.0)
        start = enemy.distance_to(500.0, 0.0)
        for _ in range(180):
            enemy.update(1 / 60, 500.0, 0.0)
        assert enemy.distance_to(500.0, 0.0) < start

    def test_shooter_keeps_its_distance(self):
        enemy = Enemy("shooter", 0.0, 0.0)
        for _ in range(300):
            enemy.update(1 / 60, 60.0, 0.0, [])
        preferred = enemy.archetype.preferred_range
        # It should stay in a band around the preferred range, not hug the
        # player nor flee to the arena edge.
        assert 0.25 * preferred < enemy.distance_to(60.0, 0.0) < 2.0 * preferred

    def test_shooter_emits_bullets(self):
        enemy = Enemy("shooter", 0.0, 0.0)
        shots = []
        for _ in range(240):
            enemy.update(1 / 60, 300.0, 0.0, shots)
        assert len(shots) >= 2

    def test_charger_cycles_states(self):
        enemy = Enemy("charger", 0.0, 0.0)
        seen = []
        for _ in range(400):
            enemy.update(1 / 60, 400.0, 0.0, None)
            if not seen or seen[-1] != enemy.state:
                seen.append(enemy.state)
        assert "windup" in seen and "dash" in seen

    def test_charger_dash_is_faster_than_its_walk(self):
        enemy = Enemy("charger", 0.0, 0.0)
        peak = 0.0
        for _ in range(400):
            enemy.update(1 / 60, 400.0, 0.0, None)
            peak = max(peak, math.hypot(enemy.vx, enemy.vy))
        assert peak == pytest.approx(enemy.archetype.charge_speed, rel=0.05)

    def test_charger_hits_harder_while_dashing(self):
        enemy = Enemy("charger", 0.0, 0.0)
        assert enemy.is_damaging
        walk = enemy.contact_damage
        enemy.state = "windup"
        assert enemy.contact_damage == pytest.approx(walk)
        enemy.state = "dash"
        assert enemy.contact_damage > walk

    def test_boss_emits_radial_patterns(self):
        boss = Enemy("boss", 0.0, 0.0)
        shots = []
        for _ in range(180):
            boss.update(1 / 60, 400.0, 0.0, shots)
        assert len(shots) > 10

    def test_boss_gets_faster_as_it_loses_health(self):
        boss = Enemy("boss", 0.0, 0.0)
        boss.spawn_grace = 0.0
        for _ in range(120):
            boss.update(1 / 60, 400.0, 0.0, [])
        boss.take_damage(boss.max_health * 0.8, 0.0, 1.0, 0.0)
        for _ in range(180):
            boss.update(1 / 60, 400.0, 0.0, [])
        assert boss.rage > 0.5

    def test_enemies_never_reverse_direction_permanently(self):
        enemy = Enemy("grunt", 0.0, 0.0)
        for _ in range(60):
            enemy.update(1 / 60, 100.0, 0.0)
        # Speed must stay exactly the archetype speed (plus knockback).
        assert math.hypot(enemy.vx, enemy.vy) == pytest.approx(enemy.speed, rel=0.05)

    def test_separation_pushes_apart(self):
        a = Enemy("grunt", 0.0, 0.0)
        b = Enemy("grunt", 1.0, 0.0)
        min_dist = a.radius + b.radius
        assert a.separate(b)
        assert a.distance_to(b.x, b.y) == pytest.approx(min_dist, abs=1e-6)

    def test_separation_respects_mass(self):
        light = Enemy("runner", 0.0, 0.0)   # mass 0.7
        heavy = Enemy("tank", 1.0, 0.0)     # mass 3.4
        light.separate(heavy)
        moved_light = abs(light.x)
        moved_heavy = abs(heavy.x - 1.0)
        assert moved_light > moved_heavy * 2

    def test_separation_of_coincident_centres(self):
        a = Enemy("grunt", 5.0, 5.0)
        b = Enemy("grunt", 5.0, 5.0)
        assert a.separate(b)
        assert a.distance_to(b.x, b.y) == pytest.approx(a.radius + b.radius, abs=1e-6)


class TestProjectiles:
    def test_bullet_moves(self):
        bullet = Bullet(0, 0, 100.0, 0.0, 10.0, 5.0, 1.0)
        bullet.update(0.1)
        assert bullet.x == pytest.approx(10.0)

    def test_bullet_expires(self):
        bullet = Bullet(0, 0, 100.0, 0.0, 10.0, 5.0, 0.1)
        bullet.update(0.2)
        assert not bullet.alive

    def test_pierce_consumes_hits(self):
        bullet = Bullet(0, 0, 10.0, 0.0, 1.0, pierce=1)
        assert bullet.hit()
        assert not bullet.hit()
        assert not bullet.alive

    def test_hits_circle(self):
        bullet = Bullet(0, 0, 0.0, 0.0, 1.0, radius=5.0)
        assert bullet_hits_circle(bullet, 8.0, 0.0, 5.0)
        assert not bullet_hits_circle(bullet, 30.0, 0.0, 5.0)

    def test_pool_culls_out_of_bounds(self, arena: Arena):
        pool = ProjectilePool()
        pool.spawn(-500.0, -500.0, 10.0, 0.0, 1.0)
        pool.update(1 / 60, arena)
        assert len(pool) == 0

    def test_pool_keeps_in_bounds(self, arena: Arena):
        pool = ProjectilePool()
        pool.spawn(arena.center[0], arena.center[1], 10.0, 0.0, 1.0)
        pool.update(1 / 60, arena)
        assert len(pool) == 1

    def test_pool_partitions_by_side(self, arena: Arena):
        pool = ProjectilePool()
        pool.spawn(1000.0, 1000.0, 1.0, 0.0, 1.0, hostile=False)
        pool.spawn(1000.0, 1000.0, 1.0, 0.0, 1.0, hostile=True)
        assert len(list(pool.for_each_player_bullet())) == 1
        assert len(list(pool.for_each_hostile_bullet())) == 1


class TestPickups:
    def test_roll_returns_a_valid_type(self):
        import random

        rng = random.Random(4)
        for _ in range(200):
            kind = roll_pickup(rng)
            assert kind in PICKUP_TYPES
            assert PICKUP_TYPES[kind].weight > 0

    def test_gem_is_never_rolled(self):
        import random

        rng = random.Random(4)
        rolled = {roll_pickup(rng) for _ in range(500)}
        assert "gem" not in rolled

    def test_magnet_pulls_a_pickup_in(self):
        from neon_survivor.config import PICKUP_MAGNET_RADIUS

        pickup = Pickup("health", 0.0, 0.0)
        player_x = PICKUP_MAGNET_RADIUS * 0.9  # inside the magnet radius
        for _ in range(60):
            pickup.update(1 / 60, player_x, 0.0)
        assert pickup.pulled
        assert abs(pickup.x - player_x) < abs(0.0 - player_x)

    def test_magnet_ignores_far_pickups(self):
        from neon_survivor.config import PICKUP_MAGNET_RADIUS

        pickup = Pickup("health", 0.0, 0.0)
        for _ in range(30):
            pickup.update(1 / 60, PICKUP_MAGNET_RADIUS * 3.0, 0.0)
        assert not pickup.pulled
        assert pickup.x == pytest.approx(0.0)

    def test_pickup_expires(self):
        pickup = Pickup("health", 0.0, 0.0)
        pickup.life = 0.01
        pickup.update(1.0, 1e6, 1e6)
        assert pickup.should_despawn()

    def test_blink_flag(self):
        pickup = Pickup("health", 0.0, 0.0)
        assert not pickup.blinking
        pickup.life = 0.5
        assert pickup.blinking

    @pytest.mark.parametrize("kind", sorted(PICKUP_TYPES.keys()))
    def test_every_pickup_applies_cleanly(self, kind):
        player = Player()
        pickup = Pickup(kind, 0.0, 0.0)
        result = apply_pickup(pickup, player, None)
        assert result.label
        assert player.alive

    def test_health_pickup_heals(self):
        player = Player()
        player.health = 10.0
        apply_pickup(Pickup("health", 0.0, 0.0), player, None)
        assert player.health > 10.0

    def test_power_pickup_upgrades(self):
        player = Player()
        apply_pickup(Pickup("power", 0.0, 0.0), player, None)
        assert player.weapon_power == 2

    def test_nuke_calls_the_game_hook(self):
        calls = []

        class FakeGame:
            def trigger_nuke(self, pickup):
                calls.append(pickup)

        apply_pickup(Pickup("nuke", 0.0, 0.0), Player(), FakeGame())
        assert len(calls) == 1
