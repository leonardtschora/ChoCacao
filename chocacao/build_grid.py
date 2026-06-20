"""One-time build step.

Compute the ~25 km grid over metropolitan France, map every grid point to the
commune that contains it, deduplicate by commune, and write the result to
``data/grid_points.csv`` (committed to the repo so the runtime never has to do
this work).

Run with::

    uv run python -m chocacao.build_grid
"""

from __future__ import annotations

import csv
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

from chocacao.geocode import Commune, lookup_commune
from chocacao.grid import GridPoint, generate_grid

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_CSV = DATA_DIR / "grid_points.csv"
MAX_WORKERS = 8

_thread_local = threading.local()


def _session() -> requests.Session:
    """One requests.Session per worker thread (Sessions are not thread-safe)."""
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        _thread_local.session = session
    return session


def _resolve(point: GridPoint) -> Commune | None:
    return lookup_commune(_session(), point.lat, point.lon)


def build() -> None:
    points = generate_grid()
    total = len(points)
    print(f"Generated {total} grid points; resolving communes...", flush=True)

    communes: dict[str, Commune] = {}
    errors = 0
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(_resolve, pt): pt for pt in points}
        for future in as_completed(futures):
            done += 1
            try:
                commune = future.result()
            except Exception as exc:  # log the failure and keep going
                errors += 1
                print(f"  ! error on {futures[future]}: {exc}", flush=True)
                commune = None
            if commune is not None:
                communes.setdefault(commune.insee_code, commune)
            if done % 100 == 0 or done == total:
                print(
                    f"  {done}/{total} points processed, "
                    f"{len(communes)} unique communes, {errors} errors",
                    flush=True,
                )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = sorted(communes.values(), key=lambda c: (c.name, c.insee_code))
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["insee_code", "name", "postal_code", "lat", "lon"])
        for commune in rows:
            writer.writerow(
                [
                    commune.insee_code,
                    commune.name,
                    commune.postal_code,
                    f"{commune.lat:.6f}",
                    f"{commune.lon:.6f}",
                ]
            )
    print(f"Wrote {len(rows)} communes to {OUTPUT_CSV}", flush=True)


if __name__ == "__main__":
    build()
