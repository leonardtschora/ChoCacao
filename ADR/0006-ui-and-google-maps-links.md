# 6. UI and clickable Google Maps links

- **Status:** Accepted
- **Date:** 2026-06-20

## Context

The spec asks for two tables (name, postal code, coordinates, temperature) where
**clicking the place name opens Google Maps with the location pinned**, plus a
date picker and an optional hour (default 16:00, default date today).

## Decision

- **Controls:** `st.date_input` (min today, max today + 7) and an hour
  `st.selectbox` (0–23, default index 16). No selection ⇒ today at 16:00.
- **Tables:** rendered as HTML via `st.markdown(..., unsafe_allow_html=True)`
  rather than `st.dataframe`. This is the only way to make the **place name
  itself** an `<a href>` link (the spec's requirement) while displaying accented
  commune names cleanly. Names are HTML-escaped.
- **Map link:** `https://www.google.com/maps/search/?api=1&query={lat},{lon}` —
  the official Maps URL scheme, which drops a pin at the exact coordinates.
- **Visual cue:** each temperature cell is shaded on a gradient (amber→deep red
  for hot, pale→deep blue for cool) so extremes are obvious at a glance.
- **Bonus:** an expandable `st.map` plots the 40 extreme places (red = hot,
  blue = cool) so users can see *where* in France to go.

## Why not `st.dataframe` + `LinkColumn`

`LinkColumn` can render a link, but its display text is derived from the URL via
regex, which mangles accented French names and cannot make the *name* column the
link cleanly. The HTML table gives full control for a top-20 list that is already
sorted and doesn't need interactive sorting.

## Consequences

- Output is presentation-focused and exactly matches the spec's interaction.
- `unsafe_allow_html=True` is safe here: all dynamic text is escaped and values
  come from a trusted, precomputed dataset.
