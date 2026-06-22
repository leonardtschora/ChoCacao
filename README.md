# 🍫 ChoCacao

**Find the hottest and coolest *communes* in metropolitan France for any hour in
the week ahead.** (The interface is in French — it's built for French users.)

France packs Atlantic, Mediterranean and Alpine climates into one country — 200 km
can mean ±10 °C. When the next heatwave hits, ChoCacao shows you exactly where to
chase the sun or escape the heat.

Pick a **date** (today up to one week ahead) and an **hour** (default 16:00, the
usual daily peak). ChoCacao queries [Open-Meteo](https://open-meteo.com/) for
**~1160 communes** — a 25 km grid **plus the 288 most populous communes** so big
cities like Paris show up — and presents them all in one **sortable** table
(commune, département, air temperature, apparent "feels-like" temperature, and
difference to the national median): ~30 rows at a glance, sort to surface either
extreme. A **Mesure** toggle switches the whole view — table, median and map —
between air and apparent temperature. A **map** plots every commune on a single
diverging scale (deep-blue coolest → green at the median → deep-red hottest);
**click a point** for its detail and a 48-hour curve.

**Need a commune that isn't sampled?** Search any of France's ~35 000 communes by
name (e.g. *La Tremblade*) and ChoCacao fetches its forecast on demand, highlights
it (📍, with its rank in the field) and plots it — without adding it to the daily
dataset.

## How it works

```
                build time (once)                          run time
   ┌────────────────────────────────────────┐   ┌──────────────────────────────┐
   │ 25 km grid over France (grid.py)        │   │ load data/grid_points.csv    │
   │   2036 points → reverse-geocode         │   │ fetch hourly temps for the   │
   │   (geo.api.gouv.fr) → 880 communes      │   │   whole week (open-meteo,    │
   │        +                                │   │   batched, cached daily)     │
   │ 288 most populous communes              │   │ slice chosen date+hour       │
   │   (build_cities.py, dedupe by INSEE)    │   │ colour all on one diverging  │
   │      ▼  1161 communes                   │   │   scale → sortable table +   │
   │ data/grid_points.csv      (committed)   │   │   full map + click→detail    │
   │ data/communes_index.csv   (committed) ──┼──▶│ name search → on-demand fetch│
   │   every commune, for manual lookups     │   │   (not stored)               │
   └────────────────────────────────────────┘   └──────────────────────────────┘
```

The grid → commune mapping and the commune index are **precomputed once** and
committed (`data/grid_points.csv`, `data/communes_index.csv`), so the running app
needs no build-time work or city database. See [`ADR/`](ADR/) for the full
reasoning behind every decision.

## Project layout

| Path | Purpose |
| --- | --- |
| `streamlit_app.py` | The Streamlit app (entry point). |
| `chocacao/grid.py` | Generate the ~25 km grid over France. |
| `chocacao/geocode.py` | Reverse-geocode a point to its commune. |
| `chocacao/communes.py` | Fetch the full commune list (population) from geo.api.gouv.fr. |
| `chocacao/build_grid.py` | One-time build of the grid communes. |
| `chocacao/build_index.py` | One-time build of `data/communes_index.csv` (every commune). |
| `chocacao/build_cities.py` | Merge the 288 most populous communes into `grid_points.csv`. |
| `chocacao/forecast.py` | Batched, rate-limited open-meteo fetching (+ on-demand single fetch). |
| `chocacao/departements.py` | INSEE-code → département name map. |
| `data/grid_points.csv` | Precomputed fetch set: grid + top cities (1161 rows). |
| `data/communes_index.csv` | Every metropolitan commune, for the manual lookup (~34 700 rows). |
| `ADR/` | Architecture Decision Records. |

## Run locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                   # create the env, install deps
uv run streamlit run streamlit_app.py     # open http://localhost:8501
```

### Rebuild the data (optional)

Only needed to regenerate the committed datasets. The grid build makes ~2000
calls to geo.api.gouv.fr; the index/cities builds make one bulk call each.

```bash
uv run python -m chocacao.build_grid     # grid → commune table (~2000 calls)
uv run python -m chocacao.build_index    # every commune → data/communes_index.csv
uv run python -m chocacao.build_cities   # merge top-288 cities into grid_points.csv
```

Run `build_index` before `build_cities` (the latter reads population from the
index). `build_cities` is idempotent — it de-duplicates by INSEE code.

### Quality checks

```bash
uv run ruff check . && uv run ruff format --check . && uv run pyright
```

## Deploy (Streamlit Community Cloud)

1. Push this repo to GitHub.
2. On [share.streamlit.io](https://share.streamlit.io), create an app pointing at
   `streamlit_app.py`. Dependencies install from `requirements.txt`.

## Data & attribution

- Weather: [Open-Meteo.com](https://open-meteo.com/) — 2 m air temperature,
  hourly, local time (CC BY 4.0).
- Communes & départements: [geo.api.gouv.fr](https://geo.api.gouv.fr/) (French
  government).
- Basemap: © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors,
  © [CARTO](https://carto.com/) (Voyager style, French labels).

Coverage is metropolitan France including Corsica; overseas territories are out
of scope. Temperatures are forecasts, coloured on a diverging blue→red scale
centred on the national median (blue = cooler, red = hotter).
