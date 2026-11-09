"""Tests for the hourly temperature builder."""

from __future__ import annotations

import pytest

from chillcheck.hourly import hourly_from_daily


def test_length_matches_input():
    series = hourly_from_daily([10.0, 11.0, 12.0], [20.0, 21.0, 22.0])
    assert len(series) == 72


def test_anchors_are_exact():
    tmin = [10.0, 11.0]
    tmax = [20.0, 21.0]
    series = hourly_from_daily(tmin, tmax)
    assert series[5] == pytest.approx(10.0)
    assert series[15] == pytest.approx(20.0)
    assert series[24 + 5] == pytest.approx(11.0)
    assert series[24 + 15] == pytest.approx(21.0)


def test_values_stay_inside_the_daily_range():
    series = hourly_from_daily([5.0, 6.0], [18.0, 19.0])
    assert min(series) >= 5.0
    assert max(series) <= 19.0


def test_curve_is_continuous():
    series = hourly_from_daily([4.0, 5.0], [16.0, 17.0])
    jumps = [abs(b - a) for a, b in zip(series, series[1:])]
    assert max(jumps) < 3.0


def test_empty_input():
    assert hourly_from_daily([], []) == []


def test_mismatched_input_raises():
    with pytest.raises(ValueError):
        hourly_from_daily([1.0, 2.0], [3.0])