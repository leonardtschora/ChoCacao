"""ChoCacao — the 20 hottest and 20 coolest places in metropolitan France.

Pick a date (up to a week ahead) and an hour; ChoCacao queries open-meteo for
~1000 communes spread on a 25 km grid and shows the extremes as two tables.
Click a place name to open it, pinned, in Google Maps.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from chocacao.forecast import Place, fetch_forecast, load_places

st.set_page_config(page_title="ChoCacao", page_icon="🍫", layout="wide")

DEFAULT_HOUR = 16  # 4 pm: usually the hottest hour of the day
TOP_N = 20

PARIS_TZ = ZoneInfo("Europe/Paris")
REFRESH_HOUR = 2  # forecasts are refreshed once a day at 02:00 Paris time

HOT_COLOR = "#d7301f"
COOL_COLOR = "#0b5394"


@dataclass(frozen=True)
class Reading:
    name: str
    postal_code: str
    lat: float
    lon: float
    temp: float


def forecast_period_key(now: datetime | None = None) -> str:
    """Cache key for the daily forecast pull.

    Rolls over once a day at REFRESH_HOUR (02:00 Europe/Paris): before 02:00 we
    are still on the previous day's pull; at/after 02:00 the key changes and a
    single fresh fetch is shared by everyone for the next 24 hours.
    """
    now = now or datetime.now(PARIS_TZ)
    return (now - timedelta(hours=REFRESH_HOUR)).date().isoformat()


@st.cache_data(show_spinner="Fetching forecasts from open-meteo…", max_entries=2)
def get_forecast(period_key: str) -> tuple[list[Place], list[str], dict[str, list[float | None]]]:
    """Load places and their forecasts, pulled once per day.

    ``period_key`` (from :func:`forecast_period_key`) is the cache key: it changes
    once a day at 02:00 Paris time, so open-meteo is queried just once daily.
    Because ``st.cache_data`` is shared across all user sessions, that single pull
    serves every user and every selectable date/hour — we fetch the whole week
    and slice it in memory, so changing the date or hour never hits the API.
    """
    places = load_places()
    times, series = fetch_forecast(places)
    return places, times, series


def maps_url(lat: float, lon: float) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={lat:.5f},{lon:.5f}"


def _lerp(a: int, b: int, frac: float) -> int:
    return round(a + (b - a) * frac)


def temp_color(temp: float, vmin: float, vmax: float, hot: bool) -> str:
    """Inline style for a temperature cell (deeper colour = more extreme)."""
    span = vmax - vmin
    frac = 0.0 if span <= 0 else (temp - vmin) / span
    if not hot:
        frac = 1.0 - frac  # coolest gets the deepest colour
    if hot:
        light, deep = (255, 244, 219), (183, 28, 28)  # pale amber -> deep red
    else:
        light, deep = (227, 242, 253), (13, 71, 161)  # pale -> deep blue
    r = _lerp(light[0], deep[0], frac)
    g = _lerp(light[1], deep[1], frac)
    b = _lerp(light[2], deep[2], frac)
    text = "#ffffff" if frac > 0.55 else "#1a1a1a"
    return f"background-color: rgb({r},{g},{b}); color: {text};"


def render_table(rows: list[Reading], hot: bool) -> str:
    """Render a ranked list as an HTML table; names link to Google Maps."""
    temps = [r.temp for r in rows]
    vmin, vmax = min(temps), max(temps)
    head = (
        "<table class='cc-table'><thead><tr>"
        "<th>#</th><th>Place</th><th>Postal&nbsp;code</th>"
        "<th>Latitude</th><th>Longitude</th><th>°C</th>"
        "</tr></thead><tbody>"
    )
    body: list[str] = []
    for rank, row in enumerate(rows, start=1):
        url = maps_url(row.lat, row.lon)
        name = html.escape(row.name)
        postal = html.escape(row.postal_code)
        style = temp_color(row.temp, vmin, vmax, hot)
        body.append(
            f"<tr><td class='rank'>{rank}</td>"
            f"<td><a href='{url}' target='_blank' rel='noopener'>{name}</a></td>"
            f"<td>{postal}</td>"
            f"<td>{row.lat:.4f}</td><td>{row.lon:.4f}</td>"
            f"<td class='temp' style='{style}'>{row.temp:.1f}</td></tr>"
        )
    return head + "".join(body) + "</tbody></table>"


TABLE_CSS = """
<style>
.cc-table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
.cc-table th, .cc-table td { padding: 6px 10px; text-align: left;
    border-bottom: 1px solid rgba(128,128,128,0.25); }
.cc-table th { font-weight: 600; border-bottom: 2px solid rgba(128,128,128,0.5); }
.cc-table td.rank { color: #888; width: 2rem; }
.cc-table td.temp { text-align: right; font-weight: 600; font-variant-numeric: tabular-nums;
    border-radius: 4px; }
.cc-table a { text-decoration: none; font-weight: 600; }
.cc-table a:hover { text-decoration: underline; }
</style>
"""


def build_readings(
    places: list[Place], times: list[str], series: dict[str, list[float | None]], target: str
) -> list[Reading]:
    """Collect a temperature reading per place at the ``target`` timestamp."""
    try:
        idx = times.index(target)
    except ValueError:
        return []

    readings: list[Reading] = []
    for place in places:
        temps = series.get(place.insee_code, [])
        if idx >= len(temps):
            continue
        temp = temps[idx]
        if temp is None:
            continue
        readings.append(Reading(place.name, place.postal_code, place.lat, place.lon, float(temp)))
    return readings


def selected_date(value: object, fallback: date) -> date:
    """Normalise st.date_input's return (date | tuple | None) to a single date."""
    if isinstance(value, date):
        return value
    if isinstance(value, (tuple, list)) and value and isinstance(value[0], date):
        return value[0]
    return fallback


def main() -> None:
    st.markdown(TABLE_CSS, unsafe_allow_html=True)
    st.title("🍫 ChoCacao")
    st.caption(
        "The hottest and coolest places in metropolitan France — find where to "
        "chase the sun or escape the heatwave."
    )

    try:
        places, times, series = get_forecast(forecast_period_key())
    except Exception as exc:  # surface API/network issues to the user
        st.error(f"Could not fetch forecasts from open-meteo: {exc}")
        st.stop()
    if not times:
        st.error("open-meteo returned no forecast timeline. Please try again later.")
        st.stop()

    # The selectable range is exactly the window held in today's cached pull,
    # so a valid selection can never fall outside the fetched data.
    available_dates = sorted({t[:10] for t in times})
    min_date = date.fromisoformat(available_dates[0])
    max_date = date.fromisoformat(available_dates[-1])
    today = datetime.now(PARIS_TZ).date()
    default_date = min(max(today, min_date), max_date)

    col_date, col_hour, _ = st.columns([1, 1, 2])
    with col_date:
        date_value = st.date_input(
            "Date",
            value=default_date,
            min_value=min_date,
            max_value=max_date,
            help="Forecasts are available up to one week ahead.",
        )
    with col_hour:
        hour = st.selectbox(
            "Hour (local time)",
            options=list(range(24)),
            index=DEFAULT_HOUR,
            format_func=lambda h: f"{h:02d}:00",
            help="Default is 16:00 (4 pm), usually the hottest hour of the day.",
        )

    chosen = selected_date(date_value, default_date)
    target = f"{chosen.isoformat()}T{hour:02d}:00"

    readings = build_readings(places, times, series, target)
    when = datetime.fromisoformat(target).strftime("%A %d %B %Y at %H:%M")
    if not readings:
        st.warning(f"No forecast available for {when}. Try another date or hour.")
        st.stop()

    st.subheader(f"{when} · {len(places)} places surveyed")

    hottest = sorted(readings, key=lambda r: r.temp, reverse=True)[:TOP_N]
    coolest = sorted(readings, key=lambda r: r.temp)[:TOP_N]

    left, right = st.columns(2)
    with left:
        st.markdown(f"### 🔥 {TOP_N} hottest")
        st.markdown(render_table(hottest, hot=True), unsafe_allow_html=True)
    with right:
        st.markdown(f"### ❄️ {TOP_N} coolest")
        st.markdown(render_table(coolest, hot=False), unsafe_allow_html=True)

    with st.expander("🗺️ Show these places on a map"):
        map_rows = [{"lat": r.lat, "lon": r.lon, "color": HOT_COLOR} for r in hottest]
        map_rows += [{"lat": r.lat, "lon": r.lon, "color": COOL_COLOR} for r in coolest]
        map_df = pd.DataFrame(map_rows)
        st.map(map_df, latitude="lat", longitude="lon", color="color", size=10000)

    st.divider()
    st.caption(
        "Click a place name to open it in Google Maps. "
        "Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0); "
        "commune data from [geo.api.gouv.fr](https://geo.api.gouv.fr/). "
        "Temperatures are 2 m air temperature in °C, local time."
    )


if __name__ == "__main__":
    main()
