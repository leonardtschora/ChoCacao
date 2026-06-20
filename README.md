# 🍫 ChoCacao

**Find the 100 hottest and 100 coolest *communes* in metropolitan France for any
hour in the week ahead.** (The interface is in French — it's built for French
users.)

France packs Atlantic, Mediterranean and Alpine climates into one country — 200 km
can mean ±10 °C. When the next heatwave hits, ChoCacao shows you exactly where to
chase the sun or escape the heat.

Pick a **date** (today up to one week ahead) and an **hour** (default 16:00, the
usual daily peak). ChoCacao queries [Open-Meteo](https://open-meteo.com/) for ~880
communes on a 25 km grid and shows the extremes as two **sortable** tables
(commune, département, temperature, and difference to the national median). An
**IGN map** plots the extremes, coloured by temperature; **click a point** to open
a panel with its detail and a 48-hour temperature curve.

## How it works

```
                build time (once)                         run time
   ┌───────────────────────────────────────┐   ┌──────────────────────────────┐
   │ 25 km grid over France  (grid.py)      │   │ load data/grid_points.csv    │
   │   2036 points                          │   │ fetch hourly temps for the   │
   │      │ reverse-geocode each point      │   │   whole week (open-meteo,    │
   │      ▼ (geo.api.gouv.fr, geocode.py)   │   │   batched, cached daily)     │
   │ keep points inside France, dedupe      │   │ slice chosen date+hour       │
   │   880 communes                         │   │ rank → top 100 cold / hot    │
   │      ▼                                 │   │ sortable tables + IGN map    │
   │ data/grid_points.csv  (committed)      │   │   + click→detail dialog      │
   └───────────────────────────────────────┘   └──────────────────────────────┘
```

The grid → commune mapping is **precomputed once** and committed as
`data/grid_points.csv`, so the running app needs no build-time work or city
database. See [`ADR/`](ADR/) for the full reasoning behind every decision.

## Project layout

| Path | Purpose |
| --- | --- |
| `streamlit_app.py` | The Streamlit app (entry point). |
| `chocacao/grid.py` | Generate the ~25 km grid over France. |
| `chocacao/geocode.py` | Reverse-geocode a point to its commune. |
| `chocacao/build_grid.py` | One-time build of `data/grid_points.csv`. |
| `chocacao/forecast.py` | Batched, rate-limited open-meteo fetching. |
| `chocacao/departements.py` | INSEE-code → département name map. |
| `data/grid_points.csv` | Precomputed grid → commune table (880 rows). |
| `ADR/` | Architecture Decision Records. |

## Run locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                   # create the env, install deps
uv run streamlit run streamlit_app.py     # open http://localhost:8501
```

### Rebuild the grid (optional)

Only needed to regenerate the dataset (makes ~2000 calls to geo.api.gouv.fr):

```bash
uv run python -m chocacao.build_grid
```

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
- Basemap: [IGN / Géoplateforme](https://geoservices.ign.fr/) (Plan IGN vector
  style, rendered by MapLibre).

Coverage is metropolitan France including Corsica; overseas territories are out
of scope. Temperatures are forecasts, coloured on a diverging blue→red scale
centred on the national median (blue = cooler, red = hotter).
