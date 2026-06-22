# 12. Show every commune: one sortable table + a full diverging map

- **Status:** Accepted
- **Date:** 2026-06-22
- **Supersedes:** the two-group (top-100 cool / top-100 hot) presentation of
  ADR 0006 / ADR 0008.

## Context

Users wanted **more data points**, especially along the western coast. The honest
fix is a finer grid (more queries); as a first step, we can instead **show
everything we already fetch**. The previous UI showed only the 100 coolest and 100
hottest, in two tables and as two map groups — so most communes were invisible.

## Decision

Show **all** communes (grid + top cities + manual lookups) in both views.

- **One table, not two.** A single `st.dataframe` of every commune, sorted coolest
  → hottest. The "hottest" table is removed: the table is sortable, so clicking the
  header descending surfaces the hottest just as well. ~30 rows are visible
  (`TABLE_ROWS_VISIBLE`); the rest scroll. Manual communes are flagged `📍`.
- **Full map.** The scatter layer plots every commune, not just the extremes.
- **Single diverging colour scale.** With every commune shown, the per-group
  "stretch each top-100 over its own range" scheme (ADR 0008) no longer applies.
  Colour is now one diverging scale over `[min, max]`, centred on the **median**:
  deep-blue (coolest) → green at the median → deep-red (hottest), reusing the
  existing `COOL_RAMP`/`HOT_RAMP` stops. The whole country — including the western
  coast — is now meaningfully coloured.

## Consequences

- The table renders ~1160 styled rows instead of 100; well within Streamlit's
  capacity, and client-side sort keeps per-cell colours with their rows.
- `TOP_N` is gone; `TABLE_ROWS_VISIBLE` controls the viewport height. `group_rgb`
  (per-group) is replaced by `diverging_rgb` (global, median-centred).
- This is presentation-only: the fetched data is unchanged. A genuinely denser
  grid remains the real lever for more coastal resolution, and is future work.
