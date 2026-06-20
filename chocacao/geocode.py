"""Map coordinates to the French commune that contains them.

Uses the official French government geo API (geo.api.gouv.fr). A point falling
in the ocean or in a neighbouring country maps to no commune and is therefore
filtered out of the grid automatically.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests

GEO_API_URL = "https://geo.api.gouv.fr/communes"
REQUEST_TIMEOUT = 15
MAX_RETRIES = 4


@dataclass(frozen=True)
class Commune:
    insee_code: str
    name: str
    postal_code: str
    lat: float  # commune centre (official label point)
    lon: float


def lookup_commune(session: requests.Session, lat: float, lon: float) -> Commune | None:
    """Return the commune containing (lat, lon), or None if outside France."""
    params = {
        "lat": f"{lat:.6f}",
        "lon": f"{lon:.6f}",
        "fields": "nom,code,codesPostaux,centre",
        "format": "json",
    }
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = session.get(GEO_API_URL, params=params, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 429:  # rate limited: back off and retry
                time.sleep(2**attempt)
                continue
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return None
            entry = data[0]
            coords = (entry.get("centre") or {}).get("coordinates")
            if not coords:
                return None
            postal_codes = entry.get("codesPostaux") or [""]
            return Commune(
                insee_code=entry.get("code", ""),
                name=entry.get("nom", ""),
                postal_code=postal_codes[0],
                lat=float(coords[1]),
                lon=float(coords[0]),
            )
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            time.sleep(2**attempt)
    if last_exc is not None:
        raise last_exc
    return None
