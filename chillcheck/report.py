"""Build the chill assessment for one location.

The report answers four questions.

1. How much chill does this place get now?
2. Is the total falling?
3. How much will it get in 2050?
4. Which varieties still clear their requirement?
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from statistics import mean, pstdev
from typing import Iterable

from . import models
from .climate import (
    ClimateError,
    clamp_years,
    expected_season_days,
    fetch_daily,
    group_seasons,
    is_southern,
    last_complete_season,
    parse_daily,
    season_bounds,
)
from .config import (
    DEFAULT_HORIZON,
    DEFAULT_YEARS,
    PROJECTION_WINDOW,
    RATIO_HIGH,
    RATIO_LOW,
)
from .hourly import hourly_from_daily
from .varieties import load_varieties, match_varieties, summarise


def season_metrics(tmin: list[float], tmax: list[float]) -> dict:
    """Run all three chill metrics over one season."""
    hours = hourly_from_daily(tmin, tmax)
    return {
        "chill_hours": round(models.chill_hours(hours), 1),
        "utah_units": round(models.utah_units(hours), 1),
        "chill_portions": round(models.dynamic_chill_portions(hours), 2),
        "hours_modelled": len(hours),
    }


def _mean_of(series: list[dict], key: str) -> float | None:
    values = [row[key] for row in series if row.get(key) is not None]
    if not values:
        return None
    return round(mean(values), 2)


def _slope_per_decade(series: list[dict], key: str) -> float | None:
    """Least squares slope of a metric against season year, scaled to a decade."""
    rows = [row for row in series if row.get(key) is not None]
    if len(rows) < 3:
        return None
    xs = [float(row["season"]) for row in rows]
    ys = [float(row[key]) for row in rows]
    mx, my = mean(xs), mean(ys)
    denominator = sum((x - mx) ** 2 for x in xs)
    if denominator == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denominator
    return round(slope * 10.0, 2)


def _window(series: list[dict]) -> dict:
    seasons = [row["season"] for row in series]
    return {"from": min(seasons), "to": max(seasons), "count": len(seasons)}


def assess(
    lat: float,
    lon: float,
    *,
    name: str | None = None,
    years: int = DEFAULT_YEARS,
    horizon: int = DEFAULT_HORIZON,
    crops: Iterable[str] | None = None,
    varieties_path: str | None = None,
    cache_root: str | None = None,
    refresh: bool = False,
    today: date | None = None,
) -> dict:
    """Return the full assessment as a plain dictionary."""
    years = clamp_years(years)
    last = last_complete_season(lat, today)
    first = last - years + 1
    start = season_bounds(lat, first)[0]
    end = season_bounds(lat, last)[1]

    payload = fetch_daily(
        lat,
        lon,
        start,
        end,
        kind="archive",
        cache_root=cache_root,
        refresh=refresh,
    )
    parsed = parse_daily(payload)
    groups = group_seasons(lat, parsed, range(first, last + 1))

    minimum_days = int(expected_season_days(lat) * 0.7)
    series: list[dict] = []
    skipped: list[int] = []
    for season_year in range(first, last + 1):
        tmin, tmax = groups.get(season_year, ([], []))
        if len(tmin) < minimum_days:
            skipped.append(season_year)
            continue
        row = {"season": season_year, "days": len(tmin)}
        row.update(season_metrics(tmin, tmax))
        series.append(row)

    if not series:
        raise ClimateError("no complete season in the requested range")

    recent = series[-min(10, len(series)) :]
    baseline = {
        **_window(series),
        "chill_hours": _mean_of(series, "chill_hours"),
        "utah_units": _mean_of(series, "utah_units"),
        "chill_portions": _mean_of(series, "chill_portions"),
        "sd_portions": round(pstdev([r["chill_portions"] for r in series]), 2)
        if len(series) > 1
        else 0.0,
        "min_portions": min(r["chill_portions"] for r in series),
        "max_portions": max(r["chill_portions"] for r in series),
    }
    recent_block = {
        **_window(recent),
        "chill_hours": _mean_of(recent, "chill_hours"),
        "utah_units": _mean_of(recent, "utah_units"),
        "chill_portions": _mean_of(recent, "chill_portions"),
    }
    trend = {
        "portions_per_decade": _slope_per_decade(series, "chill_portions"),
        "hours_per_decade": _slope_per_decade(series, "chill_hours"),
        "utah_units_per_decade": _slope_per_decade(series, "utah_units"),
    }

    notes: list[str] = []
    projection = _projection(
        lat, lon, horizon, baseline, notes, cache_root=cache_root, refresh=refresh
    )

    ratio = None
    utah_ratio = None
    if baseline["chill_portions"]:
        ratio = round(baseline["chill_hours"] / baseline["chill_portions"], 1)
        utah_ratio = round(baseline["utah_units"] / baseline["chill_portions"], 1)
        if ratio < RATIO_LOW:
            notes.append(
                "This site is warm. The hour count is low against the portion count. "
                "The hour-based match is cautious."
            )
        elif ratio > RATIO_HIGH:
            notes.append(
                "This site is cold. The hour count is high against the portion count. "
                "Read the portion figure as the better measure."
            )

    table = load_varieties(varieties_path)
    rows = match_varieties(
        table,
        baseline["chill_hours"],
        (projection or {}).get("chill_hours"),
        crops=crops,
    )

    hemisphere = "southern" if is_southern(lat) else "northern"
    window_label = (
        "May to September" if is_southern(lat) else "November to March"
    )

    notes.append(
        "Hourly temperature is estimated from daily minimum and maximum "
        "with a cosine curve. Daily extremes are exact."
    )
    if parsed.get("elevation") is not None:
        notes.append(
            f"The weather grid cell sits at {parsed['elevation']} m. "
            "Local terrain can differ."
        )
    if skipped:
        notes.append(
            f"Skipped incomplete seasons: {', '.join(str(s) for s in skipped)}."
        )

    return {
        "location": {
            "name": name or f"{lat:.4f}, {lon:.4f}",
            "latitude": round(float(lat), 4),
            "longitude": round(float(lon), 4),
            "elevation_m": parsed.get("elevation"),
            "timezone": parsed.get("timezone"),
            "hemisphere": hemisphere,
            "season_window": window_label,
        },
        "seasons": series,
        "baseline": baseline,
        "recent": recent_block,
        "trend": trend,
        "projection": projection,
        "variety_ratio": {
            "chill_hours_per_portion": ratio,
            "utah_units_per_portion": utah_ratio,
            "note": "Diagnostic only. Warm sites show a lower ratio than cool sites.",
        },
        "variety_summary": {
            "now": summarise(rows, "status_now"),
            "y2050": summarise(rows, "status_2050"),
        },
        "varieties": rows,
        "notes": notes,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _window_rows(
    lat: float,
    lon: float,
    first: int,
    last: int,
    *,
    cache_root: str | None = None,
    refresh: bool = False,
) -> list[dict]:
    """Return per-season metrics for a projected window."""
    payload = fetch_daily(
        lat,
        lon,
        season_bounds(lat, first)[0],
        season_bounds(lat, last)[1],
        kind="climate",
        cache_root=cache_root,
        refresh=refresh,
    )
    parsed = parse_daily(payload)
    groups = group_seasons(lat, parsed, range(first, last + 1))

    rows: list[dict] = []
    minimum_days = int(expected_season_days(lat) * 0.7)
    for season_year in range(first, last + 1):
        tmin, tmax = groups.get(season_year, ([], []))
        if len(tmin) < minimum_days:
            continue
        row = {"season": season_year, "days": len(tmin)}
        row.update(season_metrics(tmin, tmax))
        rows.append(row)
    return rows


def _projection(
    lat: float,
    lon: float,
    horizon: int,
    baseline: dict,
    notes: list[str],
    *,
    cache_root: str | None = None,
    refresh: bool = False,
) -> dict | None:
    """Project the season with a change factor against the observed baseline.

    Raw GCM output carries a large local bias. At Sydney the default model set
    puts the winter minimum about 4 C above the reanalysis. Absolute values from
    the model are therefore not usable.

    The tool compares the model against itself on two windows. It applies the
    ratio to the observed baseline. Hours are derived from the observed
    hours-per-portion ratio, because the model does not resolve the cold tail.
    """
    future_first = horizon - PROJECTION_WINDOW + 1
    reference_last = horizon - 46
    reference_first = reference_last - (PROJECTION_WINDOW * 2 - 1)

    try:
        reference_rows = _window_rows(
            lat, lon, reference_first, reference_last, cache_root=cache_root, refresh=refresh
        )
        future_rows = _window_rows(
            lat, lon, future_first, horizon, cache_root=cache_root, refresh=refresh
        )
    except ClimateError as exc:
        notes.append(f"The {horizon} projection is not available ({exc}).")
        return None

    if not reference_rows or not future_rows:
        notes.append(f"The {horizon} projection returned no complete season.")
        return None

    reference_portions = _mean_of(reference_rows, "chill_portions")
    future_portions = _mean_of(future_rows, "chill_portions")
    if not reference_portions or reference_portions <= 0:
        notes.append("The projection reference window has no chill.")
        return None

    factor = max(0.1, min(1.5, future_portions / reference_portions))
    base_portions = baseline.get("chill_portions")
    base_hours = baseline.get("chill_hours")
    if not base_portions:
        notes.append("The projection needs a baseline with chill.")
        return None

    projected_portions = round(base_portions * factor, 2)
    if base_hours is not None:
        projected_hours = round(projected_portions * (base_hours / base_portions), 1)
    else:
        projected_hours = None

    notes.append(
        "The projection uses a change factor. The tool compares the model on two "
        "windows, then applies the ratio to the observed baseline. This removes "
        "model bias."
    )

    return {
        "year": horizon,
        "window": [min(r["season"] for r in future_rows), max(r["season"] for r in future_rows)],
        "reference_window": [
            min(r["season"] for r in reference_rows),
            max(r["season"] for r in reference_rows),
        ],
        "seasons": len(future_rows),
        "change_factor": round(factor, 3),
        "chill_hours": projected_hours,
        "chill_portions": projected_portions,
        "model_portions": {
            "reference": reference_portions,
            "future": future_portions,
        },
        "method": "change_factor",
        "source": "Open-Meteo Climate API, CMIP6 downscaled, default model set",
    }


def to_text(report: dict) -> str:
    """Render a report as short plain text."""
    loc = report["location"]
    base = report["baseline"]
    recent = report["recent"]
    proj = report["projection"]
    lines = [
        f"chillcheck - {loc['name']}",
        f"Grid {loc['latitude']}, {loc['longitude']} at {loc['elevation_m']} m",
        f"Season {loc['season_window']} ({loc['hemisphere']} hemisphere)",
        "",
        f"Baseline {base['from']} to {base['to']} ({base['count']} seasons)",
        f"  chill portions  {base['chill_portions']}",
        f"  chill hours     {base['chill_hours']}",
        f"  Utah units      {base['utah_units']}",
        "",
        f"Recent {recent['from']} to {recent['to']} ({recent['count']} seasons)",
        f"  chill portions  {recent['chill_portions']}",
        f"  chill hours     {recent['chill_hours']}",
        "",
        f"Trend {report['trend']['portions_per_decade']} portions per decade",
    ]
    if proj:
        lines += [
            "",
            f"Projection {proj['year']} ({proj['window'][0]} to {proj['window'][1]})",
            f"  chill portions  {proj['chill_portions']}",
            f"  chill hours     {proj['chill_hours']}",
        ]
    else:
        lines += ["", "Projection not available."]

    lines += ["", "Varieties", ""]
    for row in report["varieties"]:
        lines.append(
            f"  {row['name']:<22} {row['crop']:<9} "
            f"{row['chill_low']:>4.0f}-{row['chill_high']:<4.0f} h  "
            f"now {row['status_now']:<8} 2050 {row['status_2050']}"
        )
    if report["notes"]:
        lines += ["", "Notes"]
        for note in report["notes"]:
            lines.append(f"  - {note}")
    return "\n".join(lines)