# 2. Data sources: open-meteo and geo.api.gouv.fr

- **Status:** Accepted
- **Date:** 2026-06-20

## Context

ChoCacao needs (a) temperature forecasts for arbitrary coordinates and (b) a way
to turn coordinates into a named French place with a postal code.

## Decision

- **Forecasts: [Open-Meteo](https://open-meteo.com/).** Mandated by the spec. Free
  for non-commercial use, no API key, supports `temperature_2m` at 1 h
  granularity, up to 16 forecast days, and — crucially — **multiple coordinates
  in a single request** (comma-separated `latitude`/`longitude`). We use
  `forecast_days`, `timezone=Europe/Paris`, and `hourly=temperature_2m`.

- **Coordinate → commune: [geo.api.gouv.fr](https://geo.api.gouv.fr/).** The
  official French government geocoding API. Its `/communes?lat=&lon=` endpoint
  returns the commune that *contains* a point, with `nom`, `codesPostaux` and the
  official `centre` (label point). No key, authoritative, France-specific.

## Why not alternatives

- *OSM/Nominatim* for reverse geocoding: stricter rate limits and a usage policy
  that discourages bulk gridded queries; geo.api.gouv.fr is purpose-built for FR.
- *Downloading the full communes polygon set + local point-in-polygon*: more
  robust offline but pulls a large GeoJSON and a `shapely` dependency for a job
  we only run once. The API gives the same result with no heavy dependency.

## Consequences

- Two external dependencies, but each is used in a context that suits it:
  geo.api.gouv.fr only at **build time**, open-meteo only at **run time**.
- Attribution is required for open-meteo (CC BY 4.0); shown in the app footer.
- A single API call returning **no commune** is exactly our signal that a grid
  point is in the sea or abroad — this powers the filtering (see ADR 0004).
