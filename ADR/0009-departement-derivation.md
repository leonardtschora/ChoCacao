# 9. Deriving the département from the INSEE code

- **Status:** Accepted
- **Date:** 2026-06-20

## Context

The tables and the map detail need each commune's département. The precomputed
`data/grid_points.csv` stores the INSEE code but not the département.

## Decision

Derive the département **at load time** instead of re-running the grid build:

- The département **code** is the first two characters of the INSEE code
  (`"75056" → "75"`, `"2A031" → "2A"`). This mapping is exact and deterministic.
- The département **name** comes from `chocacao/departements.py`, a static
  `code → name` dict generated once from `geo.api.gouv.fr/departements` (a single
  authoritative API call, including Corsica's `2A`/`2B`).

## Why not store it in the CSV / re-run the build

The département is 100 % derivable from data we already have, so re-querying ~2000
points just to add a redundant column would be wasteful and risk drift. Deriving
it on load keeps a single source of truth (the INSEE code) and needs no network.

## Consequences

- No rebuild required; `load_places()` attaches `departement_code`/`name`.
- If France's département list ever changes, regenerate `departements.py` from the
  same one-call endpoint.
