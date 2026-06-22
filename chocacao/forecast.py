"""Fetch hourly 2 m temperature forecasts for the ChoCacao places from open-meteo.

Requests are batched (many coordinates per call) so the whole of France is
covered in a handful of HTTP calls. The Streamlit layer wraps :func:`fetch_forecast`
in ``st.cache_data`` so the API is hit only once per refresh window, regardless
of how many users are connected — this is what caps the daily query count.
"""

from __future__ import annotations

import csv
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from chocacao.departements import DEPARTEMENTS

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = "Europe/Paris"
FORECAST_DAYS = 8  # today + up to 7 days ahead ("up to 1 week ahead")
BATCH_SIZE = 100  # keep request URLs comfortably under server length limits
REQUEST_TIMEOUT = 30
# open-meteo's free tier limits the number of *locations* per minute (~600).
# We may need to wait out a 429 (the minute window resets), so retry with
# backoff and honour the Retry-After header when present.
MAX_RETRIES = 6
INTER_BATCH_PAUSE = 0.4  # gentle smoothing between batches
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_CSV = DATA_DIR / "grid_points.csv"
INDEX_CSV = DATA_DIR / "communes_index.csv"


@dataclass(frozen=True)
class Place:
    insee_code: str
    name: str
    postal_code: str
    departement_code: str
    departement_name: str
    lat: float
    lon: float


def _row_to_place(row: dict[str, str]) -> Place:
    """Build a Place from a CSV row, deriving the département from the INSEE code."""
    insee = row["insee_code"]
    dept_code = insee[:2]
    return Place(
        insee_code=insee,
        name=row["name"],
        postal_code=row["postal_code"],
        departement_code=dept_code,
        departement_name=DEPARTEMENTS.get(dept_code, ""),
        lat=float(row["lat"]),
        lon=float(row["lon"]),
    )


def load_places() -> list[Place]:
    """Load the precomputed grid + top-cities → commune table from disk.

    The département (code + name) is derived from the INSEE code at load time
    (see :mod:`chocacao.departements`), so it stays in sync without re-running
    the build.
    """
    with DATA_CSV.open(encoding="utf-8") as handle:
        return [_row_to_place(row) for row in csv.DictReader(handle)]


def load_commune_index() -> list[Place]:
    """Load every metropolitan commune (data/communes_index.csv) for manual lookups.

    Returns the same Place type as :func:`load_places`; the extra ``population``
    column in the index file is ignored. Rows are sorted by name (as written by
    :mod:`chocacao.build_index`) so the search box reads naturally.
    """
    with INDEX_CSV.open(encoding="utf-8") as handle:
        return [_row_to_place(row) for row in csv.DictReader(handle)]


def fetch_one(place: Place) -> tuple[list[str], list[float | None], list[float | None]]:
    """Fetch a single commune's forecast (for a runtime, ad-hoc manual lookup).

    Returns ``(times, temps, apparent)`` for that one commune, aligned the same
    way as :func:`fetch_forecast`. Used for user-requested communes that are not
    in the daily-cached set — fetched on demand and never written to disk.
    """
    times, temps, apparent = fetch_forecast([place])
    return times, temps.get(place.insee_code, []), apparent.get(place.insee_code, [])


def _chunks(seq: Sequence[Place], size: int) -> Iterator[Sequence[Place]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def _request_json(session: requests.Session, params: dict[str, Any]) -> Any:
    """GET one batch, retrying through rate limits (HTTP 429)."""
    last_resp: requests.Response | None = None
    for attempt in range(MAX_RETRIES):
        resp = session.get(OPEN_METEO_URL, params=params, timeout=REQUEST_TIMEOUT)
        last_resp = resp
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            # The per-minute window resets within ~60s; wait it out.
            wait = float(retry_after) if retry_after else min(60.0, 15.0 * (attempt + 1))
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    if last_resp is not None:
        last_resp.raise_for_status()
    raise RuntimeError("open-meteo request failed without a response")


def fetch_forecast(
    places: Sequence[Place],
) -> tuple[list[str], dict[str, list[float | None]], dict[str, list[float | None]]]:
    """Fetch forecasts for all places.

    Returns ``(times, temps, apparent)`` where ``times`` is the shared hourly
    timeline in local Europe/Paris time (e.g. ``"2026-06-20T16:00"``); ``temps``
    maps each commune's INSEE code to its 2 m air temperature list and
    ``apparent`` to its apparent ("feels-like") temperature list, both aligned
    with ``times``.
    """
    session = requests.Session()
    times: list[str] = []
    temps: dict[str, list[float | None]] = {}
    apparent: dict[str, list[float | None]] = {}
    batches = list(_chunks(places, BATCH_SIZE))
    for i, batch in enumerate(batches):
        params: dict[str, Any] = {
            "latitude": ",".join(f"{p.lat:.5f}" for p in batch),
            "longitude": ",".join(f"{p.lon:.5f}" for p in batch),
            "hourly": "temperature_2m,apparent_temperature",
            "timezone": TIMEZONE,
            "forecast_days": FORECAST_DAYS,
        }
        payload = _request_json(session, params)
        # A single-location request returns an object, not a list.
        entries = [payload] if isinstance(payload, dict) else payload
        for place, entry in zip(batch, entries, strict=False):
            hourly = entry.get("hourly", {})
            if not times:
                times = hourly.get("time", [])
            temps[place.insee_code] = hourly.get("temperature_2m", [])
            apparent[place.insee_code] = hourly.get("apparent_temperature", [])
        if i < len(batches) - 1:
            time.sleep(INTER_BATCH_PAUSE)
    return times, temps, apparent
