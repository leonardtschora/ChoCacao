# 3. The 25 km sampling grid

- **Status:** Accepted
- **Date:** 2026-06-20

## Context

There are ~35 000 communes in metropolitan France — far too many to query at
run time. The spec proposes a 25 km grid (~1600 points over a 1000×1000 km box,
of which ~1000 fall on French land).

## Decision

Generate a grid over the bounding box of metropolitan France
(`lat 41.3–51.15`, `lon -5.2–9.65`), which **includes Corsica** and excludes the
overseas territories (DROM-COM), since the spec targets *metropolitan* France.

To keep spacing close to a true 25 km on the ground despite meridian
convergence:

- Latitude rows are stepped by a constant `25 / 111.32 ≈ 0.225°`.
- Within each row, longitude is stepped by `25 / (111.32 · cos(lat))°`, which
  widens the angular step as we go north so the east-west *ground* distance stays
  ~25 km everywhere.

No coastline/border filtering is done geometrically here — points outside France
are dropped later because they map to no commune (see ADR 0004).

## Result

The bounding box yields **2036 grid points**; **880 unique communes** remain
after mapping and de-duplication. (The remaining ~1150 points fall in the sea or
in neighbouring countries.) This is in line with the spec's "~1000 points"
estimate and is comfortably queryable.

## Consequences

- Coverage is even and country-wide; some small coastal/island communes between
  grid lines are not represented — an accepted approximation of a sampling grid.
- Changing `spacing_km` re-scales the whole grid; the build is deterministic.
