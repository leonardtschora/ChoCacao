"""Fetch the full list of French communes from geo.api.gouv.fr.

Two products are derived from one bulk download:

* the **most populous communes** — added to the daily-fetched set so big cities
  (Paris, Lyon, …) appear on the map even though a 25 km grid would skip them
  (see :mod:`chocacao.build_cities`);
* the **commune index** — every metropolitan commune, used at runtime to validate
  and resolve a user's manual lookup (see :mod:`chocacao.build_index`).

Population comes straight from the official source (INSEE legal populations served
by geo.api.gouv.fr), so "top N by population" matches the Wikipedia "communes les
plus peuplées" list without scraping any HTML.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests

GEO_API_URL = "https://geo.api.gouv.fr/communes"
REQUEST_TIMEOUT = 60  # one big response (~35k communes)
MAX_RETRIES = 4


@dataclass(frozen=True)
class CommuneRecord:
    insee_code: str
    name: str
    postal_code: str
    lat: float  # official commune centre (label point)
    lon: float
    population: int


def _is_metropolitan(insee_code: str) -> bool:
    """True for metropolitan France (incl. Corsica 2A/2B), excluding DROM-COM.

    Overseas INSEE codes start with 97 or 98; everything else is metropolitan.
    The app's grid, map bounds and basemap are metropolitan-only, so out-of-scope
    overseas communes are dropped here to stay consistent.
    """
    return not insee_code.startswith(("97", "98"))


def fetch_all_communes(session: requests.Session) -> list[CommuneRecord]:
    """Download every metropolitan commune (with population and centre), sorted by name."""
    params = {
        "fields": "nom,code,codesPostaux,centre,population",
        "format": "json",
    }
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(GEO_API_URL, params=params, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 429:
                time.sleep(2**attempt)
                continue
            resp.raise_for_status()
            data = resp.json()
            break
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            time.sleep(2**attempt)
    else:
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("geo.api.gouv.fr returned no commune data")

    records: list[CommuneRecord] = []
    for entry in data:
        code = entry.get("code", "")
        coords = (entry.get("centre") or {}).get("coordinates")
        population = entry.get("population")
        if not code or not coords or not population or not _is_metropolitan(code):
            continue
        postal_codes = entry.get("codesPostaux") or [""]
        records.append(
            CommuneRecord(
                insee_code=code,
                name=entry.get("nom", ""),
                postal_code=postal_codes[0],
                lat=float(coords[1]),
                lon=float(coords[0]),
                population=int(population),
            )
        )
    records.sort(key=lambda c: (c.name, c.insee_code))
    return records


def top_by_population(communes: list[CommuneRecord], n: int) -> list[CommuneRecord]:
    """Return the ``n`` most populous communes (ties broken by INSEE code)."""
    ranked = sorted(communes, key=lambda c: (-c.population, c.insee_code))
    return ranked[:n]
