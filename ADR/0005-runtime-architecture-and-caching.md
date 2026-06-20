# 5. Runtime architecture and caching

- **Status:** Accepted
- **Date:** 2026-06-20

## Context

At run time the app must, for a chosen date/hour, return the 20 hottest and 20
coolest of ~880 places — while staying within open-meteo's free limits and being
responsive for many users.

## Decision

### Fetch the whole week once, slice in memory

One open-meteo request returns the **entire hourly series** for a location
regardless of the hour we care about. So we fetch all 8 forecast days
(`today + 7`) for every place once, then slice the requested timestamp in memory.
Changing the date/hour in the UI needs **no new API call**.

### Batching

Coordinates are sent ~100 per request (comma-separated). ~880 places → ~9 HTTP
requests covering all of France.

### Rate-limit handling

open-meteo's free tier limits the number of *locations* per minute (~600). The
fetch retries HTTP 429 with back-off (honouring `Retry-After`) and lightly paces
batches, so a cold fetch reliably completes in tens of seconds.

### Caching (`st.cache_data`)

`get_forecast(period_key)` is cached and keyed by a **forecast period that rolls
over once a day at 02:00 Europe/Paris** (`forecast_period_key()` returns
`(now − 2h).date()`). There is **no short TTL**: the key changes exactly once per
day, so the whole of France is pulled from open-meteo **once daily** and that
single pull serves every user and every selectable date/hour (we fetch the entire
week and slice in memory). Because `st.cache_data` is shared across all user
sessions, the daily query count is a small fixed number regardless of how many
people connect. `max_entries=2` bounds memory to the current and previous day.

02:00 is chosen as a quiet hour just after the day boundary. The trade-off is
that the displayed forecast can lag the latest open-meteo model run by up to a
day — acceptable for "where to escape the heat this week".

The date-picker bounds are derived from the dates actually present in the cached
timeline (not from the calendar), so the selectable range and the cached data can
never disagree (e.g. in the 00:00–02:00 window before the daily refresh).

## Future work (per spec)

- A scheduled job (e.g. GitHub Action or cron) could pull forecasts into a
  committed / object-store snapshot, making the app fully read-only at run time
  and removing even the first-request-of-the-day fetch latency. The current
  once-daily shared cache already realises the spec's "pull on a daily basis /
  cap queries" goal in-process; an external snapshot is the natural next step.

## Consequences

- The first request after 02:00 each day pays the fetch cost (~tens of seconds,
  with a spinner); every other request that day is instant.
- The forecast horizon is tied to `FORECAST_DAYS` (8 → today + 7).
