"""Fetch and cache daily temperature data from Open-Meteo.

Two endpoints are used.

* Archive API: ERA5 reanalysis for past seasons. No key.
* Climate API: downscaled CMIP6 projections to 2050. No key.

Responses are cached on disk by request hash. Past archive data does not
change, so the cache never expires.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

from .config import (
    ARCHIVE_MODEL,
    ARCHIVE_URL,
    CLIMATE_URL,
    MAX_YEARS,
    PROJECTION_WINDOW,
    USER_AGENT,
    cache_dir,
)


class ClimateError(RuntimeError):
    """Raised when a weather request fails after all retries."""


def _cache_path(key: str, root: Path | None = None) -> Path:
    base = root if root is not None else cache_dir()
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{key}.json"


def _http_json(url: str, params: dict, *, retries: int = 4, timeout: float = 90.0) -> dict:
    query = urllib.parse.urlencode(params)
    full = f"{url}?{query}"
    last: Exception | None = None
    for attempt in range(retries):
        delay = 1.5 * (attempt + 1)
        try:
            request = urllib.request.Request(full, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code == 429:
                header = exc.headers.get("Retry-After") if exc.headers else None
                delay = float(header) if header and header.isdigit() else 8.0 * (attempt + 1)
        except Exception as exc:  # network or JSON
            last = exc
        if attempt + 1 < retries:
            time.sleep(delay)
    raise ClimateError(f"request failed after {retries} attempts: {full} ({last})")


def fetch_daily(
    lat: float,
    lon: float,
    start: str,
    end: str,
    *,
    kind: str = "archive",
    model: str | None = None,
    cache_root: Path | None = None,
    refresh: bool = False,
    retries: int = 3,
) -> dict:
    """Return the raw JSON payload for a daily temperature range."""
    params = {
        "latitude": round(float(lat), 4),
        "longitude": round(float(lon), 4),
        "start_date": start,
        "end_date": end,
        "daily": "temperature_2m_min,temperature_2m_max",
        "timezone": "auto",
    }
    url = ARCHIVE_URL if kind == "archive" else CLIMATE_URL
    if model is None and kind == "archive":
        model = ARCHIVE_MODEL
    if model:
        params["models"] = model

    key = hashlib.sha1(
        json.dumps({"url": url, "params": params}, sort_keys=True).encode("utf-8")
    ).hexdigest()[:20]
    path = _cache_path(key, cache_root)

    if path.exists() and not refresh:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

    payload = _http_json(url, params, retries=retries)
    try:
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass
    return payload


def _pick_series(daily: dict, name: str) -> list[float | None] | None:
    """Return one series, or the mean of several suffixed model series."""
    if name in daily:
        return daily[name]
    keys = sorted(k for k in daily if k.startswith(name + "_"))
    if not keys:
        return None
    rows = [daily[k] for k in keys]
    length = min(len(row) for row in rows)
    out: list[float | None] = []
    for i in range(length):
        values = [row[i] for row in rows if row[i] is not None]
        out.append(sum(values) / len(values) if values else None)
    return out


def parse_daily(payload: dict) -> dict:
    """Flatten an Open-Meteo payload into time, tmin and tmax lists."""
    daily = payload.get("daily") or {}
    times = daily.get("time") or []
    tmin = _pick_series(daily, "temperature_2m_min")
    tmax = _pick_series(daily, "temperature_2m_max")
    if tmin is None or tmax is None:
        raise ClimateError("response has no daily temperature series")
    length = min(len(times), len(tmin), len(tmax))
    return {
        "time": list(times[:length]),
        "tmin": list(tmin[:length]),
        "tmax": list(tmax[:length]),
        "latitude": payload.get("latitude"),
        "longitude": payload.get("longitude"),
        "elevation": payload.get("elevation"),
        "timezone": payload.get("timezone"),
    }


def is_southern(lat: float) -> bool:
    return float(lat) < 0.0


def season_bounds(lat: float, year: int) -> tuple[str, str]:
    """Return the first and last date of the winter season that ends in ``year``."""
    if is_southern(lat):
        return f"{year}-05-01", f"{year}-09-30"
    return f"{year - 1}-11-01", f"{year}-03-31"


def season_label(lat: float, iso_date: str) -> int | None:
    """Return the season year for a date, or None when the date is out of season."""
    day = date.fromisoformat(iso_date)
    if is_southern(lat):
        return day.year if 5 <= day.month <= 9 else None
    if day.month >= 11:
        return day.year + 1
    if day.month <= 3:
        return day.year
    return None


def last_complete_season(lat: float, today: date | None = None) -> int:
    """Return the most recent season that has fully passed."""
    today = today or date.today()
    if is_southern(lat):
        return today.year if today.month >= 10 else today.year - 1
    return today.year if today.month >= 4 else today.year - 1


def group_seasons(
    lat: float, parsed: dict, years: Iterable[int]
) -> dict[int, tuple[list[float], list[float]]]:
    """Split a daily series into per-season (tmin, tmax) pairs."""
    wanted = set(years)
    groups: dict[int, tuple[list[float], list[float]]] = {y: ([], []) for y in wanted}
    for iso, low, high in zip(parsed["time"], parsed["tmin"], parsed["tmax"]):
        if low is None or high is None:
            continue
        label = season_label(lat, iso)
        if label in wanted:
            groups[label][0].append(float(low))
            groups[label][1].append(float(high))
    return groups


def expected_season_days(lat: float) -> int:
    return 153 if is_southern(lat) else 151


def clamp_years(years: int) -> int:
    return max(5, min(int(years), MAX_YEARS))