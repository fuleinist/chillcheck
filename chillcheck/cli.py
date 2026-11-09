"""Command line interface for chillcheck."""

from __future__ import annotations

import argparse
import json
import sys

from .climate import ClimateError
from .geocode import describe_place, geocode
from .report import assess, to_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chillcheck",
        description="Winter chill calculator for fruit trees.",
    )
    parser.add_argument("--place", help="Place name or postcode to look up")
    parser.add_argument("--country", help="Two letter country code for place search, for example AU")
    parser.add_argument("--lat", type=float, help="Latitude in decimal degrees")
    parser.add_argument("--lon", type=float, help="Longitude in decimal degrees")
    parser.add_argument(
        "--years", type=int, default=30, help="Number of past seasons (5 to 40)"
    )
    parser.add_argument(
        "--horizon", type=int, default=2050, help="Projection year (up to 2050)"
    )
    parser.add_argument("--crops", help="Comma separated crop filter, for example apple,pear")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print JSON")
    parser.add_argument("--refresh", action="store_true", help="Ignore the cache")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    lat, lon, name = args.lat, args.lon, None
    if lat is None or lon is None:
        if not args.place:
            print("Give --place, or give both --lat and --lon.", file=sys.stderr)
            return 2
        try:
            hits = geocode(args.place, count=1, country=args.country)
        except Exception as exc:
            print(f"Geocoding failed: {exc}", file=sys.stderr)
            return 1
        if not hits:
            print(f"No place found for {args.place!r}.", file=sys.stderr)
            return 1
        hit = hits[0]
        lat, lon = hit["latitude"], hit["longitude"]
        name = describe_place(hit)

    crops = [c.strip() for c in args.crops.split(",")] if args.crops else None

    try:
        report = assess(
            lat,
            lon,
            name=name,
            years=args.years,
            horizon=args.horizon,
            crops=crops,
            refresh=args.refresh,
        )
    except ClimateError as exc:
        print(f"Weather data failed: {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(report, indent=2))
    else:
        print(to_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())