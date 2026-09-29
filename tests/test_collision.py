"""Tests for :mod:`neon_survivor.core.collision` and the arena."""

from __future__ import annotations

import math

import pytest

from neon_survivor.core.collision import (
    SpatialHash,
    circles_overlap,
    clamp_to_bounds,
    resolve_circle_collision,
    resolve_pillars,
)
from neon_survivor.core.world import Arena, find_free_position, generate_pillars, pillar_at


class TestCircles:
    def test_overlap(self):
        assert circles_overlap(0, 0, 5, 8, 0, 5)
        assert not circles_overlap(0, 0, 5, 11, 0, 5)

    def test_resolve_pushes_apart(self):
        pos = [0.0, 0.0]
        assert resolve_circle_collision(pos, 5.0, 8.0, 0.0, 5.0)
        assert math.hypot(pos[0] - 8.0, pos[1]) == pytest.approx(10.0, abs=1e-6)

    def test_resolve_no_overlap_returns_false(self):
        pos = [0.0, 0.0]
        assert not resolve_circle_collision(pos, 1.0, 100.0, 0.0, 1.0)
        assert pos == [0.0, 0.0]

    def test_resolve_perfect_overlap_is_safe(self):
        pos = [5.0, 5.0]
        assert resolve_circle_collision(pos, 3.0, 5.0, 5.0, 3.0)
        assert math.hypot(pos[0] - 5.0, pos[1] - 5.0) == pytest.approx(6.0, abs=1e-6)


class TestBounds:
    def test_clamp_to_bounds(self):
        pos = [-10.0, 500.0]
        assert clamp_to_bounds(pos, 5.0, 0.0, 0.0, 100.0, 100.0)
        assert pos == [5.0, 95.0]

    def test_clamp_no_change(self):
        pos = [50.0, 50.0]
        assert not clamp_to_bounds(pos, 5.0, 0.0, 0.0, 100.0, 100.0)


class TestPillars:
    def test_pushes_out_of_pillar(self):
        pillars = [(50.0, 50.0, 20.0)]
        pos = [50.0, 40.0]  # circle radius 5, so min distance is 25
        normal = resolve_pillars(pos, 5.0, pillars)
        assert normal is not None
        assert math.hypot(pos[0] - 50.0, pos[1] - 50.0) == pytest.approx(25.0, abs=1e-6)

    def test_ignores_far_pillars(self):
        pos = [0.0, 0.0]
        assert resolve_pillars(pos, 5.0, [(500.0, 500.0, 10.0)]) is None

    def test_bounce_returns_normal(self):
        pillars = [(50.0, 50.0, 20.0)]
        pos = [50.0, 40.0]
        normal = resolve_pillars(pos, 5.0, pillars, bounce=2.0)
        assert normal is not None
        # The normal points away from the pillar centre, i.e. -Y here.
        assert normal[1] < 0
        assert normal[0] == pytest.approx(0.0, abs=1e-9)


class TestSpatialHash:
    def test_finds_neighbours(self):
        grid = SpatialHash(10.0)
        grid.insert(0.0, 0.0, 5.0, "a")
        grid.insert(100.0, 100.0, 5.0, "b")
        found = grid.query(1.0, 1.0, 5.0)
        assert "a" in found
        assert "b" not in found

    def test_clear(self):
        grid = SpatialHash(10.0)
        grid.insert(0.0, 0.0, 1.0, "a")
        grid.clear()
        assert grid.query(0.0, 0.0, 1.0) == []

    def test_large_radius_spans_cells(self):
        grid = SpatialHash(10.0)
        grid.insert(0.0, 0.0, 40.0, "big")
        assert "big" in grid.query(35.0, 35.0, 1.0)


class TestArena:
    def test_pillars_are_inside_and_disjoint(self, arena: Arena):
        for x, y, r in arena.pillars:
            assert arena.wall + r <= x <= arena.width - arena.wall - r
            assert arena.wall + r <= y <= arena.height - arena.wall - r
        for i, a in enumerate(arena.pillars):
            for b in arena.pillars[i + 1:]:
                assert math.hypot(a[0] - b[0], a[1] - b[1]) > a[2] + b[2]

    def test_nearby_pillars_never_misses(self, arena: Arena):
        import random

        rng = random.Random(7)
        for _ in range(300):
            x = rng.uniform(0, arena.width)
            y = rng.uniform(0, arena.height)
            r = rng.uniform(5, 90)
            near = set(arena.nearby_pillars(x, y, r))
            for pillar in arena.pillars:
                if math.hypot(x - pillar[0], y - pillar[1]) < pillar[2] + r:
                    assert pillar in near

    def test_nearby_matches_bruteforce_for_resolution(self, arena: Arena):
        import random

        rng = random.Random(11)
        for _ in range(200):
            x = rng.uniform(0, arena.width)
            y = rng.uniform(0, arena.height)
            radius = rng.uniform(10, 60)
            a = [x, y]
            b = [x, y]
            resolve_pillars(a, radius, arena.pillars)
            resolve_pillars(b, radius, arena.nearby_pillars(x, y, radius))
            assert a == pytest.approx(b, abs=1e-9)

    def test_contains_and_clamp(self, arena: Arena):
        assert arena.contains(arena.center[0], arena.center[1])
        assert not arena.contains(-10, -10)
        pos = [-50.0, -50.0]
        arena.clamp_position(pos, 18.0)
        assert arena.contains(pos[0], pos[1], 18.0)

    def test_center_is_pillar_free(self, arena: Arena):
        assert pillar_at(arena.pillars, *arena.center, 40.0) is None

    def test_generate_pillars_is_deterministic(self):
        first = generate_pillars(count=10, seed=42)
        second = generate_pillars(count=10, seed=42)
        assert first == second

    def test_find_free_position(self, arena: Arena):
        import random

        rng = random.Random(5)
        x, y = find_free_position(
            rng, arena.pillars, arena.wall, arena.wall,
            arena.width - arena.wall, arena.height - arena.wall, 30.0,
        )
        assert pillar_at(arena.pillars, x, y, 30.0) is None
