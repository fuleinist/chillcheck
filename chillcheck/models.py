"""Chill accumulation models.

Three metrics, each with a different purpose.

``chill_hours``
    Count of hours between 0 and 7.2 C. Nursery tables use this unit.
``utah_units``
    Richardson (1974) weighted sum. Above 15.9 C the weights go negative.
``dynamic_chill_portions``
    Dynamic Model of Erez, Fishman, Linsley-Noakes and Allan (1990).

The Dynamic Model follows the published equations and the reference code in the
R package ``chillR`` (``chilling.R``). One difference: this code uses 273.15 for
the kelvin offset. ``chillR`` uses 273. The effect is below 0.05 percent.
"""

from __future__ import annotations

import math
from typing import Sequence

from .config import CHILL_HOURS_HIGH_C, CHILL_HOURS_LOW_C

# Dynamic Model constants, after Fishman et al. (1987) and Erez et al. (1990).
E0 = 4153.5
E1 = 12888.8
A0 = 139500.0
A1 = 2.567e18
SLP = 1.6
TETMLT = 277.0
AA = A0 / A1
EE = E1 - E0

KELVIN_OFFSET = 273.15


def utah_weight(temp_c: float) -> float:
    """Return the Richardson chill unit weight for one hour at ``temp_c``."""
    if temp_c < 1.4:
        return 0.0
    if temp_c < 2.4:
        return 0.5
    if temp_c <= 9.1:
        return 1.0
    if temp_c <= 12.4:
        return 0.5
    if temp_c <= 15.9:
        return 0.0
    if temp_c <= 18.0:
        return -0.5
    return -1.0


def chill_hours(temps_c: Sequence[float]) -> float:
    """Count hours at or between the chill hour limits."""
    return float(
        sum(1 for t in temps_c if CHILL_HOURS_LOW_C <= t <= CHILL_HOURS_HIGH_C)
    )


def utah_units(temps_c: Sequence[float]) -> float:
    """Sum the Richardson weights over the series."""
    return float(sum(utah_weight(t) for t in temps_c))


def dynamic_chill_portions(temps_c: Sequence[float]) -> float:
    """Return chill portions for one continuous season.

    State carries from hour to hour. Pass the whole season as one series.
    """
    e_prev = 0.0
    xi_prev = 0.0
    portions = 0.0

    for temp_c in temps_c:
        tk = float(temp_c) + KELVIN_OFFSET
        if tk < 150.0:
            # Physically meaningless value. Reset the destruction term.
            xi_prev = 0.0
            continue

        ftmprt = SLP * TETMLT * (tk - TETMLT) / tk
        sr = math.exp(ftmprt) if ftmprt < 700.0 else math.inf
        xi = 1.0 if sr == math.inf else sr / (1.0 + sr)

        xs = AA * math.exp(EE / tk)
        ak1 = A1 * math.exp(-E1 / tk)

        if e_prev < 1.0:
            s = e_prev
        else:
            s = e_prev - e_prev * xi_prev

        e_new = xs - (xs - s) * math.exp(-ak1)

        if e_new >= 1.0:
            portions += e_new * xi

        e_prev = e_new
        xi_prev = xi

    return portions