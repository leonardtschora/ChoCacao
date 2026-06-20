# 6. UI and result tables

- **Status:** Accepted (revised — supersedes the original HTML-table approach)
- **Date:** 2026-06-20

## Context

The app shows the extremes as two tables. Users must be able to **sort** them by
commune name, by département, or by temperature. Each row needs commune name,
département, temperature, and the difference to the national median. Latitude and
longitude are no longer shown.

## Decision

- **Controls:** `st.date_input` and an hour `st.selectbox` (0–23, default 16:00).
  Defaults to today at 16:00 (Paris time). Bounds come from the cached forecast
  window (see ADR 0005).
- **Tables: `st.dataframe`** (one per side) with native, click-to-sort column
  headers — this is what satisfies the sort-by-name / département / temperature
  requirement without any extra controls. **Coolest on the left, hottest on the
  right.** Top 50 each.
- **Columns:** `Commune`, `Département` (`"05 · Hautes-Alpes"`, derived from the
  INSEE code — see ADR 0009), `Température`, `Écart médiane`.
- **Difference to median:** the median is computed over **all** ~880 communes at
  the selected hour; each row shows `temperature − median` (signed).
- **Colour:** the `Température` cell is shaded with a **diverging blue→neutral→red
  scale centred on the median**, via a pandas `Styler`. The exact same mapping
  colours the map points (ADR 0008), so a given temperature looks identical in
  both places.

## Why `st.dataframe` (revised from the original HTML tables)

The first version rendered HTML tables so the commune *name* could be a Google
Maps `<a>` link. The new requirement is interactive sorting, which `st.dataframe`
provides natively and HTML tables cannot. The Google Maps link moves to the
map-click detail dialog (ADR 0008), where it pins the exact coordinates. Net: we
gain sorting and lose nothing meaningful.

## Consequences

- Sorting, accented names, and per-cell colour all work together.
- `Styler` + `column_config` (number formatting/labels) + header sorting compose
  cleanly in `st.dataframe`.
