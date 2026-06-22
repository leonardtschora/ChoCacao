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

# Mesure sélectionnable, partagée par le classement, la médiane et la carte.
METRIC_TEMP = "Température de l'air"
METRIC_APPARENT = "Température ressentie"

# Échelles de couleur par groupe : chaque groupe est étiré sur toute sa gamme pour
# faire ressortir les écarts entre points. Les 100 plus fraîches vont du bleu
# profond (la plus froide) au vert (la « plus chaude » des fraîches) ; les 100 plus
# chaudes vont du jaune (la « moins chaude » des chaudes) au rouge profond.
COOL_RAMP = ((13, 71, 161), (0, 150, 160), (76, 175, 80))  # bleu → turquoise → vert
HOT_RAMP = ((255, 214, 53), (245, 130, 32), (176, 0, 32))  # jaune → orange → rouge

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
    apparent: float

    @property
    def departement(self) -> str:
        return f"{self.departement_code} · {self.departement_name}"

    def value(self, metric: str) -> float:
        """The reading's air or apparent temperature, per the selected metric."""
        return self.apparent if metric == METRIC_APPARENT else self.temp


def format_fr(dt: datetime) -> str:
    """e.g. 'samedi 20 juin 2026 à 16:00'."""
    return f"{JOURS[dt.weekday()]} {dt.day} {MOIS[dt.month - 1]} {dt.year} à {dt.hour:02d}:00"


def forecast_period_key(now: datetime | None = None) -> str:
    """Cache key that rolls over once a day at REFRESH_HOUR (Europe/Paris)."""
    now = now or datetime.now(PARIS_TZ)
    return (now - timedelta(hours=REFRESH_HOUR)).date().isoformat()


@st.cache_data(show_spinner="Récupération des prévisions depuis open-meteo…", max_entries=2)
def get_forecast(
    period_key: str,
) -> tuple[list[Place], list[str], dict[str, list[float | None]], dict[str, list[float | None]]]:
    """Load places and their forecasts, pulled once per day (see forecast_period_key)."""
    places = load_places()
    times, temps, apparent = fetch_forecast(places)
    return places, times, temps, apparent


def maps_url(lat: float, lon: float) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={lat:.5f},{lon:.5f}"


def _lerp(a: int, b: int, frac: float) -> int:
    return round(a + (b - a) * frac)


def _ramp(stops: tuple[tuple[int, int, int], ...], t: float) -> tuple[int, int, int]:
    """Interpolate a colour at position ``t`` in [0, 1] across the ramp's stops."""
    t = max(0.0, min(1.0, t))
    span = t * (len(stops) - 1)
    i = min(int(span), len(stops) - 2)
    frac = span - i
    a, b = stops[i], stops[i + 1]
    return _lerp(a[0], b[0], frac), _lerp(a[1], b[1], frac), _lerp(a[2], b[2], frac)


def group_rgb(value: float, lo: float, hi: float, hot: bool) -> tuple[int, int, int]:
    """Colour for ``value`` stretched over its group's own [lo, hi] range."""
    t = 0.5 if hi <= lo else (value - lo) / (hi - lo)
    return _ramp(HOT_RAMP if hot else COOL_RAMP, t)


def cell_style(value: float, lo: float, hi: float, hot: bool) -> str:
    r, g, b = group_rgb(value, lo, hi, hot)
    # Texte blanc sur fond sombre (bleu/rouge profond), sinon texte foncé.
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    text = "#ffffff" if luminance < 140 else "#1a1a1a"
    return f"background-color: rgb({r},{g},{b}); color: {text};"


def selected_date(value: object, fallback: date) -> date:
    """Normalise st.date_input's return (date | tuple | None) to a single date."""
    if isinstance(value, date):
        return value
    if isinstance(value, (tuple, list)) and value and isinstance(value[0], date):
        return value[0]
    return fallback


def build_readings(
    places: list[Place],
    temps: dict[str, list[float | None]],
    apparent: dict[str, list[float | None]],
    idx: int,
) -> list[Reading]:
    """Air and apparent temperature reading per place at timeline position ``idx``."""
    readings: list[Reading] = []
    for place in places:
        t = temps.get(place.insee_code, [])
        a = apparent.get(place.insee_code, [])
        if idx >= len(t) or idx >= len(a) or t[idx] is None or a[idx] is None:
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
                float(t[idx]),  # type: ignore[arg-type]
                float(a[idx]),  # type: ignore[arg-type]
            )
        )
    return readings


def render_table(
    rows: list[Reading], hot: bool, metric: str, lo: float, hi: float, median: float
) -> None:
    """Sortable table: commune, département, air, ressentie, écart à la médiane.

    Both temperature columns are always shown; the one matching ``metric`` is
    colour-coded and drives the ``Écart`` (deviation from that metric's median).
    """
    df = pd.DataFrame(
        {
            "Commune": [r.name for r in rows],
            "Département": [r.departement for r in rows],
            "Air": [round(r.temp, 1) for r in rows],
            "Ressentie": [round(r.apparent, 1) for r in rows],
            "Écart médiane": [round(r.value(metric) - median, 1) for r in rows],
        }
    )
    coloured = "Ressentie" if metric == METRIC_APPARENT else "Air"
    styles = [cell_style(r.value(metric), lo, hi, hot) for r in rows]
    styler = df.style.apply(lambda _col: styles, subset=[coloured])
    st.dataframe(
        styler,
        hide_index=True,
        width="stretch",
        height=600,
        column_config={
            "Commune": st.column_config.TextColumn("Commune"),
            "Département": st.column_config.TextColumn("Département"),
            "Air": st.column_config.NumberColumn("Air", format="%.1f °C"),
            "Ressentie": st.column_config.NumberColumn("Ressentie", format="%.1f °C"),
            "Écart médiane": st.column_config.NumberColumn("Écart médiane", format="%+.1f °C"),
        },
    )


def map_records(
    rows: list[Reading], hot: bool, metric: str, lo: float, hi: float, median: float
) -> list[dict[str, Any]]:
    """Map point records coloured by the selected metric over the group's range."""
    return [
        {
            "insee_code": r.insee_code,
            "name": r.name,
            "dept": r.departement,
            "air": round(r.temp, 1),
            "ressentie": round(r.apparent, 1),
            "ecart": round(r.value(metric) - median, 1),
            "lat": r.lat,
            "lon": r.lon,
            "color": [*group_rgb(r.value(metric), lo, hi, hot), 220],
        }
        for r in rows
    ]


def build_map(records: list[dict[str, Any]], metric: str):
    """French map; points coloured by the selected metric, sized to scale with zoom."""
    df = pd.DataFrame(records)
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
    metric_line = (
        "ressentie <b>{ressentie} °C</b> · air {air} °C"
        if metric == METRIC_APPARENT
        else "air <b>{air} °C</b> · ressentie {ressentie} °C"
    )
    deck_kwargs: dict[str, Any] = {
        "tooltip": {
            "html": f"<b>{{name}}</b> ({{dept}})<br/>{metric_line}<br/>{{ecart}} vs médiane",
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
    r: Reading,
    metric: str,
    median: float,
    idx: int,
    times: list[str],
    temps: dict[str, list[float | None]],
    apparent: dict[str, list[float | None]],
) -> None:
    st.markdown(f"### {r.name}")
    st.write(f"**Département :** {r.departement}  ·  **Code postal :** {r.postal_code}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Air", f"{r.temp:.1f} °C")
    col2.metric("Ressentie", f"{r.apparent:.1f} °C")
    col3.metric(f"Écart médiane ({metric.lower()})", f"{r.value(metric) - median:+.1f} °C")

    end = min(idx + CURVE_HOURS, len(times))
    hours = [datetime.fromisoformat(t) for t in times[idx:end]]
    curve = pd.DataFrame(
        {
            "Heure": hours,
            "Air (°C)": temps.get(r.insee_code, [])[idx:end],
            "Ressentie (°C)": apparent.get(r.insee_code, [])[idx:end],
        }
    ).set_index("Heure")
    st.markdown(f"**Évolution sur {len(hours)} h**")
    st.line_chart(curve)

    st.link_button("📍 Ouvrir dans Google Maps", maps_url(r.lat, r.lon))


def main() -> None:
    st.title("🍫 ChoCacao")
    st.caption(
        "Les communes les plus chaudes et les plus fraîches de France métropolitaine — "
        "où profiter du soleil ou fuir la canicule."
    )

    try:
        places, times, temps, apparent = get_forecast(forecast_period_key())
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

    col_date, col_hour, col_metric = st.columns([1, 1, 2])
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
    with col_metric:
        metric = st.segmented_control(
            "Mesure",
            options=[METRIC_TEMP, METRIC_APPARENT],
            default=METRIC_TEMP,
            help="Critère utilisé pour le classement, la médiane et la coloration de la carte.",
        )
        metric = metric or METRIC_TEMP  # le widget peut renvoyer None si désélectionné

    chosen = selected_date(date_value, default_date)
    target = f"{chosen.isoformat()}T{hour:02d}:00"
    when = format_fr(datetime.fromisoformat(target))
    try:
        idx = times.index(target)
    except ValueError:
        st.warning(f"Aucune prévision disponible pour {when}.")
        st.stop()

    readings = build_readings(places, temps, apparent, idx)
    if not readings:
        st.warning(f"Aucune prévision disponible pour {when}.")
        st.stop()

    # Le classement, la médiane, l'écart et la carte suivent la mesure choisie.
    median = statistics.median(r.value(metric) for r in readings)
    coolest = sorted(readings, key=lambda r: r.value(metric))[:TOP_N]
    hottest = sorted(readings, key=lambda r: r.value(metric), reverse=True)[:TOP_N]

    # Chaque groupe est coloré sur sa propre gamme pour maximiser le contraste.
    cool_lo = coolest[0].value(metric)
    cool_hi = coolest[-1].value(metric)
    hot_hi = hottest[0].value(metric)
    hot_lo = hottest[-1].value(metric)

    st.subheader(
        f"{when} · {len(readings)} communes analysées · "
        f"médiane {median:.1f} °C ({metric.lower()})"
    )
    st.caption(
        "Cliquez sur un en-tête de colonne pour trier (commune, département, air ou ressentie)."
    )

    left, right = st.columns(2)
    with left:
        st.markdown(f"### ❄️ {TOP_N} plus fraîches")
        render_table(coolest, False, metric, cool_lo, cool_hi, median)
    with right:
        st.markdown(f"### 🔥 {TOP_N} plus chaudes")
        render_table(hottest, True, metric, hot_lo, hot_hi, median)

    st.subheader("🗺️ Carte")
    st.caption("Cliquez sur un point pour afficher le détail et l'évolution sur 48 h.")
    by_insee = {r.insee_code: r for r in coolest + hottest}
    records = map_records(coolest, False, metric, cool_lo, cool_hi, median) + map_records(
        hottest, True, metric, hot_lo, hot_hi, median
    )
    event = build_map(records, metric)

    sel = getattr(event, "selection", None) or {}
    objs = (sel.get("objects") or {}).get("communes") or []
    clicked = objs[0].get("insee_code") if objs else None
    if clicked and st.session_state.get("shown_commune") != clicked:
        st.session_state["shown_commune"] = clicked
        if clicked in by_insee:
            commune_dialog(by_insee[clicked], metric, median, idx, times, temps, apparent)

    st.divider()
    st.caption(
        "Données météo : [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0) · "
        "Communes : [geo.api.gouv.fr](https://geo.api.gouv.fr/) · "
        "Fond de carte : © [OpenStreetMap](https://www.openstreetmap.org/copyright) "
        "/ [CARTO](https://carto.com/). "
        "Température de l'air à 2 m et température ressentie en °C, heure locale."
    )


if __name__ == "__main__":
    main()
