"""Constants and paths for chillcheck."""

from __future__ import annotations

import os
from pathlib import Path

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
CLIMATE_URL = "https://climate-api.open-meteo.com/v1/climate"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Pin one reanalysis model. The default "best match" series changes source
# around 2017 and creates a step in the record.
ARCHIVE_MODEL = "era5"

# Place search favours this country before it falls back to a global search.
PREFERRED_COUNTRY = os.environ.get("CHILLCHECK_COUNTRY", "AU")

DEFAULT_YEARS = 30
DEFAULT_HORIZON = 2050
MIN_YEARS = 5
MAX_YEARS = 40
PROJECTION_WINDOW = 5

# Chill hour window used by nursery tables.
CHILL_HOURS_LOW_C = 0.0
CHILL_HOURS_HIGH_C = 7.2

# Working ratio between chill hours and chill portions. Wide band, used only
# as a sanity check. Warm and cool sites differ by design.
HOURS_PER_PORTION = 30.0
RATIO_LOW = 6.0
RATIO_HIGH = 45.0

# Season windows by hemisphere.
SOUTHERN_MONTHS = (5, 6, 7, 8, 9)
NORTHERN_MONTHS = (11, 12, 1, 2, 3)

USER_AGENT = "chillcheck/0.1 (open data; +https://github.com/fuleinist/chillcheck)"


def cache_dir() -> Path:
    """Return the cache directory, honouring CHILLCHECK_CACHE."""
    raw = os.environ.get("CHILLCHECK_CACHE")
    if raw:
        return Path(raw)
    return Path.home() / ".chillcheck-cache"