# 10. Adding the most populous communes, and a full commune index

- **Status:** Accepted
- **Date:** 2026-06-22

## Context

The 25 km grid samples France evenly, but a commune whose centre falls between
grid points is simply absent — including big cities. Users asked *"why can't I
see Paris?"*. Refining the grid is the wrong lever: it multiplies the open-meteo
query count, which we deliberately cap (see ADR 0005).

Separately, users want to look up an *arbitrary* commune by name (ADR 0011), which
needs a validated list of every commune.

## Decision

Both needs are met from **one authoritative source**: `geo.api.gouv.fr/communes`
with `fields=nom,code,codesPostaux,centre,population` returns all ~35 000 communes
in a single response, including the official INSEE **population**.

- **Top cities.** `chocacao/build_cities.py` takes the **288 most populous**
  communes and merges them into `data/grid_points.csv`, **bypassing the grid**.
  The merge de-duplicates by INSEE code, so a commune already hit by a grid point
  is fetched once. Result: 880 grid + 281 new cities = **1161 communes**.
- **Commune index.** `chocacao/build_index.py` writes **every** commune to
  `data/communes_index.csv` (`insee_code, name, postal_code, lat, lon,
  population`), used at runtime for the manual lookup.
- Shared fetch + parsing lives in `chocacao/communes.py`.

### Why the geo API, not the Wikipedia list

The request pointed at the Wikipedia *"communes les plus peuplées"* page. That
list is itself derived from INSEE legal populations — exactly what the geo API
serves. Pulling from the API gives INSEE codes, centres and postal codes directly
(no HTML scraping, no name→commune disambiguation) in the same schema the grid
build already uses. "Top N by population" reproduces the Wikipedia ranking without
its fragility.

### Why 288, and why metropolitan-only

288 is the size of the referenced list. We take the 288 most populous
**metropolitan** communes (INSEE code not starting with 97/98). The app's grid,
map bounds and basemap are metropolitan-only (ADR 0003/0008), so DROM-COM cities
(Saint-Denis de la Réunion, Fort-de-France, …) are out of scope and would land
off the map; dropping them keeps the set consistent. The cutoff is ~28 600
inhabitants.

## Consequences

- `data/grid_points.csv` is now "grid **+** top cities" (1161 rows); its schema is
  unchanged (`insee_code, name, postal_code, lat, lon`), so the runtime loader and
  the daily open-meteo fetch need no change — only ~12 batches instead of ~9.
- A new committed artifact, `data/communes_index.csv` (~34 700 rows, ~1.5 MB).
- Rebuild order matters: `build_index` (writes the index, with population) must run
  before `build_cities` (reads population from the index). Both are idempotent.
