"""Tests for season handling and payload parsing."""

from __future__ import annotations

from datetime import date

import pytest

from chillcheck.climate import (
    ClimateError,
    clamp_years,
    group_seasons,
    is_southern,
    last_complete_season,
    parse_daily,
    season_bounds,
    season_label,
)


def test_hemisphere():
    assert is_southern(-33.8)
    assert not is_southern(51.5)


def test_southern_season_bounds():
    assert season_bounds(-33.8, 2025) == ("2025-05-01", "2025-09-30")


def test_northern_season_bounds():
    assert season_bounds(51.5, 2025) == ("2024-11-01", "2025-03-31")


def test_season_label_south():
    assert season_label(-33.8, "2024-07-15") == 2024
    assert season_label(-33.8, "2024-11-15") is None


def test_season_label_north():
    assert season_label(51.5, "2024-12-01") == 2025
    assert season_label(51.5, "2025-02-01") == 2025
    assert season_label(51.5, "2025-06-01") is None


def test_last_complete_season_south():
    assert last_complete_season(-33.8, date(2026, 11, 10)) == 2026
    assert last_complete_season(-33.8, date(2026, 3, 10)) == 2025


def test_last_complete_season_north():
    assert last_complete_season(51.5, date(2026, 5, 1)) == 2026
    assert last_complete_season(51.5, date(2026, 1, 1)) == 2025


def test_parse_daily_plain_keys():
    payload = {
        "elevation": 47.0,
        "daily": {
            "time": ["2025-07-01", "2025-07-02"],
            "temperature_2m_min": [5.0, 6.0],
            "temperature_2m_max": [15.0, 16.0],
        },
    }
    parsed = parse_daily(payload)
    assert parsed["time"] == ["2025-07-01", "2025-07-02"]
    assert parsed["tmin"] == [5.0, 6.0]
    assert parsed["tmax"] == [15.0, 16.0]
    assert parsed["elevation"] == 47.0


def test_parse_daily_averages_model_keys():
    payload = {
        "daily": {
            "time": ["2025-07-01", "2025-07-02"],
            "temperature_2m_min_A": [4.0, 6.0],
            "temperature_2m_min_B": [6.0, 8.0],
            "temperature_2m_max_A": [14.0, 16.0],
            "temperature_2m_max_B": [16.0, 18.0],
        }
    }
    parsed = parse_daily(payload)
    assert parsed["tmin"] == [5.0, 7.0]
    assert parsed["tmax"] == [15.0, 17.0]


def test_parse_daily_raises_without_series():
    with pytest.raises(ClimateError):
        parse_daily({"daily": {"time": []}})


def test_group_seasons():
    parsed = {
        "time": ["2025-05-01", "2025-07-01", "2025-10-01"],
        "tmin": [5.0, 4.0, 9.0],
        "tmax": [15.0, 14.0, 19.0],
    }
    groups = group_seasons(-33.8, parsed, [2025])
    assert groups[2025][0] == [5.0, 4.0]
    assert groups[2025][1] == [15.0, 14.0]


def test_clamp_years():
    assert clamp_years(1) == 5
    assert clamp_years(30) == 30
    assert clamp_years(99) == 40