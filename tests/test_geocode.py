"""Tests for place lookup helpers. No network calls."""

from __future__ import annotations

from chillcheck.geocode import describe_place, normalise_nominatim


def test_normalise_nominatim_city():
    raw = {
        "lat": "-33.2820463",
        "lon": "149.0971567",
        "type": "administrative",
        "display_name": "Orange, New South Wales, 2800, Australia",
        "address": {
            "city": "Orange",
            "state": "New South Wales",
            "country": "Australia",
            "country_code": "au",
        },
    }
    place = normalise_nominatim(raw)
    assert place["name"] == "Orange"
    assert place["admin1"] == "New South Wales"
    assert place["country_code"] == "AU"
    assert place["latitude"] == -33.2820463
    assert place["longitude"] == 149.0971567


def test_normalise_nominatim_postcode_falls_back_to_display_name():
    raw = {
        "lat": "-33.28",
        "lon": "149.05",
        "type": "postal_code",
        "display_name": "2800, Orange, New South Wales, Australia",
        "address": {"postcode": "2800", "state": "New South Wales", "country_code": "au"},
    }
    place = normalise_nominatim(raw)
    assert place["name"] == "2800"
    assert place["admin1"] == "New South Wales"


def test_describe_place_drops_repeats():
    place = {"name": "Sydney", "admin1": "New South Wales", "country": "Australia"}
    assert describe_place(place) == "Sydney, New South Wales, Australia"


def test_describe_place_skips_missing_parts():
    place = {"name": "Huonville", "admin1": None, "country": "Australia"}
    assert describe_place(place) == "Huonville, Australia"