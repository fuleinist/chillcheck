"""JSON API for the web UI."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .climate import ClimateError, clamp_years
from .geocode import geocode
from .report import assess

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(
    title="chillcheck",
    version=__version__,
    description="Winter chill calculator for fruit trees.",
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/api/geocode")
def api_geocode(
    q: str = Query(..., min_length=2),
    count: int = 5,
    country: str | None = None,
) -> dict:
    try:
        return {"results": geocode(q, count=count, country=country)}
    except Exception as exc:  # network or parse failure
        raise HTTPException(status_code=502, detail=f"geocoding failed: {exc}") from exc


@app.get("/api/assess")
def api_assess(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    name: str | None = None,
    years: int = 30,
    horizon: int = 2050,
    crops: str | None = None,
    refresh: bool = False,
) -> dict:
    crop_list = [c.strip() for c in crops.split(",")] if crops else None
    try:
        return assess(
            lat,
            lon,
            name=name,
            years=clamp_years(years),
            horizon=horizon,
            crops=crop_list,
            refresh=refresh,
        )
    except ClimateError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/")
def index() -> FileResponse:
    page = WEB_DIR / "index.html"
    if not page.exists():
        raise HTTPException(status_code=404, detail="web UI not installed")
    return FileResponse(page)


if WEB_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")