"""One-time build step: the commune index for manual lookups.

Downloads every metropolitan commune from geo.api.gouv.fr and writes them to
``data/communes_index.csv`` (committed). The runtime uses this index to offer a
validated commune search box and to resolve a chosen commune's coordinates,
without shipping a heavy OSM database.

Run with::

    uv run python -m chocacao.build_index
"""

from __future__ import annotations

import csv
from pathlib import Path

import requests

from chocacao.communes import fetch_all_communes

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_CSV = DATA_DIR / "communes_index.csv"


def build() -> None:
    session = requests.Session()
    print("Downloading the full commune list from geo.api.gouv.fr…", flush=True)
    communes = fetch_all_communes(session)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["insee_code", "name", "postal_code", "lat", "lon", "population"])
        for c in communes:
            writer.writerow(
                [c.insee_code, c.name, c.postal_code, f"{c.lat:.6f}", f"{c.lon:.6f}", c.population]
            )
    print(f"Wrote {len(communes)} communes to {OUTPUT_CSV}", flush=True)


if __name__ == "__main__":
    build()
