"""End-to-end tests for the report builder."""

from __future__ import annotations

from datetime import date

import pytest

from chillcheck.climate import ClimateError
from chillcheck.report import assess, season_metrics, to_text


@pytest.fixture
def patched(monkeypatch, fake_fetch):
    monkeypatch.setattr("chillcheck.report.fetch_daily", fake_fetch)
    return fake_fetch


def test_assess_returns_full_report(patched):
    report = assess(-33.78, 151.12, name="Sydney", years=5, today=date(2026, 11, 10))

    assert report["location"]["name"] == "Sydney"
    assert report["location"]["hemisphere"] == "southern"
    assert report["location"]["season_window"] == "May to September"
    assert report["baseline"]["count"] == 5
    assert len(report["seasons"]) == 5
    assert report["baseline"]["chill_portions"] > 0
    assert report["projection"] is not None
    assert report["projection"]["chill_portions"] is not None
    assert report["varieties"]
    assert report["notes"]


def test_assess_marks_every_variety(patched):
    report = assess(-33.78, 151.12, years=5, today=date(2026, 11, 10))
    allowed = {"safe", "marginal", "at_risk", "unknown"}
    for row in report["varieties"]:
        assert row["status_now"] in allowed
        assert row["status_2050"] in allowed


def test_assess_filters_crops(patched):
    report = assess(-33.78, 151.12, years=5, crops=["apple"], today=date(2026, 11, 10))
    assert {row["crop"] for row in report["varieties"]} == {"apple"}


def test_northern_location_uses_november_season(patched):
    report = assess(51.5, -0.12, name="London", years=5, today=date(2026, 11, 10))
    assert report["location"]["hemisphere"] == "northern"
    assert report["location"]["season_window"] == "November to March"


def test_projection_failure_is_reported(monkeypatch, fake_fetch):
    def failing(lat, lon, start, end, *, kind="archive", **kwargs):
        if kind == "climate":
            raise ClimateError("offline")
        return fake_fetch(lat, lon, start, end, kind=kind, **kwargs)

    monkeypatch.setattr("chillcheck.report.fetch_daily", failing)
    report = assess(-33.78, 151.12, years=5, today=date(2026, 11, 10))
    assert report["projection"] is None
    assert any("projection" in note.lower() for note in report["notes"])


def test_season_metrics_keys():
    # A curve from 1 C to 6 C stays inside the chill hour window all day.
    metrics = season_metrics([1.0] * 153, [6.0] * 153)
    assert set(metrics) == {"chill_hours", "utah_units", "chill_portions", "hours_modelled"}
    assert metrics["hours_modelled"] == 153 * 24
    assert metrics["chill_hours"] == 153 * 24


def test_season_metrics_counts_only_cold_hours():
    # A curve from 5 C to 15 C leaves part of each day above the window.
    metrics = season_metrics([5.0] * 153, [15.0] * 153)
    assert 0 < metrics["chill_hours"] < 153 * 24


def test_text_rendering(patched):
    report = assess(-33.78, 151.12, name="Sydney", years=5, today=date(2026, 11, 10))
    text = to_text(report)
    assert "chillcheck - Sydney" in text
    assert "Varieties" in text
    assert "chill portions" in text