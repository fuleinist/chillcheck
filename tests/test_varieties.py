"""Tests for the variety table and match logic."""

from __future__ import annotations

import pytest

from chillcheck.varieties import (
    crops_in,
    load_varieties,
    match_varieties,
    status_for,
    summarise,
)


def test_load_varieties():
    table = load_varieties()
    assert len(table) >= 20
    for row in table:
        assert row["chill_low"] <= row["chill_high"]
        assert row["crop"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (900.0, "safe"),
        (500.0, "safe"),
        (450.0, "marginal"),
        (400.0, "marginal"),
        (399.0, "at_risk"),
        (None, "unknown"),
    ],
)
def test_status_for(value, expected):
    assert status_for(value, 400.0, 500.0) == expected


def test_match_sorts_safe_first():
    table = load_varieties()
    rows = match_varieties(table, 900.0, 300.0)
    order = {"safe": 0, "marginal": 1, "at_risk": 2, "unknown": 3}
    statuses = [row["status_2050"] for row in rows]
    assert statuses == sorted(statuses, key=lambda status: order[status])
    assert rows[0]["status_2050"] == "safe"
    assert rows[-1]["status_2050"] == "at_risk"


def test_match_filters_by_crop():
    table = load_varieties()
    rows = match_varieties(table, 800.0, 800.0, crops=["apple"])
    assert rows
    assert {row["crop"] for row in rows} == {"apple"}


def test_match_marks_risk_when_warm():
    table = load_varieties()
    rows = match_varieties(table, 50.0, 20.0)
    assert all(row["status_now"] == "at_risk" for row in rows)
    assert all(row["status_2050"] == "at_risk" for row in rows)


def test_summarise_counts():
    rows = [
        {"status_now": "safe"},
        {"status_now": "safe"},
        {"status_now": "at_risk"},
    ]
    counts = summarise(rows, "status_now")
    assert counts["safe"] == 2
    assert counts["at_risk"] == 1
    assert counts["marginal"] == 0


def test_crops_in():
    crops = crops_in(load_varieties())
    assert "apple" in crops
    assert "cherry" in crops