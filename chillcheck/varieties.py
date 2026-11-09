"""Variety table and match logic."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Iterable

STATUS_ORDER = {"safe": 0, "marginal": 1, "at_risk": 2, "unknown": 3}


def load_varieties(path: str | Path | None = None) -> list[dict]:
    """Load the curated variety table."""
    if path is not None:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    text = resources.files(__package__).joinpath("data/varieties.json").read_text(encoding="utf-8")
    return json.loads(text)


def status_for(value: float | None, low: float, high: float) -> str:
    """Classify an observed chill total against a requirement range."""
    if value is None:
        return "unknown"
    if value >= high:
        return "safe"
    if value >= low:
        return "marginal"
    return "at_risk"


def match_varieties(
    varieties: Iterable[dict],
    baseline_hours: float | None,
    projected_hours: float | None,
    *,
    crops: Iterable[str] | None = None,
) -> list[dict]:
    """Score each variety at the baseline climate and at the projection."""
    wanted = {c.lower() for c in crops} if crops else None
    rows: list[dict] = []
    for item in varieties:
        crop = str(item.get("crop", "")).lower()
        if wanted and crop not in wanted:
            continue
        low = float(item["chill_low"])
        high = float(item["chill_high"])
        rows.append(
            {
                "name": item["name"],
                "crop": crop,
                "chill_low": low,
                "chill_high": high,
                "source": item.get("source", ""),
                "note": item.get("note", ""),
                "status_now": status_for(baseline_hours, low, high),
                "status_2050": status_for(projected_hours, low, high),
                "margin_now": None if baseline_hours is None else round(baseline_hours - high, 1),
                "margin_2050": None if projected_hours is None else round(projected_hours - high, 1),
            }
        )
    rows.sort(key=lambda r: (STATUS_ORDER[r["status_2050"]], -r["chill_high"], r["name"]))
    return rows


def crops_in(varieties: Iterable[dict]) -> list[str]:
    return sorted({str(v.get("crop", "")).lower() for v in varieties if v.get("crop")})


def summarise(rows: Iterable[dict], key: str) -> dict[str, int]:
    counts = {"safe": 0, "marginal": 0, "at_risk": 0, "unknown": 0}
    for row in rows:
        counts[row[key]] = counts.get(row[key], 0) + 1
    return counts