"""Tests for the chill models."""

from __future__ import annotations

import pytest

from chillcheck.models import (
    chill_hours,
    dynamic_chill_portions,
    utah_units,
    utah_weight,
)


@pytest.mark.parametrize(
    ("temp", "weight"),
    [
        (0.0, 0.0),
        (1.4, 0.5),
        (3.0, 1.0),
        (5.0, 1.0),
        (9.1, 1.0),
        (10.0, 0.5),
        (12.4, 0.5),
        (14.0, 0.0),
        (16.5, -0.5),
        (20.0, -1.0),
    ],
)
def test_utah_weight(temp, weight):
    assert utah_weight(temp) == weight


def test_chill_hours_counts_the_window():
    series = [5.0] * 48
    assert chill_hours(series) == 48.0


def test_chill_hours_ignores_warm_hours():
    series = [5.0, 10.0, 20.0, -1.0, 7.2, 0.0]
    assert chill_hours(series) == 3.0


def test_utah_units_goes_negative_in_heat():
    assert utah_units([5.0] * 10) == 10.0
    assert utah_units([20.0] * 10) == -10.0


def test_dynamic_model_is_about_one_portion_per_day_at_six_c():
    days = 10
    portions = dynamic_chill_portions([6.0] * (24 * days))
    per_day = portions / days
    assert 0.6 <= per_day <= 1.1, f"got {per_day:.2f} portions per day"


def test_dynamic_model_is_zero_when_warm():
    assert dynamic_chill_portions([20.0] * 720) == 0.0
    assert dynamic_chill_portions([30.0] * 720) == 0.0


def test_dynamic_model_falls_as_winter_warms():
    cold = dynamic_chill_portions([5.0] * 720)
    mild = dynamic_chill_portions([11.0] * 720)
    assert cold > mild > 0


def test_dynamic_model_handles_empty_input():
    assert dynamic_chill_portions([]) == 0.0