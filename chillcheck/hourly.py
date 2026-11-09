"""Estimate hourly temperature from a daily minimum and maximum.

A chill model needs hourly values. Weather archives serve daily pairs. This
module joins the pairs with a cosine half wave.

The curve is anchored on two points per day: the minimum at 05:00 and the
maximum at 15:00. A half cosine joins each pair of anchors. The daily minimum
and maximum therefore stay exact. The method is the common sine curve used in
degree-day work.

Known limit: the curve cannot show a warm night after a hot day. The Utah model
still allows negative values, so the error stays bounded.
"""

from __future__ import annotations

import bisect
import math
from typing import Sequence

TMIN_HOUR = 5
TMAX_HOUR = 15
HOURS_PER_DAY = 24


def hourly_from_daily(
    tmin: Sequence[float],
    tmax: Sequence[float],
    *,
    tmin_hour: int = TMIN_HOUR,
    tmax_hour: int = TMAX_HOUR,
    hours_per_day: int = HOURS_PER_DAY,
) -> list[float]:
    """Return an hourly temperature series built from daily extremes.

    ``tmin`` and ``tmax`` hold one value per day, in order. The result holds
    ``hours_per_day`` values per day.
    """
    n = len(tmin)
    if n == 0:
        return []
    if len(tmax) != n:
        raise ValueError("tmin and tmax must have the same length")

    times: list[float] = []
    values: list[float] = []

    # Hold the first minimum back through the night before the first day.
    times.append(float(tmin_hour - hours_per_day))
    values.append(float(tmin[0]))

    for i in range(n):
        times.append(float(i * hours_per_day + tmin_hour))
        values.append(float(tmin[i]))
        times.append(float(i * hours_per_day + tmax_hour))
        values.append(float(tmax[i]))

    # Fall from the last maximum toward the last minimum.
    times.append(float(n * hours_per_day + tmin_hour))
    values.append(float(tmin[-1]))

    out: list[float] = []
    last = len(times) - 1
    for hour in range(n * hours_per_day):
        idx = bisect.bisect_right(times, hour) - 1
        if idx < 0:
            out.append(values[0])
            continue
        if idx >= last:
            out.append(values[-1])
            continue
        t0, t1 = times[idx], times[idx + 1]
        v0, v1 = values[idx], values[idx + 1]
        if t1 <= t0:
            out.append(v1)
            continue
        frac = (hour - t0) / (t1 - t0)
        out.append(v0 + (v1 - v0) * (1.0 - math.cos(math.pi * frac)) / 2.0)
    return out