"""ChoCacao — les communes les plus chaudes et les plus fraîches de France.

Choisissez une date (jusqu'à une semaine à l'avance) et une heure ; ChoCacao
interroge open-meteo pour ~1160 communes (grille de 25 km + les 288 plus
peuplées) et les affiche toutes dans un tableau triable et sur une carte, du
plus frais au plus chaud. Cherchez n'importe quelle commune par son nom pour
l'ajouter à la volée. Cliquez sur un point de la carte pour le détail.
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

from chocacao.forecast import (
    Place,
    fetch_forecast,
    fetch_one,
    load_commune_index,
    load_places,
)

st.set_page_config(page_title="ChoCacao", page_icon="🍫", layout="wide")

DEFAULT_HOUR = 16  # 16 h : heure généralement la plus chaude de la journée
TABLE_ROWS_VISIBLE = 30  # hauteur du tableau : ~30 lignes visibles, le reste défile
CURVE_HOURS = 48
MANUAL_MAX = 10  # garde-fou sur le nombre de communes ajoutées à la volée

PARIS_TZ = ZoneInfo("Europe/Paris")
REFRESH_HOUR = 2  # les prévisions sont rafraîchies une fois par jour, à 02 h 00

# Mesure sélectionnable, partagée par le tableau, la médiane et la carte.
METRIC_TEMP = "Température de l'air"
METRIC_APPARENT = "Température ressentie"

# Échelle de couleur divergente unique, centrée sur la médiane : toutes les communes
# sont colorées sur la même gamme. Du bleu profond (la plus froide) au vert à la
# médiane, puis du jaune au rouge profond (la plus chaude).
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


@st.cache_data(show_spinner=False)
def get_index() -> list[Place]:
    """Full metropolitan commune index, for the validated manual-lookup search box."""
    return load_commune_index()


@st.cache_data(show_spinner="Récupération de la commune demandée…", max_entries=64)
def get_manual_forecast(
    place: Place, period_key: str
) -> tuple[list[float | None], list[float | None]]:
    """On-demand forecast for one user-requested commune (not in the daily set).

    Cached for the day (keyed by the commune and ``period_key``) but never written
    to disk — it exists only as long as someone is asking for that commune.
    """
    _times, temps, apparent = fetch_one(place)
    return temps, apparent


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


def diverging_rgb(value: float, vmin: float, vmax: float, median: float) -> tuple[int, int, int]:
    """Colour on a single diverging scale: blue (vmin) → green (median) → red (vmax)."""
    if value <= median:
        t = 1.0 if median <= vmin else (value - vmin) / (median - vmin)
        return _ramp(COOL_RAMP, t)
    t = 1.0 if vmax <= median else (value - median) / (vmax - median)
    return _ramp(HOT_RAMP, t)


def cell_style(value: float, vmin: float, vmax: float, median: float) -> str:
    r, g, b = diverging_rgb(value, vmin, vmax, median)
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


def reading_at(
    place: Place,
    t: list[float | None],
    a: list[float | None],
    idx: int,
) -> Reading | None:
    """Build the reading for one place at timeline position ``idx`` (None if missing)."""
    if idx >= len(t) or idx >= len(a) or t[idx] is None or a[idx] is None:
        return None
    return Reading(
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
        r = reading_at(place, t, a, idx)
        if r is not None:
            readings.append(r)
    return readings


def render_table(
    rows: list[Reading],
    metric: str,
    vmin: float,
    vmax: float,
    median: float,
    manual_codes: set[str],
) -> None:
    """Single sortable table of every commune, coloured on the diverging scale.

    Both temperature columns are always shown; the one matching ``metric`` is
    colour-coded and drives the ``Écart`` (deviation from that metric's median).
    Manually-added communes are flagged with a 📍 so they stay findable after a
    sort. ~30 rows are visible; the rest scroll. Click a header to sort.
    """
    df = pd.DataFrame(
        {
            "Commune": [f"📍 {r.name}" if r.insee_code in manual_codes else r.name for r in rows],
            "Département": [r.departement for r in rows],
            "Air": [round(r.temp, 1) for r in rows],
            "Ressentie": [round(r.apparent, 1) for r in rows],
            "Écart médiane": [round(r.value(metric) - median, 1) for r in rows],
        }
    )
    coloured = "Ressentie" if metric == METRIC_APPARENT else "Air"
    styles = [cell_style(r.value(metric), vmin, vmax, median) for r in rows]
    styler = df.style.apply(lambda _col: styles, subset=[coloured])
    st.dataframe(
        styler,
        hide_index=True,
        width="stretch",
        height=35 * TABLE_ROWS_VISIBLE + 38,  # ~30 lignes visibles + l'en-tête
        column_config={
            "Commune": st.column_config.TextColumn("Commune"),
            "Département": st.column_config.TextColumn("Département"),
            "Air": st.column_config.NumberColumn("Air", format="%.1f °C"),
            "Ressentie": st.column_config.NumberColumn("Ressentie", format="%.1f °C"),
            "Écart médiane": st.column_config.NumberColumn("Écart médiane", format="%+.1f °C"),
        },
    )


def map_records(
    rows: list[Reading],
    metric: str,
    vmin: float,
    vmax: float,
    median: float,
    manual_codes: set[str],
) -> list[dict[str, Any]]:
    """Map point records coloured by the selected metric on the diverging scale."""
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
            "color": [*diverging_rgb(r.value(metric), vmin, vmax, median), 220],
            "manual": r.insee_code in manual_codes,
        }
        for r in rows
    ]


def build_map(records: list[dict[str, Any]], metric: str):
    """French map; every commune coloured by the selected metric, sized to scale with zoom.

    Manually-added communes get a second, larger white-ringed marker on top so the
    user can spot them among the ~1160 points.
    """
    df = pd.DataFrame(records)
    base = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        id="communes",
        get_position=["lon", "lat"],
        get_fill_color="color",
        get_radius=6000,  # mètres → la taille grandit au zoom
        radius_min_pixels=2,
        radius_max_pixels=30,
        pickable=True,
        stroked=True,
        get_line_color=[40, 40, 40],
        line_width_min_pixels=0.3,
        auto_highlight=True,
    )
    layers = [base]
    manual_df = df[df["manual"]]
    if not manual_df.empty:
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=manual_df,
                id="communes_manuelles",
                get_position=["lon", "lat"],
                get_fill_color="color",
                get_radius=11000,
                radius_min_pixels=6,
                radius_max_pixels=44,
                pickable=True,
                stroked=True,
                get_line_color=[255, 255, 255],
                line_width_min_pixels=2.5,
            )
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
        layers=layers,
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


def manual_lookup(index: list[Place]) -> list[Place]:
    """Validated commune search: returns the Places the user chose to add by name."""
    by_code = {p.insee_code: p for p in index}
    labels = {p.insee_code: f"{p.name} ({p.postal_code})" for p in index}

    def label(code: object) -> str:
        return labels.get(str(code), str(code))

    selected = st.multiselect(
        "🔍 Ajouter une commune précise",
        options=list(by_code),  # index is pre-sorted by name
        format_func=label,
        max_selections=MANUAL_MAX,
        placeholder="Tapez un nom de commune (ex. La Tremblade)…",
        help=(
            "Recherchez n'importe quelle commune de France métropolitaine. "
            "Sa prévision est récupérée à la demande et affichée avec les autres, "
            "sans être ajoutée au jeu de données quotidien."
        ),
    )
    return [by_code[c] for c in selected]


def add_manual_readings(
    manual_places: list[Place],
    existing: set[str],
    period_key: str,
    idx: int,
    readings: list[Reading],
    temps: dict[str, list[float | None]],
    apparent: dict[str, list[float | None]],
) -> tuple[dict[str, list[float | None]], dict[str, list[float | None]]]:
    """Fetch user-requested communes missing from the daily set, on demand.

    Appends their readings to ``readings`` and returns temperature views that
    include the manual series (copies, so the daily cache is never mutated). A
    commune the user picked that is already in the daily set needs no fetch.
    """
    to_fetch = [p for p in manual_places if p.insee_code not in existing]
    if not to_fetch:
        return temps, apparent

    temps_view = dict(temps)
    apparent_view = dict(apparent)
    failed: list[str] = []
    for place in to_fetch:
        try:
            t_list, a_list = get_manual_forecast(place, period_key)
        except Exception:  # réseau/API : on prévient l'utilisateur et on continue
            failed.append(place.name)
            continue
        temps_view[place.insee_code] = t_list
        apparent_view[place.insee_code] = a_list
        r = reading_at(place, t_list, a_list, idx)
        if r is not None:
            readings.append(r)
    if failed:
        st.warning(f"Prévision indisponible pour : {', '.join(failed)}.")
    return temps_view, apparent_view


def render_highlights(
    readings: list[Reading], manual_codes: set[str], metric: str, median: float
) -> None:
    """Compact readout of the user's chosen communes, with their rank in the field."""
    chosen = [r for r in readings if r.insee_code in manual_codes]
    if not chosen:
        return
    rank = {r.insee_code: i for i, r in enumerate(sorted(readings, key=lambda r: r.value(metric)))}
    total = len(readings)
    st.markdown("#### 📍 Vos communes")
    per_row = 4
    for start in range(0, len(chosen), per_row):
        row = chosen[start : start + per_row]
        for r, col in zip(row, st.columns(per_row), strict=False):
            with col:
                st.metric(
                    f"{r.name} ({r.departement_code})",
                    f"{r.value(metric):.1f} °C",
                    delta=f"{r.value(metric) - median:+.1f} °C vs médiane",
                    delta_color="off",
                )
                st.caption(f"{rank[r.insee_code] + 1}ᵉ / {total} (du plus frais au plus chaud)")


def main() -> None:
    st.title("🍫 ChoCacao")
    st.caption(
        "Les communes les plus chaudes et les plus fraîches de France métropolitaine — "
        "où profiter du soleil ou fuir la canicule."
    )

    period_key = forecast_period_key()
    try:
        places, times, temps, apparent = get_forecast(period_key)
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
            help="Critère utilisé pour le tableau, la médiane et la coloration de la carte.",
        )
        metric = metric or METRIC_TEMP  # le widget peut renvoyer None si désélectionné

    manual_places = manual_lookup(get_index())

    chosen = selected_date(date_value, default_date)
    target = f"{chosen.isoformat()}T{hour:02d}:00"
    when = format_fr(datetime.fromisoformat(target))
    try:
        idx = times.index(target)
    except ValueError:
        st.warning(f"Aucune prévision disponible pour {when}.")
        st.stop()

    readings = build_readings(places, temps, apparent, idx)
    # Communes ajoutées à la volée : récupérées à la demande, jamais stockées.
    existing = {p.insee_code for p in places}
    temps, apparent = add_manual_readings(
        manual_places, existing, period_key, idx, readings, temps, apparent
    )
    manual_codes = {p.insee_code for p in manual_places}
    if not readings:
        st.warning(f"Aucune prévision disponible pour {when}.")
        st.stop()

    # La médiane, l'écart, le tri et la carte suivent la mesure choisie.
    median = statistics.median(r.value(metric) for r in readings)
    values = [r.value(metric) for r in readings]
    vmin, vmax = min(values), max(values)
    ordered = sorted(readings, key=lambda r: r.value(metric))  # du plus frais au plus chaud

    st.subheader(f"{when} · {len(readings)} communes · médiane {median:.1f} °C ({metric.lower()})")

    render_highlights(readings, manual_codes, metric, median)

    st.markdown("### 🌡️ Toutes les communes")
    st.caption(
        "Triées du plus frais au plus chaud. Cliquez sur un en-tête de colonne pour trier "
        "(commune, département, air, ressentie) — décroissant pour voir les plus chaudes."
    )
    render_table(ordered, metric, vmin, vmax, median, manual_codes)

    st.subheader("🗺️ Carte")
    st.caption("Cliquez sur un point pour afficher le détail et l'évolution sur 48 h.")
    by_insee = {r.insee_code: r for r in readings}
    records = map_records(readings, metric, vmin, vmax, median, manual_codes)
    event = build_map(records, metric)

    sel = getattr(event, "selection", None) or {}
    objects = sel.get("objects") or {}
    # Un point ajouté à la volée est dans les deux couches ; deck.gl renvoie la
    # couche du dessus ("communes_manuelles"), sinon la couche de base.
    objs = objects.get("communes") or objects.get("communes_manuelles") or []
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
