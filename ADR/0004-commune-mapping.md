# 4. Mapping grid points to communes (and filtering France)

- **Status:** Accepted
- **Date:** 2026-06-20

## Context

Each on-land grid point must be turned into a named place (name, postal code,
coordinates). Points in the sea or abroad must be discarded.

## Decision

At **build time** (`chocacao/build_grid.py`), every grid point is reverse-geocoded
with `geo.api.gouv.fr/communes?lat=&lon=`:

- A point inside France returns its containing commune → we keep `code` (INSEE),
  `nom`, the first of `codesPostaux`, and the official `centre` coordinates.
- A point in the sea or abroad returns an **empty array** → discarded. This is
  the filtering mechanism; no separate coastline polygon is needed.

Results are **de-duplicated by INSEE code** (with a 25 km grid, two points rarely
land in the same commune, but large communes can be hit twice). The output is
written to `data/grid_points.csv`, committed to the repo so the runtime never
performs this work.

The build runs the ~2000 lookups concurrently (8 worker threads, one
`requests.Session` per thread), with retry/back-off on HTTP 429.

### Which coordinates do we store and query?

We store and later query the **commune `centre`** (official label point), not the
raw grid point. Rationale: the centre is a real, named location, makes the Google
Maps pin land on the town, and keeps the displayed coordinates meaningful. The
grid point is only ever a sampling device. The ≤25 km shift from grid point to
commune centre is immaterial for "hottest/coolest region" purposes.

## Consequences

- One CSV (~880 rows) is the single runtime data artifact; no build-time deps or
  network access are needed to run the app.
- Re-running the build refreshes the mapping if commune boundaries change.
- `data/grid_points.csv` columns: `insee_code, name, postal_code, lat, lon`.
