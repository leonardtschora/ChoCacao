# 🍫 ChoCacao

**Find the 20 hottest and 20 coolest places in metropolitan France for any hour
in the week ahead.**

France packs Atlantic, Mediterranean and Alpine climates into one country — 200 km
can mean ±10 °C. When the next heatwave hits, ChoCacao shows you exactly where to
chase the sun or escape the heat.

Pick a **date** (today up to one week ahead) and an **hour** (default 16:00, the
usual daily peak). ChoCacao queries [Open-Meteo](https://open-meteo.com/) for ~880
communes spread on a 25 km grid and shows the temperature extremes as two tables.
**Click any place name** to open it, pinned, in Google Maps.

## How it works

```
                build time (once)                         run time
   ┌───────────────────────────────────────┐   ┌──────────────────────────────┐
   │ 25 km grid over France  (grid.py)      │   │ load data/grid_points.csv    │
   │   2036 points                          │   │ fetch hourly temps for the   │
   │      │ reverse-geocode each point      │   │   whole week (open-meteo,    │
   │      ▼ (geo.api.gouv.fr, geocode.py)   │   │   batched, cached)           │
   │ keep points inside France, dedupe      │   │ slice chosen date+hour       │
   │   880 communes                         │   │ rank → top 20 hot / cold     │
   │      ▼                                 │   │ two tables + Google Maps      │
   │ data/grid_points.csv  (committed)      │   │   links + map (streamlit_app)│
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
- Communes: [geo.api.gouv.fr](https://geo.api.gouv.fr/) (French government).

Coverage is metropolitan France including Corsica; overseas territories are out
of scope. Temperatures are forecasts and shaded amber→red (hot) / blue (cool).
