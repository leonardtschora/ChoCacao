"""One-time build step: fold the most populous communes into the fetch set.

A 25 km grid skips big cities whose centre falls between sample points ("why
can't I see Paris?"). Rather than refine the grid — which would multiply the
open-meteo query count — we add the ``TOP_N`` most populous communes directly to
``data/grid_points.csv``, bypassing the grid. Communes already present (a grid
point landed inside them) are kept once: the merge de-duplicates by INSEE code.

Reads the population from ``data/communes_index.csv`` (built by
:mod:`chocacao.build_index`), so no extra network call is needed.

Run *after* the index build::

    uv run python -m chocacao.build_index   # produces communes_index.csv
    uv run python -m chocacao.build_cities  # merges top cities into grid_points.csv
"""

from __future__ import annotations

import csv
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INDEX_CSV = DATA_DIR / "communes_index.csv"
GRID_CSV = DATA_DIR / "grid_points.csv"

# 288 = the size of the Wikipedia "communes de France les plus peuplées" list the
# users referenced; metropolitan-only, matching the app's scope.
TOP_N = 288

# Schema shared with the grid build (chocacao.build_grid) and the runtime loader.
FIELDNAMES = ["insee_code", "name", "postal_code", "lat", "lon"]


def _load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def build() -> None:
    index = _load_rows(INDEX_CSV)
    index.sort(key=lambda r: (-int(r["population"]), r["insee_code"]))
    top_cities = index[:TOP_N]

    # Start from the existing grid communes; add cities the grid missed.
    communes: dict[str, dict[str, str]] = {}
    for row in _load_rows(GRID_CSV):
        communes[row["insee_code"]] = {k: row[k] for k in FIELDNAMES}

    grid_count = len(communes)
    added = 0
    for row in top_cities:
        if row["insee_code"] not in communes:
            communes[row["insee_code"]] = {k: row[k] for k in FIELDNAMES}
            added += 1

    rows = sorted(communes.values(), key=lambda r: (r["name"], r["insee_code"]))
    with GRID_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    overlap = len(top_cities) - added
    print(
        f"Grid communes: {grid_count}; top-{TOP_N} cities: {len(top_cities)} "
        f"({overlap} already in grid); added {added}.",
        flush=True,
    )
    print(f"Wrote {len(rows)} communes to {GRID_CSV}", flush=True)


if __name__ == "__main__":
    build()
