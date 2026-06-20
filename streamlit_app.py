"""ChoCacao — les communes les plus chaudes et les plus fraîches de France.

Choisissez une date (jusqu'à une semaine à l'avance) et une heure ; ChoCacao
interroge open-meteo pour ~880 communes réparties sur une grille de 25 km et
affiche les extrêmes. Cliquez sur un point de la carte pour le détail.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import pydeck as pdk
import streamlit as st

from chocacao.forecast import Place, fetch_forecast, load_places

st.set_page_config(page_title="ChoCacao", page_icon="🍫", layout="wide")

DEFAULT_HOUR = 16  # 16 h : heure généralement la plus chaude de la journée
TOP_N = 100
CURVE_HOURS = 48

PARIS_TZ = ZoneInfo("Europe/Paris")
REFRESH_HOUR = 2  # les prévisions sont rafraîchies une fois par jour, à 02 h 00

# Échelle de couleur divergente (RGB) partagée par les tableaux et la carte :
# bleu profond = plus frais que la médiane, rouge profond = plus chaud.
NEUTRAL_RGB = (245, 245, 240)
HOT_RGB = (176, 0, 32)
COOL_RGB = (0, 51, 160)
# Gamma < 1 raidit le dégradé : un faible écart à la médiane se voit déjà bien.
GRADIENT_GAMMA = 0.5

# Fond de carte : style vectoriel CARTO « Voyager » (labels en français, sans clé
# d'API). NB : Streamlit/pydeck (fournisseur "carto") n'accepte que des styles
# hébergés par CARTO — un style IGN/Géoplateforme fait planter le rendu deck.gl.
BASEMAP_STYLE = pdk.map_styles.CARTO_ROAD

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]


@dataclass(frozen=True)
class Reading:
    insee_code: str
    name: str
    postal_code: str
    departement_code: str
    departement_name: str
    lat: float
    lon: float
    temp: float

    @property
    def departement(self) -> str:
        return f"{self.departement_code} · {self.departement_name}"


def format_fr(dt: datetime) -> str:
    """e.g. 'samedi 20 juin 2026 à 16:00'."""
    return f"{JOURS[dt.weekday()]} {dt.day} {MOIS[dt.month - 1]} {dt.year} à {dt.hour:02d}:00"


def forecast_period_key(now: datetime | None = None) -> str:
    """Cache key that rolls over once a day at REFRESH_HOUR (Europe/Paris)."""
    now = now or datetime.now(PARIS_TZ)
    return (now - timedelta(hours=REFRESH_HOUR)).date().isoformat()


@st.cache_data(show_spinner="Récupération des prévisions depuis open-meteo…", max_entries=2)
def get_forecast(period_key: str) -> tuple[list[Place], list[str], dict[str, list[float | None]]]:
    """Load places and their forecasts, pulled once per day (see forecast_period_key)."""
    places = load_places()
    times, series = fetch_forecast(places)
    return places, times, series


def maps_url(lat: float, lon: float) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={lat:.5f},{lon:.5f}"


def _lerp(a: int, b: int, frac: float) -> int:
    return round(a + (b - a) * frac)


def _intensity(temp: float, median: float, scale: float) -> tuple[float, float]:
    """Return (signed fraction in [-1,1], gamma-steepened magnitude in [0,1])."""
    frac = 0.0 if scale <= 0 else max(-1.0, min(1.0, (temp - median) / scale))
    return frac, abs(frac) ** GRADIENT_GAMMA


def diverging_rgb(temp: float, median: float, scale: float) -> tuple[int, int, int]:
    """RGB on a steep blue→neutral→red scale based on deviation from the median."""
    frac, f = _intensity(temp, median, scale)
    target = HOT_RGB if frac >= 0 else COOL_RGB
    return (
        _lerp(NEUTRAL_RGB[0], target[0], f),
        _lerp(NEUTRAL_RGB[1], target[1], f),
        _lerp(NEUTRAL_RGB[2], target[2], f),
    )


def cell_style(temp: float, median: float, scale: float) -> str:
    r, g, b = diverging_rgb(temp, median, scale)
    _, f = _intensity(temp, median, scale)
    text = "#ffffff" if f > 0.6 else "#1a1a1a"
    return f"background-color: rgb({r},{g},{b}); color: {text};"


def selected_date(value: object, fallback: date) -> date:
    """Normalise st.date_input's return (date | tuple | None) to a single date."""
    if isinstance(value, date):
        return value
    if isinstance(value, (tuple, list)) and value and isinstance(value[0], date):
        return value[0]
    return fallback


def build_readings(
    places: list[Place], series: dict[str, list[float | None]], idx: int
) -> list[Reading]:
    """Temperature reading per place at timeline position ``idx``."""
    readings: list[Reading] = []
    for place in places:
        temps = series.get(place.insee_code, [])
        if idx >= len(temps) or temps[idx] is None:
            continue
        readings.append(
            Reading(
                place.insee_code,
                place.name,
                place.postal_code,
                place.departement_code,
                place.departement_name,
                place.lat,
                place.lon,
                float(temps[idx]),  # type: ignore[arg-type]
            )
        )
    return readings


def render_table(rows: list[Reading], median: float, scale: float) -> None:
    """Sortable table: commune, département, température, écart à la médiane."""
    df = pd.DataFrame(
        {
            "Commune": [r.name for r in rows],
            "Département": [r.departement for r in rows],
            "Température": [round(r.temp, 1) for r in rows],
            "Écart médiane": [round(r.temp - median, 1) for r in rows],
        }
    )
    styles = [cell_style(r.temp, median, scale) for r in rows]
    styler = df.style.apply(lambda _col: styles, subset=["Température"])
    st.dataframe(
        styler,
        hide_index=True,
        width="stretch",
        height=600,
        column_config={
            "Commune": st.column_config.TextColumn("Commune"),
            "Département": st.column_config.TextColumn("Département"),
            "Température": st.column_config.NumberColumn("Température", format="%.1f °C"),
            "Écart médiane": st.column_config.NumberColumn("Écart médiane", format="%+.1f °C"),
        },
    )


def build_map(rows: list[Reading], median: float, scale: float):
    """French (IGN) map; points coloured by temperature, sized to scale with zoom."""
    df = pd.DataFrame(
        [
            {
                "insee_code": r.insee_code,
                "name": r.name,
                "dept": r.departement,
                "temp": round(r.temp, 1),
                "ecart": round(r.temp - median, 1),
                "lat": r.lat,
                "lon": r.lon,
                "color": [*diverging_rgb(r.temp, median, scale), 220],
            }
            for r in rows
        ]
    )
    scatter = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        id="communes",
        get_position=["lon", "lat"],
        get_fill_color="color",
        get_radius=9000,  # mètres → la taille grandit au zoom
        radius_min_pixels=3,
        radius_max_pixels=40,
        pickable=True,
        stroked=True,
        get_line_color=[40, 40, 40],
        line_width_min_pixels=0.5,
        auto_highlight=True,
    )
    # The HTML tooltip is valid at runtime but over-narrowed in pydeck's stubs.
    deck_kwargs: dict[str, Any] = {
        "tooltip": {
            "html": "<b>{name}</b> ({dept})<br/>{temp} °C ({ecart} vs médiane)",
            "style": {"backgroundColor": "#222", "color": "#fff", "fontSize": "12px"},
        },
    }
    deck = pdk.Deck(
        layers=[scatter],
        initial_view_state=pdk.ViewState(latitude=46.6, longitude=2.5, zoom=4.7),
        map_provider="carto",
        map_style=BASEMAP_STYLE,
        height=560,
        **deck_kwargs,
    )
    return st.pydeck_chart(
        deck, on_select="rerun", selection_mode="single-object", key="france_map"
    )


@st.dialog("Détail de la commune", width="large")
def commune_dialog(
    r: Reading, median: float, idx: int, times: list[str], series: dict[str, list[float | None]]
) -> None:
    st.markdown(f"### {r.name}")
    st.write(f"**Département :** {r.departement}  ·  **Code postal :** {r.postal_code}")
    col1, col2 = st.columns(2)
    col1.metric("Température", f"{r.temp:.1f} °C")
    col2.metric("Écart à la médiane", f"{r.temp - median:+.1f} °C")

    end = min(idx + CURVE_HOURS, len(times))
    temps = series.get(r.insee_code, [])[idx:end]
    hours = [datetime.fromisoformat(t) for t in times[idx:end]]
    curve = pd.DataFrame({"Heure": hours, "Température (°C)": temps}).set_index("Heure")
    st.markdown(f"**Évolution sur {len(hours)} h**")
    st.line_chart(curve, y="Température (°C)")

    st.link_button("📍 Ouvrir dans Google Maps", maps_url(r.lat, r.lon))


def main() -> None:
    st.title("🍫 ChoCacao")
    st.caption(
        "Les communes les plus chaudes et les plus fraîches de France métropolitaine — "
        "où profiter du soleil ou fuir la canicule."
    )

    try:
        places, times, series = get_forecast(forecast_period_key())
    except Exception as exc:  # remonter les erreurs réseau / API à l'utilisateur
        st.error(f"Impossible de récupérer les prévisions depuis open-meteo : {exc}")
        st.stop()
    if not times:
        st.error("open-meteo n'a renvoyé aucune prévision. Veuillez réessayer plus tard.")
        st.stop()

    # La plage sélectionnable correspond exactement à la fenêtre déjà en cache.
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
            help="Prévisions disponibles jusqu'à une semaine à l'avance.",
        )
    with col_hour:
        hour = st.selectbox(
            "Heure (locale)",
            options=list(range(24)),
            index=DEFAULT_HOUR,
            format_func=lambda h: f"{h:02d}:00",
            help="Par défaut 16 h, l'heure généralement la plus chaude.",
        )

    chosen = selected_date(date_value, default_date)
    target = f"{chosen.isoformat()}T{hour:02d}:00"
    when = format_fr(datetime.fromisoformat(target))
    try:
        idx = times.index(target)
    except ValueError:
        st.warning(f"Aucune prévision disponible pour {when}.")
        st.stop()

    readings = build_readings(places, series, idx)
    if not readings:
        st.warning(f"Aucune prévision disponible pour {when}.")
        st.stop()

    median = statistics.median(r.temp for r in readings)
    scale = max((abs(r.temp - median) for r in readings), default=1.0) or 1.0

    coolest = sorted(readings, key=lambda r: r.temp)[:TOP_N]
    hottest = sorted(readings, key=lambda r: r.temp, reverse=True)[:TOP_N]

    st.subheader(f"{when} · {len(readings)} communes analysées · médiane {median:.1f} °C")
    st.caption(
        "Cliquez sur un en-tête de colonne pour trier (commune, département ou température)."
    )

    left, right = st.columns(2)
    with left:
        st.markdown(f"### ❄️ {TOP_N} plus fraîches")
        render_table(coolest, median, scale)
    with right:
        st.markdown(f"### 🔥 {TOP_N} plus chaudes")
        render_table(hottest, median, scale)

    st.subheader("🗺️ Carte")
    st.caption("Cliquez sur un point pour afficher le détail et l'évolution sur 48 h.")
    extreme = coolest + hottest
    by_insee = {r.insee_code: r for r in extreme}
    event = build_map(extreme, median, scale)

    sel = getattr(event, "selection", None) or {}
    objs = (sel.get("objects") or {}).get("communes") or []
    clicked = objs[0].get("insee_code") if objs else None
    if clicked and st.session_state.get("shown_commune") != clicked:
        st.session_state["shown_commune"] = clicked
        if clicked in by_insee:
            commune_dialog(by_insee[clicked], median, idx, times, series)

    st.divider()
    st.caption(
        "Données météo : [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0) · "
        "Communes : [geo.api.gouv.fr](https://geo.api.gouv.fr/) · "
        "Fond de carte : © [OpenStreetMap](https://www.openstreetmap.org/copyright) "
        "/ [CARTO](https://carto.com/). "
        "Températures de l'air à 2 m en °C, heure locale."
    )


if __name__ == "__main__":
    main()
