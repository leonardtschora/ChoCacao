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

`get_forecast(day)` is cached with `ttl=1800` and keyed by the calendar day.
Because `st.cache_data` is **shared across all user sessions** on a Streamlit
server, the API is hit only a handful of times per 30-minute window *no matter
how many users connect*. This already caps the daily query count to a small,
bounded number — directly addressing the spec's "cap queries / cache daily"
concern.

## Future work (per spec)

- A scheduled job (e.g. GitHub Action or cron) could pull forecasts once daily
  into a committed/object-store snapshot, making the app fully read-only at run
  time and removing even the first-user fetch latency. The current
  shared-cache design is the lightweight version of this and the natural
  stepping stone.

## Consequences

- First request after a cache miss pays the fetch cost (~tens of seconds, with a
  spinner); subsequent interactions are instant.
- The number of selectable days is tied to `FORECAST_DAYS` (8 → today + 7).
