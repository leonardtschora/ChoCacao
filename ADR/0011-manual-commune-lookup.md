# 11. On-demand manual commune lookup

- **Status:** Accepted
- **Date:** 2026-06-22

## Context

The daily set (~1160 communes) can't cover every wish. Users want to check a
specific small commune — *"Can I see La Tremblade?"* — that the grid skips and
that isn't populous enough to be a top-288 city. Adding every requested commune to
the daily batch would grow it without bound for the benefit of one user.

## Decision

Add a **validated, on-demand** lookup, separate from the daily set.

- **Validation by index.** A `st.multiselect` over `data/communes_index.csv`
  (every metropolitan commune, ADR 0010), labelled `"Nom (code postal)"`. The user
  can only pick real communes; typing filters the list (autocomplete).
- **Runtime fetch, not stored.** A chosen commune that is **not** already in the
  daily set is fetched from open-meteo on demand (`forecast.fetch_one`, a
  single-location call) and merged into the in-memory readings. It is **never**
  written to `data/grid_points.csv`.
- **Cached, not persisted.** The fetch is wrapped in `st.cache_data` keyed by the
  commune and the daily `period_key`, so repeated reruns (and other users asking
  for the same commune) don't refetch. The cache is in-memory and rolls over daily
  — caching for performance, not persistence.
- **Surfaced.** Chosen communes get a `📍` highlight panel (air, apparent, écart to
  the median, and rank *N* / total), a `📍` flag in the table so they survive a
  sort, and a larger white-ringed marker on the map.

The daily cache (`get_forecast`) is **never mutated**: manual series go into copied
temperature views, so a manual lookup can't leak into other sessions' data.

## Consequences

- One extra open-meteo call per *new* manually-requested commune per day — bounded
  by `MANUAL_MAX = 10` selections and shared via the cache.
- The runtime now depends on `data/communes_index.csv` as well as
  `data/grid_points.csv`.
- The search box ships ~34 700 options to the browser. Acceptable today; if it ever
  feels heavy, switch to a server-side text filter that returns only matches.
