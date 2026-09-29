"""Tests for the difficulty curve, spawn director and score board."""

from __future__ import annotations

import pytest

from neon_survivor.core.difficulty import UNLOCK_WAVES, DifficultyCurve, weighted_pick
from neon_survivor.core.score import ScoreBoard
from neon_survivor.core.spawner import SpawnDirector
from neon_survivor.core.world import Arena


@pytest.fixture()
def curve() -> DifficultyCurve:
    return DifficultyCurve()


class TestWaveMapping:
    def test_wave_one_starts_at_zero(self, curve):
        assert curve.wave_for_time(0) == 1

    def test_wave_changes_after_duration(self, curve):
        assert curve.wave_for_time(curve.wave_duration - 0.01) == 1
        assert curve.wave_for_time(curve.wave_duration) == 2

    def test_progress_is_clamped(self, curve):
        index, progress = curve.wave_bounds(-5.0)
        assert index == 0 and progress == 0.0
        index, progress = curve.wave_bounds(curve.wave_duration * 3 + 1000)
        assert 0.0 <= progress <= 1.0

    def test_negative_time_is_safe(self, curve):
        state = curve.state_for_time(-10.0)
        assert state.wave == 1


class TestScaling:
    def test_hp_grows_strictly(self, curve):
        values = [curve.hp_multiplier(w) for w in range(1, 40)]
        assert all(b > a for a, b in zip(values, values[1:]))

    def test_spawn_interval_shrinks(self, curve):
        # Only up to the point where the floor takes over.
        values = [curve.spawn_interval(w) for w in range(1, 20)]
        assert all(b < a for a, b in zip(values, values[1:]))

    def test_spawn_interval_has_a_floor(self, curve):
        assert curve.spawn_interval(500) >= curve.max_interval_floor

    def test_max_alive_is_capped(self, curve):
        assert curve.max_alive(999) <= curve.max_alive_cap

    def test_max_alive_grows(self, curve):
        assert curve.max_alive(10) > curve.max_alive(1)

    def test_burst_size_non_decreasing(self, curve):
        values = [curve.burst_size(w) for w in range(1, 40)]
        assert all(b >= a for a, b in zip(values, values[1:]))

    def test_difficulty_at_wave_one_is_neutral(self, curve):
        assert curve.hp_multiplier(1) == pytest.approx(1.0)
        assert curve.speed_multiplier(1) == pytest.approx(1.0)
        assert curve.damage_multiplier(1) == pytest.approx(1.0)
        assert curve.score_multiplier(1) == pytest.approx(1.0)

    def test_boss_waves(self, curve):
        assert curve.is_boss_wave(5)
        assert not curve.is_boss_wave(4)
        assert curve.boss_count(4) == 0
        assert curve.boss_count(5) >= 1


class TestComposition:
    def test_wave_one_is_grunts_only(self, curve):
        assert set(curve.composition(1)) == {"grunt"}

    def test_no_type_before_its_unlock(self, curve):
        for wave in range(1, 30):
            for name in curve.composition(wave):
                assert wave >= UNLOCK_WAVES.get(name, 1)

    def test_composition_never_empty(self, curve):
        for wave in range(1, 60):
            assert curve.composition(wave), f"wave {wave} has no enemies"

    def test_available_types_grow(self, curve):
        assert len(curve.available_types(1)) < len(curve.available_types(20))

    def test_boss_excluded_from_regular_types(self, curve):
        assert "boss" not in curve.available_types(20)


class TestWaveState:
    def test_state_matches_components(self, curve):
        state = curve.state_for_time(125.0)
        assert state.wave == curve.wave_for_time(125.0)
        assert state.hp_multiplier == curve.hp_multiplier(state.wave)
        assert state.spawn_interval == curve.spawn_interval(state.wave)
        assert 0.0 <= state.time_to_next_wave <= curve.wave_duration

    def test_is_elite_flag(self, curve):
        assert not curve.state_for_time(0).is_elite
        assert curve.state_for_time(curve.wave_duration * 10).is_elite


class TestWeightedPick:
    def test_picks_a_key(self):
        weights = {"a": 1.0, "b": 3.0}
        assert weighted_pick(weights, 0.0) == "a"
        assert weighted_pick(weights, 0.99) == "b"

    def test_empty_table(self):
        assert weighted_pick({}, 0.5) is None

    def test_distribution(self):
        weights = {"a": 1.0, "b": 1.0}
        counts = {"a": 0, "b": 0}
        for i in range(2000):
            counts[weighted_pick(weights, i / 2000.0)] += 1
        assert 700 < counts["a"] < 1300
        assert 700 < counts["b"] < 1300


class TestSpawnDirector:
    def test_respects_alive_cap(self, curve):
        director = SpawnDirector(curve, seed=1)
        state = curve.state_for_time(0)
        spawned = sum(director.pending_spawns(state, state.max_alive, 1 / 60) for _ in range(600))
        assert spawned == 0

    def test_spawns_over_time(self, curve):
        director = SpawnDirector(curve, seed=1)
        state = curve.state_for_time(0)
        spawned = sum(director.pending_spawns(state, 0, 1 / 60) for _ in range(600))
        assert 5 <= spawned <= 40

    def test_records_spawned_kinds(self, curve):
        director = SpawnDirector(curve, seed=1)
        director.record_spawn("grunt")
        assert director.spawned_by_kind == {"grunt": 1}

    def test_pick_type_matches_composition(self, curve):
        director = SpawnDirector(curve, seed=3)
        state = curve.state_for_time(0)
        assert director.pick_type(state) in state.composition

    def test_elite_only_after_wave_five(self, curve):
        director = SpawnDirector(curve, seed=3)
        assert not director.pick_elite(curve.state_for_time(0))
        assert curve.state_for_time(curve.wave_duration * 10).is_elite

    def test_spawn_points_are_valid(self, arena: Arena):
        director = SpawnDirector(curve=None, seed=5)
        points = director.spawn_points(
            20, arena.center[0], arena.center[1], 640, 360,
            arena.width, arena.height, arena.wall, arena.pillars, 24.0,
        )
        assert len(points) == 20
        for x, y in points:
            assert arena.contains(x, y, 24.0)
            # Never right on top of the player.
            import math

            assert math.hypot(x - arena.center[0], y - arena.center[1]) >= 420.0

    def test_spawn_point_never_lands_in_a_pillar(self, arena: Arena):
        from neon_survivor.core.world import pillar_at

        director = SpawnDirector(curve=None, seed=8)
        for _ in range(60):
            x, y = director.spawn_point(
                arena.center[0], arena.center[1], 640, 360,
                arena.width, arena.height, arena.wall, arena.pillars, 24.0,
            )
            assert arena.contains(x, y, 24.0)
            assert pillar_at(arena.pillars, x, y, 24.0) is None


class TestScoreBoard:
    def test_add_applies_multiplier(self):
        board = ScoreBoard()
        assert board.add(100, 1.5) == 150
        assert board.score == 150

    def test_kill_increments_combo(self):
        board = ScoreBoard()
        first = board.register_kill("grunt", 10, 1.0)
        second = board.register_kill("grunt", 10, 1.0)
        assert first == 10
        assert second > 10  # the combo multiplier kicked in
        assert board.combo == 2

    def test_combo_resets_after_window(self):
        from neon_survivor.config import SCORE_COMBO_WINDOW

        board = ScoreBoard()
        board.register_kill("grunt", 10, 1.0)
        assert board.combo == 1
        board.update(SCORE_COMBO_WINDOW + 0.1)
        assert board.combo == 0

    def test_break_combo(self):
        board = ScoreBoard()
        board.register_kill("grunt", 10, 1.0)
        board.break_combo()
        assert board.combo == 0

    def test_combo_is_capped(self):
        from neon_survivor.config import SCORE_COMBO_MAX

        board = ScoreBoard()
        for _ in range(200):
            board.register_kill("grunt", 1, 1.0)
        assert board.combo_multiplier <= SCORE_COMBO_MAX

    def test_accuracy(self):
        board = ScoreBoard()
        assert board.accuracy() == 0.0
        for _ in range(10):
            board.register_shot()
        for _ in range(5):
            board.register_hit()
        assert board.accuracy() == pytest.approx(0.5)

    def test_per_kind_tracking(self):
        board = ScoreBoard()
        board.register_kill("grunt", 5, 1.0)
        board.register_kill("tank", 5, 1.0)
        board.register_kill("grunt", 5, 1.0)
        assert board.per_kind == {"grunt": 2, "tank": 1}

    def test_time_formatting(self):
        board = ScoreBoard()
        board.elapsed = 65.4
        assert board.formatted_time == "01:05"
