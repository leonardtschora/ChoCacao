# 7. Tooling and deployment

- **Status:** Accepted
- **Date:** 2026-06-20

## Context

The spec requires `uv` for env/deps, `ruff`/`pyright` compliance, and deployment
as a public Streamlit app from a GitHub repo.

## Decision

- **Environment:** `uv` with Python **3.12** (`.python-version`). Dependencies in
  `pyproject.toml`; `uv.lock` committed for reproducibility. The project is marked
  `[tool.uv] package = false` — it's an application, not a library, so only its
  dependencies are installed and `streamlit_app.py` imports the local `chocacao`
  package via the repo root on `sys.path`.
- **Runtime deps:** `streamlit`, `requests`, `pandas`. **Dev deps:** `ruff`,
  `pyright` (in a `dev` dependency group).
- **Quality gates:** `ruff` (lint + format) and `pyright` (standard mode) both
  pass clean. Config lives in `pyproject.toml`.
- **Entry point:** `streamlit_app.py` at the repo root (the name Streamlit Cloud
  looks for by default).
- **Deployment:** Streamlit Community Cloud, deploying from GitHub. A
  `requirements.txt` mirroring the runtime deps is provided because Streamlit
  Cloud installs via `pip`/`requirements.txt`; `pyproject.toml` + `uv` remain the
  source of truth for local development.

## Consequences

- `uv run streamlit run streamlit_app.py` locally; push to GitHub and point
  Streamlit Cloud at `streamlit_app.py` to deploy.
- Two dependency declarations (pyproject + requirements.txt) are kept in sync by
  hand; both are tiny (three packages).
