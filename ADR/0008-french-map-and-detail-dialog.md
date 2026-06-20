# 8. French map, localisation, and the detail dialog

- **Status:** Accepted
- **Date:** 2026-06-20

## Context

The app targets French users. It needs a French-language UI and a French map,
where clicking a point opens an overlay with the commune's detail and a 48 h
temperature curve, closeable by the user.

## Decision

### Localisation (i18n)

All user-facing text is in **French**. Dates are formatted by hand
(`format_fr`) with French day/month names rather than relying on a system locale
(which is not guaranteed on the deploy host).

### Map: `st.pydeck_chart` over IGN tiles

We replaced the simple `st.map` with **pydeck**, because we now need click
selection, custom colours, tooltips, and zoom-aware sizing — none of which
`st.map` supports.

- **Basemap:** the official French **IGN "Plan IGN" vector style** (attenuated
  variant) from the Géoplateforme (`data.geopf.fr`, no API key), set as the deck's
  `map_style` and rendered by MapLibre via `map_provider="carto"` (token-free).
  This is a genuinely French map with French labels.
  - *Pitfall avoided:* a first attempt used a raster `TileLayer`, which appeared
    blank. deck.gl's `TileLayer` needs a JS `renderSubLayers`/`BitmapLayer`
    callback to actually draw raster tiles, which pydeck cannot express from
    Python. Using IGN's MapLibre **vector style as the base map** (not a deck
    layer) is the correct, working approach.
- **Points:** a `ScatterplotLayer` of the 200 extreme communes (100 coolest +
  100 hottest), `pickable=True`, coloured by the **same diverging scale as the
  tables** (ADR 0006). The scale is **gamma-steepened** (`abs(frac) ** 0.5`) so
  small deviations from the median are already clearly visible.
- **Zoom-aware size:** radius is in **metres** (`get_radius=11000`) so points
  grow when zooming in, bounded by `radius_min_pixels`/`radius_max_pixels` so
  they stay visible when zoomed out.

### Detail overlay: `st.dialog`

Clicking a point selects it (`on_select="rerun"`, `selection_mode="single-object"`).
A `@st.dialog` (a true modal the user can close) then shows the commune name,
département, temperature, écart to the median, a **48 h temperature line chart**,
and a Google Maps link.

To avoid the modal reopening when the user closes it (a rerun keeps the map's
selection), we remember the last-shown commune in `st.session_state` and only
open the dialog when the selection actually changes.

## Consequences

- One extra explicit dependency (`pydeck`, already shipped with Streamlit).
- The map-click interaction can only be fully verified in a browser; the
  non-interactive render and all helper logic are covered by `AppTest`/unit checks.
- IGN tiles require attribution, shown in the footer.
