"""Generate a roughly even ~25 km grid of points over metropolitan France.

The grid is the sampling mechanism used once, at build time, to discover which
French communes ChoCacao should include. Latitude rows are spaced by a constant
ground distance; within each row the longitude spacing is widened by 1/cos(lat)
so the east-west ground spacing stays close to the target everywhere.

Ocean and foreign points are *not* filtered here: they are dropped later because
they map to no French commune (see :mod:`chocacao.geocode`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Bounding box of metropolitan France, including Corsica and excluding overseas
# territories (DROM-COM). Margins are generous on purpose; everything outside
# French land is discarded by the commune lookup.
LAT_MIN = 41.3
LAT_MAX = 51.15
LON_MIN = -5.2
LON_MAX = 9.65

# 1 degree of latitude is ~111.32 km everywhere.
KM_PER_DEG_LAT = 111.32

DEFAULT_SPACING_KM = 25.0


@dataclass(frozen=True)
class GridPoint:
    lat: float
    lon: float


def generate_grid(spacing_km: float = DEFAULT_SPACING_KM) -> list[GridPoint]:
    """Return the list of grid points covering the France bounding box."""
    points: list[GridPoint] = []
    lat_step = spacing_km / KM_PER_DEG_LAT
    n_rows = math.floor((LAT_MAX - LAT_MIN) / lat_step) + 1
    for i in range(n_rows):
        lat = LAT_MIN + i * lat_step
        km_per_deg_lon = KM_PER_DEG_LAT * math.cos(math.radians(lat))
        lon_step = spacing_km / max(km_per_deg_lon, 1e-6)
        n_cols = math.floor((LON_MAX - LON_MIN) / lon_step) + 1
        for j in range(n_cols):
            lon = LON_MIN + j * lon_step
            points.append(GridPoint(round(lat, 6), round(lon, 6)))
    return points
