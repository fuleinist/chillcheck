"""Shared fixtures for the chillcheck tests."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest


def _date_range(start: str, end: str) -> list[str]:
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)
    out = []
    current = first
    while current <= last:
        out.append(current.isoformat())
        current += timedelta(days=1)
    return out


def build_payload(lat: float, lon: float, start: str, end: str) -> dict:
    """Build a synthetic Open-Meteo payload with a seasonal temperature cycle."""
    times = _date_range(start, end)
    tmin: list[float] = []
    tmax: list[float] = []
    southern = lat < 0
    coldest = 196 if southern else 15
    for iso in times:
        day = date.fromisoformat(iso)
        doy = day.timetuple().tm_yday
        base = 14.0 - 8.0 * math.cos(2.0 * math.pi * (doy - coldest) / 365.25)
        tmin.append(round(base - 5.0, 1))
        tmax.append(round(base + 6.0, 1))
    return {
        "latitude": lat,
        "longitude": lon,
        "elevation": 120.0,
        "timezone": "Australia/Sydney",
        "daily": {
            "time": times,
            "temperature_2m_min": tmin,
            "temperature_2m_max": tmax,
        },
    }


@pytest.fixture
def fake_fetch():
    """Return a fetch_daily replacement that serves synthetic data."""

    def fetch(lat, lon, start, end, *, kind="archive", model=None, cache_root=None, refresh=False, retries=3):
        return build_payload(lat, lon, start, end)

    return fetch