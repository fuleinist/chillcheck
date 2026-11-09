"""Place lookup.

Primary source is OpenStreetMap Nominatim. It handles a state suffix and a
postcode, which the Open-Meteo geocoder does not. Open-Meteo geocoding stays as
a fallback.

Nominatim asks for one request per second and a User-Agent that names the
application. Both rules are honoured here.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from .config import GEOCODE_URL, NOMINATIM_URL, PREFERRED_COUNTRY, USER_AGENT

MIN_INTERVAL_S = 1.05
_last_request = 0.0


def _throttle() -> None:
    global _last_request
    wait = MIN_INTERVAL_S - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()


def _get_json(url: str, timeout: float = 30.0) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def normalise_nominatim(raw: dict) -> dict:
    """Convert one Nominatim record to the shape this package uses."""
    address = raw.get("address") or {}
    name = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("suburb")
        or address.get("municipality")
        or (raw.get("display_name") or "").split(",")[0]
    )
    return {
        "name": name,
        "admin1": address.get("state") or address.get("region"),
        "country": address.get("country"),
        "country_code": (address.get("country_code") or "").upper(),
        "latitude": float(raw.get("lat")),
        "longitude": float(raw.get("lon")),
        "elevation": None,
        "timezone": None,
        "display_name": raw.get("display_name"),
        "kind": raw.get("type"),
    }


def _nominatim(query: str, count: int, country: str | None) -> list[dict]:
    params = {
        "format": "jsonv2",
        "limit": max(1, min(int(count), 20)),
        "addressdetails": 1,
        "q": query,
    }
    if country:
        params["countrycodes"] = country.lower()
    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
    _throttle()
    payload = _get_json(url)
    if not isinstance(payload, list):
        return []
    return [normalise_nominatim(item) for item in payload]


def _openmeteo(query: str, count: int) -> list[dict]:
    params = {
        "name": query,
        "count": max(1, min(int(count), 20)),
        "language": "en",
        "format": "json",
    }
    url = f"{GEOCODE_URL}?{urllib.parse.urlencode(params)}"
    payload = _get_json(url)
    results = (payload or {}).get("results") or []
    out = []
    for item in results:
        out.append(
            {
                "name": item.get("name"),
                "admin1": item.get("admin1"),
                "country": item.get("country"),
                "country_code": (item.get("country_code") or "").upper(),
                "latitude": item.get("latitude"),
                "longitude": item.get("longitude"),
                "elevation": item.get("elevation"),
                "timezone": item.get("timezone"),
                "display_name": None,
                "kind": None,
            }
        )
    return out


def geocode(query: str, count: int = 5, country: str | None = None) -> list[dict]:
    """Return places that match ``query``.

    The preferred country is tried first. A global search follows when that
    returns nothing, so a user outside the default country still gets results.
    """
    text = (query or "").strip()
    if len(text) < 2:
        return []

    preferred = PREFERRED_COUNTRY if country is None else country
    preferred = (preferred or "").strip().upper()

    hits: list[dict] = []
    if preferred:
        try:
            hits = _nominatim(text, count, preferred)
        except Exception:
            hits = []
    if not hits:
        try:
            hits = _nominatim(text, count, None)
        except Exception:
            hits = []
    if not hits:
        try:
            hits = _openmeteo(text, count)
        except Exception:
            hits = []
    return [hit for hit in hits if hit.get("latitude") is not None]


def describe_place(hit: dict) -> str:
    """Return a short label for a place record."""
    parts = [hit.get("name"), hit.get("admin1"), hit.get("country")]
    seen: list[str] = []
    for part in parts:
        if part and part not in seen:
            seen.append(part)
    return ", ".join(seen)