"""Tests for :mod:`neon_survivor.core.mathutils`."""

from __future__ import annotations

import math

import pytest

from neon_survivor.core.mathutils import (
    angle_between,
    angle_difference,
    approach,
    clamp,
    damp,
    from_angle,
    inverse_lerp,
    length,
    lerp,
    limit_length,
    normalize,
    point_in_rect,
    circle_intersects_rect,
    rotate_towards,
    segment_intersects_circle,
    sign,
)


class TestClamp:
    @pytest.mark.parametrize(
        "value,low,high,expected",
        [(5, 0, 10, 5), (-1, 0, 10, 0), (99, 0, 10, 10), (0, 0, 10, 0)],
    )
    def test_clamp(self, value, low, high, expected):
        assert clamp(value, low, high) == expected


class TestInterpolation:
    def test_lerp(self):
        assert lerp(0, 10, 0.5) == pytest.approx(5.0)
        assert lerp(0, 10, 0.0) == 0.0
        assert lerp(0, 10, 1.0) == 10.0

    def test_inverse_lerp(self):
        assert inverse_lerp(0, 10, 5) == pytest.approx(0.5)
        assert inverse_lerp(10, 10, 5) == 0.0  # degenerate range

    def test_approach(self):
        assert approach(0, 10, 3) == 3
        assert approach(0, 10, 100) == 10
        assert approach(10, 0, 3) == 7
        assert approach(5, 5, 100) == 5

    def test_damp_converges(self):
        value = 0.0
        for _ in range(200):
            value = damp(value, 10.0, 8.0, 1 / 60)
        assert value == pytest.approx(10.0, abs=0.1)

    def test_damp_zero_smoothing_snaps(self):
        assert damp(0.0, 10.0, 0.0, 0.016) == 10.0


class TestVectors:
    def test_normalize(self):
        assert normalize(3, 4) == pytest.approx((0.6, 0.8))

    def test_normalize_zero_is_safe(self):
        assert normalize(0.0, 0.0) == (0.0, 0.0)

    def test_length(self):
        assert length(3, 4) == pytest.approx(5.0)

    def test_limit_length(self):
        x, y = limit_length(30, 40, 5)
        assert math.hypot(x, y) == pytest.approx(5.0, abs=1e-9)

    def test_limit_length_keeps_short_vectors(self):
        assert limit_length(1.0, 0.0, 5.0) == (1.0, 0.0)

    def test_from_angle(self):
        x, y = from_angle(0.0, 2.0)
        assert (x, y) == pytest.approx((2.0, 0.0))
        x, y = from_angle(math.pi / 2, 1.0)
        assert (x, y) == pytest.approx((0.0, 1.0))


class TestAngles:
    def test_angle_between(self):
        assert angle_between(0, 0, 1, 0) == pytest.approx(0.0)
        assert angle_between(0, 0, 0, 1) == pytest.approx(math.pi / 2)

    def test_angle_difference_wraps(self):
        assert angle_difference(0.1, 2 * math.pi - 0.1) == pytest.approx(-0.2, abs=1e-6)

    def test_angle_difference_range(self):
        for a in (-3.0, 0.0, 2.0, 3.1):
            for b in (-2.7, 0.5, 3.0):
                assert -math.pi - 1e-9 <= angle_difference(a, b) <= math.pi + 1e-9

    def test_rotate_towards_respects_limit(self):
        start = 0.0
        result = rotate_towards(start, 1.0, 0.1)
        assert result == pytest.approx(0.1)

    def test_rotate_towards_snaps(self):
        assert rotate_towards(0.0, 0.05, 1.0) == pytest.approx(0.05)


class TestGeometry:
    def test_point_in_rect(self):
        assert point_in_rect(5, 5, (0, 0, 10, 10))
        assert not point_in_rect(15, 5, (0, 0, 10, 10))

    def test_circle_intersects_rect(self):
        # Centre just outside the left edge, radius reaching inside.
        assert circle_intersects_rect(0, 5, 2, (0, 0, 10, 10))
        # Fully inside the rect.
        assert circle_intersects_rect(5, 5, 1, (0, 0, 10, 10))
        # Too far away on every side.
        assert not circle_intersects_rect(-5, 5, 1, (0, 0, 10, 10))
        assert not circle_intersects_rect(5, 20, 1, (0, 0, 10, 10))

    def test_segment_hits_circle(self):
        assert segment_intersects_circle(0, 0, 10, 0, 5, 0, 1)
        assert not segment_intersects_circle(0, 0, 10, 0, 5, 5, 1)

    def test_segment_degenerate(self):
        assert segment_intersects_circle(3, 3, 3, 3, 3, 3, 1)
        assert not segment_intersects_circle(3, 3, 3, 3, 9, 9, 1)


class TestSign:
    @pytest.mark.parametrize(
        "value,expected", [(5, 1), (-5, -1), (0, 0), (0.0, 0)]
    )
    def test_sign(self, value, expected):
        assert sign(value) == expected
