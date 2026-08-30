"""
Public Health Heat-Emergency Predictor - v2
Multi-city, point-based, geocoding search, analytical charts, API caching,
follow-up chat, SQLite history/trends, real parallel scanning, NWS-sourced
risk scoring, custom zone tracking, and scan-over-scan alerting.
"""

import os
import sqlite3
import pathlib
import requests
import concurrent.futures
import pandas as pd
from datetime import date, datetime
import streamlit as st
from dotenv import load_dotenv
from google import genai
from fortyguard import FortyGuardClient

load_dotenv()

# Page Configuration with premium layout
st.set_page_config(page_title="Heat Emergency Predictor", page_icon="🌡️", layout="wide")

# ---------------------------------------------------------------------------
# NOTE ON THEME: a companion .streamlit/config.toml sets a global dark theme
# (base="dark", matching background/text colors). That's what actually makes
# native widgets (charts, chat, sidebar, inputs, dataframes) render legibly --
# CSS injected via st.markdown only reaches elements we hand-style below, it
# can't retheme Streamlit's own components. Keep both files together.
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif;
        color: #f3f4f6;
    }

    h1, h2, h3, .hero h1 {
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
    }

    .hero {
        background: linear-gradient(135deg, rgba(255, 75, 43, 0.9) 0%, rgba(255, 115, 0, 0.9) 50%, rgba(220, 20, 60, 0.95) 100%);
        padding: 2.2rem 2.2rem;
        border-radius: 20px;
        color: white;
        margin-bottom: 1.5rem;
        box-shadow: 0 10px 30px rgba(255, 75, 43, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .hero h1 { color: white; margin: 0 0 0.5rem 0; font-size: 2.2rem; letter-spacing: -0.5px; }
    .hero p { color: rgba(255, 255, 255, 0.95); margin: 0; font-size: 1.0rem; line-height: 1.6; max-width: 900px; }

    .zone-card {
        background: rgba(30, 33, 48, 0.9);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 16px rgba(0,0,0,0.25);
        transition: all 0.2s ease;
    }
    .zone-card:hover { transform: translateY(-3px); border-color: rgba(255, 75, 43, 0.4); }

    .metric-row {
        display: flex; justify-content: space-between; margin-bottom: 0.4rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08); padding-bottom: 0.3rem;
    }
    .metric-label { font-size: 0.85rem; color: #b6bac4; font-weight: 500; }
    .metric-value { font-size: 0.95rem; font-weight: 700; color: #ffffff; }

    .card-title {
        font-size: 1.15rem; font-weight: 700; color: #ffffff; margin-bottom: 0.7rem;
        display: flex; justify-content: space-between; align-items: center;
    }

    .risk-badge {
        font-size: 0.72rem; font-weight: 800; padding: 0.2rem 0.6rem; border-radius: 12px;
        text-transform: uppercase; color: white; letter-spacing: 0.3px;
    }

    /* Big glanceable stat tiles */
    .stat-tile {
        background: rgba(30, 33, 48, 0.9);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 1rem 1.2rem;
        text-align: left;
    }
    .stat-tile .stat-value { font-family: 'Outfit', sans-serif; font-size: 1.9rem; font-weight: 800; color: #ffffff; }
    .stat-tile .stat-label { font-size: 0.8rem; color: #b6bac4; margin-top: 0.2rem; }

    /* Native Streamlit widgets -- explicit contrast so nothing goes invisible */
    div.stButton > button {
        background: linear-gradient(135deg, #ff4b2b 0%, #ff7300 100%) !important;
        color: white !important; border: none !important; border-radius: 12px !important;
        padding: 0.7rem 1.6rem !important; font-weight: 700 !important;
        font-family: 'Outfit', sans-serif !important; width: 100% !important;
        box-shadow: 0 4px 15px rgba(255, 75, 43, 0.25) !important;
    }
    div.stButton > button:hover { transform: translateY(-2px) !important; color: white !important; }

    /* ── Sidebar: dark blue glassmorphism ───────────────────────────── */
    [data-testid="stSidebar"] {
        background: linear-gradient(160deg, rgba(8, 15, 45, 0.92) 0%, rgba(12, 24, 68, 0.90) 55%, rgba(9, 18, 55, 0.94) 100%);
        backdrop-filter: blur(18px) saturate(140%);
        -webkit-backdrop-filter: blur(18px) saturate(140%);
        border-right: 1px solid rgba(255, 255, 255, 0.10);
        box-shadow: 4px 0 24px rgba(0, 0, 20, 0.35);
    }
    [data-testid="stSidebar"] * { color: #f5f7ff; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #ffffff !important; }
    [data-testid="stSidebar"] hr { border-color: rgba(255, 255, 255, 0.15); }
    [data-testid="stSidebar"] .stCaption, [data-testid="stSidebar"] small { color: #c7d0f5 !important; }

    /* Glass panels behind sidebar controls (form + expander) for extra depth */
    [data-testid="stSidebar"] [data-testid="stForm"],
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.14);
        border-radius: 14px;
        padding: 0.8rem;
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
    }

    /* ── Input fields: clearly visible everywhere, sidebar included ─── */
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stTextArea"] textarea,
    div[data-baseweb="select"] > div,
    [data-testid="stChatInput"] textarea {
        background-color: rgba(255, 255, 255, 0.96) !important;
        color: #12141f !important;
        border: 1.5px solid rgba(255, 255, 255, 0.55) !important;
        border-radius: 10px !important;
        caret-color: #12141f !important;
    }
    [data-testid="stTextInput"] input::placeholder,
    [data-testid="stTextArea"] textarea::placeholder,
    [data-testid="stChatInput"] textarea::placeholder { color: #6b7280 !important; }
    [data-testid="stTextInput"] label,
    [data-testid="stNumberInput"] label,
    [data-testid="stTextArea"] label,
    [data-testid="stSelectbox"] label { color: #f5f7ff !important; font-weight: 500; }
    div[data-baseweb="select"] span { color: #12141f !important; }
    [data-testid="stSidebar"] [data-testid="stTextInput"] input,
    [data-testid="stSidebar"] div[data-baseweb="select"] > div {
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.25) !important;
    }

    [data-testid="stChatMessage"] { background: rgba(30, 33, 48, 0.85); border-radius: 12px; }
    [data-testid="stMetricValue"] { color: #ffffff; }
    [data-testid="stMetricLabel"] { color: #b6bac4; }

    .alert-banner {
        background: rgba(217, 46, 46, 0.15); border-left: 5px solid #d92e2e;
        padding: 0.9rem 1.3rem; border-radius: 10px; margin-bottom: 1.2rem;
        color: #ffdad6; font-weight: 500;
    }
    .info-banner {
        background: rgba(255, 75, 43, 0.08); border-left: 5px solid #ff4b2b;
        padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1.5rem;
    }
    .footer-note {
        text-align: center; color: #6b7280; font-size: 0.85rem; margin-top: 3rem;
        padding: 1.5rem 0; border-top: 1px solid rgba(255, 255, 255, 0.08);
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# API / DB init -- fail loudly and early, not deep inside a callback
# ---------------------------------------------------------------------------

DB_PATH = pathlib.Path(__file__).parent / "heat_history.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scanned_at TEXT NOT NULL,
            city TEXT NOT NULL,
            zone_name TEXT NOT NULL,
            lat REAL, lon REAL,
            heat_index REAL, apparent_temp REAL, humidity REAL,
            median_income INTEGER, pct_elderly REAL,
            risk TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS custom_zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city TEXT NOT NULL,
            name TEXT NOT NULL,
            lat REAL, lon REAL, zip TEXT,
            added_at TEXT
        )
    """)
    conn.commit()
    conn.close()


init_db()

missing_keys = []
if not os.getenv("GOOGLE_API_KEY"):
    missing_keys.append("GOOGLE_API_KEY (AI narrative reports)")
if not os.getenv("CENSUS_API_KEY"):
    missing_keys.append("CENSUS_API_KEY (income / elderly-% demographics)")

fg_ready, fg_error = True, None
try:
    fg_client = FortyGuardClient()
except Exception as e:
    fg_ready = False
    fg_error = str(e)

gemini_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY")) if os.getenv("GOOGLE_API_KEY") else None
CENSUS_KEY = os.getenv("CENSUS_API_KEY")

TODAY = date.today().isoformat()
CHECK_TIME = "15:00"

RISK_ORDER = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "EXTREME": 3}
RISK_COLORS_HEX = {"EXTREME": "#d92e2e", "HIGH": "#ff8c42", "MODERATE": "#ffc94a", "LOW": "#4caf7d", "UNKNOWN": "#999999"}
RISK_COLORS_RGB = {"EXTREME": [217, 46, 46], "HIGH": [255, 140, 66], "MODERATE": [255, 201, 74], "LOW": [76, 175, 125], "UNKNOWN": [153, 153, 153]}

CITIES = {
    "Los Angeles, CA": {"zones": [
        {"name": "Beverly Hills", "lat": 34.0736, "lon": -118.4004, "zip": "90210"},
        {"name": "Bel Air", "lat": 34.1004, "lon": -118.4595, "zip": "90077"},
        {"name": "Downtown LA", "lat": 34.0407, "lon": -118.2468, "zip": "90012"},
        {"name": "South LA (Watts)", "lat": 33.9425, "lon": -118.2468, "zip": "90002"},
        {"name": "Pacoima", "lat": 34.2597, "lon": -118.4076, "zip": "91331"},
        {"name": "Santa Monica", "lat": 34.0195, "lon": -118.4912, "zip": "90401"},
    ]},
    "Houston, TX": {"zones": [
        {"name": "River Oaks", "lat": 29.7534, "lon": -95.4184, "zip": "77019"},
        {"name": "Memorial", "lat": 29.7700, "lon": -95.5430, "zip": "77024"},
        {"name": "Downtown Houston", "lat": 29.7604, "lon": -95.3698, "zip": "77002"},
        {"name": "Third Ward", "lat": 29.7280, "lon": -95.3630, "zip": "77004"},
        {"name": "Sunnyside", "lat": 29.6704, "lon": -95.3860, "zip": "77051"},
        {"name": "Alief", "lat": 29.7133, "lon": -95.5872, "zip": "77072"},
    ]},
    "New York, NY": {"zones": [
        {"name": "Harlem", "lat": 40.8116, "lon": -73.9465, "zip": "10027"},
        {"name": "Upper East Side", "lat": 40.7736, "lon": -73.9566, "zip": "10021"},
        {"name": "Chinatown", "lat": 40.7158, "lon": -73.9970, "zip": "10002"},
        {"name": "Astoria (Queens)", "lat": 40.7644, "lon": -73.9235, "zip": "11102"},
        {"name": "Bedford-Stuyvesant (Brooklyn)", "lat": 40.6872, "lon": -73.9418, "zip": "11216"},
        {"name": "South Bronx", "lat": 40.8130, "lon": -73.9060, "zip": "10454"},
    ]},
    "Phoenix, AZ": {"zones": [
        {"name": "Downtown Phoenix", "lat": 33.4484, "lon": -112.0740, "zip": "85003"},
        {"name": "Maryvale", "lat": 33.4900, "lon": -112.1800, "zip": "85033"},
        {"name": "Paradise Valley", "lat": 33.5312, "lon": -111.9427, "zip": "85253"},
        {"name": "South Phoenix", "lat": 33.4000, "lon": -112.0700, "zip": "85040"},
        {"name": "Sunnyslope", "lat": 33.5700, "lon": -112.0700, "zip": "85020"},
        {"name": "Tempe", "lat": 33.4255, "lon": -111.9400, "zip": "85281"},
    ]},
}


# ---------------------------------------------------------------------------
# Risk scoring -- grounded in the official NWS Heat Index categories
# (weather.gov): Caution >=80F/27C, Extreme Caution >=90F/32C,
# Danger >=103F/39C, Extreme Danger >=125F/52C. Vulnerability (low income or
# high elderly %) bumps a zone up one tier.
# ---------------------------------------------------------------------------

def nws_heat_category(heat_index_c: float | None) -> str:
    if heat_index_c is None:
        return "UNKNOWN"
    f = heat_index_c * 9 / 5 + 32
    if f >= 125:
        return "EXTREME_DANGER"
    elif f >= 103:
        return "DANGER"
    elif f >= 90:
        return "EXTREME_CAUTION"
    elif f >= 80:
        return "CAUTION"
    return "NONE"


def classify_risk(heat_index: float | None, income: int | None, elderly_pct: float | None) -> str:
    """NWS heat category, bumped one tier by socio-economic vulnerability."""
    category = nws_heat_category(heat_index)
    if category == "UNKNOWN":
        return "UNKNOWN"
    vulnerable = (income is not None and income < 70000) or (elderly_pct is not None and elderly_pct > 20)
    if category == "EXTREME_DANGER":
        return "EXTREME"
    if category == "DANGER":
        return "EXTREME" if vulnerable else "HIGH"
    if category == "EXTREME_CAUTION":
        return "HIGH" if vulnerable else "MODERATE"
    if category == "CAUTION":
        return "MODERATE" if vulnerable else "LOW"
    return "LOW"


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

def geocode_zip(zip_code: str) -> tuple[float, float, str] | None:
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={zip_code}&format=json&countrycodes=us&limit=1"
        headers = {"User-Agent": "HeatEmergencyPredictorAgent/2.0"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200 and r.json():
            data = r.json()[0]
            return float(data["lat"]), float(data["lon"]), data.get("display_name", f"ZIP {zip_code}")
    except Exception:
        pass
    return None


def geocode_address(query: str) -> dict | None:
    """Free-form address/place geocoding, also recovers a ZIP for census lookup."""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": query, "format": "json", "countrycodes": "us", "limit": 1, "addressdetails": 1}
        headers = {"User-Agent": "HeatEmergencyPredictorAgent/2.0"}
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200 and r.json():
            data = r.json()[0]
            return {
                "lat": float(data["lat"]),
                "lon": float(data["lon"]),
                "display_name": data.get("display_name", query),
                "zip": data.get("address", {}).get("postcode", ""),
            }
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# API-backed data fetchers (cached)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=86400)
def get_census_data(zip_code: str) -> dict:
    if not zip_code:
        return {"median_income": None, "pct_elderly": None}
    try:
        income_url = (f"https://api.census.gov/data/2022/acs/acs5"
                       f"?get=B19013_001E&for=zip%20code%20tabulation%20area:{zip_code}&key={CENSUS_KEY}")
        median_income = requests.get(income_url, timeout=15).json()[1][0]
        elderly_url = (f"https://api.census.gov/data/2022/acs/acs5/subject"
                        f"?get=S0101_C02_030E&for=zip%20code%20tabulation%20area:{zip_code}&key={CENSUS_KEY}")
        pct_elderly = requests.get(elderly_url, timeout=15).json()[1][0]
        return {
            "median_income": int(median_income) if median_income not in (None, "-666666666") else None,
            "pct_elderly": float(pct_elderly) if pct_elderly not in (None, "-666666666") else None,
        }
    except Exception:
        return {"median_income": None, "pct_elderly": None}


@st.cache_data(ttl=1800)
def get_heat_data(lat: float, lon: float) -> dict:
    response = fg_client.environmental_parameters(
        latitude=lat, longitude=lon, temperature=35.0,
        start_date=TODAY, start_time=CHECK_TIME, end_date=TODAY, end_time=CHECK_TIME, filter_type=1,
    )
    result = response["result"]
    params = result["locations"][0].get("parameters", {})

    def extract_val(key):
        val = params.get(key)
        return (val[0] if val else None) if isinstance(val, list) else val

    return {
        "heat_index": extract_val("heat_index_celsius"),
        "apparent_temp": extract_val("apparent_temperature_celsius"),
        "humidity": extract_val("relative_humidity_percent"),
    }


def compute_heat_index_f(temp_f: float, rh_pct: float) -> float | None:
    """Official NWS Rothfusz regression. Only valid/defined for T >= 80F --
    below that the heat index isn't meaningfully different from air temp,
    so we return None (treated as no heat risk) rather than a fake number."""
    if temp_f is None or rh_pct is None or temp_f < 80:
        return None
    T, RH = temp_f, rh_pct
    hi = (-42.379 + 2.04901523 * T + 10.14333127 * RH - 0.22475541 * T * RH
          - 0.00683783 * T * T - 0.05481717 * RH * RH + 0.00122874 * T * T * RH
          + 0.00085282 * T * RH * RH - 0.00000199788 * T * T * RH * RH)
    if RH < 13 and 80 <= T <= 112:
        hi -= ((13 - RH) / 4) * (((17 - abs(T - 95.0)) / 17) ** 0.5)
    elif RH > 85 and 80 <= T <= 87:
        hi += ((RH - 85) / 10) * ((87 - T) / 5)
    if hi < 50 or hi > 200:  # sanity clamp -- physically implausible for a heat index in F
        return None
    return hi


@st.cache_data(ttl=1800)
def get_nws_forecast(lat: float, lon: float) -> pd.DataFrame:
    """Real 48-hour hourly forecast from the National Weather Service
    (api.weather.gov, free, no key, US-only), converted to heat index via
    the same official NWS formula used for current-conditions risk scoring."""
    headers = {"User-Agent": "HeatEmergencyPredictorAgent/2.1 (hackathon project)"}
    points = requests.get(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}", headers=headers, timeout=15)
    points.raise_for_status()
    hourly_url = points.json()["properties"]["forecastHourly"]

    hourly = requests.get(hourly_url, headers=headers, timeout=15)
    hourly.raise_for_status()
    periods = hourly.json()["properties"]["periods"]

    rows = []
    for p in periods[:48]:
        temp_f = p.get("temperature")
        rh = (p.get("relativeHumidity") or {}).get("value")
        if temp_f is None or rh is None:
            continue
        hi_f = compute_heat_index_f(temp_f, rh)
        rows.append({
            "timestamp": pd.to_datetime(p["startTime"]),
            "temp_f": temp_f,
            "humidity_pct": rh,
            "heat_index_c": ((hi_f - 32) * 5 / 9) if hi_f is not None else None,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.set_index("timestamp")
    return df


def summarize_forecast_risk(forecast_df: pd.DataFrame, income: int | None, elderly_pct: float | None) -> dict:
    """Peak forecasted risk over the window and when it's expected."""
    if forecast_df.empty:
        return {"peak_risk": "UNKNOWN", "peak_time": None, "hours_until": None}
    risks = forecast_df["heat_index_c"].apply(lambda hi: classify_risk(hi, income, elderly_pct))
    order = risks.map(lambda r: RISK_ORDER.get(r, -1))
    peak_idx = order.idxmax()
    hours_until = (peak_idx - pd.Timestamp.now(tz=peak_idx.tzinfo)).total_seconds() / 3600
    return {"peak_risk": risks.loc[peak_idx], "peak_time": peak_idx, "hours_until": max(0, hours_until)}


@st.cache_data(ttl=1800)
def get_intraday_trend(lat: float, lon: float) -> pd.DataFrame:
    """Real intraday heat-index trend for today so far (midnight -> now), not a forecast."""
    response = fg_client.environmental_parameters(
        latitude=lat, longitude=lon, temperature=35.0,
        start_date=TODAY, start_time="00:00", end_date=TODAY, end_time=CHECK_TIME, filter_type=2,
    )
    result = response["result"]
    location = result["locations"][0]
    timestamps = result["metadata"].get("timestamps", [])
    params = location.get("parameters", {})
    df = pd.DataFrame({k: v for k, v in params.items() if isinstance(v, list) and len(v) == len(timestamps)})
    if not df.empty:
        df.insert(0, "timestamp", pd.to_datetime(timestamps))
        df.set_index("timestamp", inplace=True)
    return df


def scan_zones(zones: list[dict]) -> list[dict]:
    """Fully parallel: heat + census requests for every zone are all in
    flight at once (not just heat, with census tacked on serially after)."""
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(16, max(1, len(zones) * 2))) as executor:
        heat_futures = {executor.submit(get_heat_data, z["lat"], z["lon"]): z for z in zones}
        census_futures = {executor.submit(get_census_data, z.get("zip", "")): z for z in zones}

        heat_by_zone, census_by_zone = {}, {}
        for future in concurrent.futures.as_completed(heat_futures):
            zone = heat_futures[future]
            try:
                heat_by_zone[zone["name"]] = future.result(timeout=60)
            except Exception as e:
                st.warning(f"Could not fetch heat data for {zone['name']}: {e}")
        for future in concurrent.futures.as_completed(census_futures):
            zone = census_futures[future]
            try:
                census_by_zone[zone["name"]] = future.result(timeout=60)
            except Exception:
                census_by_zone[zone["name"]] = {"median_income": None, "pct_elderly": None}

    for z in zones:
        heat_data = heat_by_zone.get(z["name"])
        if heat_data is None:
            continue
        census_data = census_by_zone.get(z["name"], {"median_income": None, "pct_elderly": None})
        risk = classify_risk(heat_data.get("heat_index"), census_data.get("median_income"), census_data.get("pct_elderly"))
        results.append({"name": z["name"], "lat": z["lat"], "lon": z["lon"], "risk": risk, **heat_data, **census_data})
    return results


# ---------------------------------------------------------------------------
# Persistence -- scan history, trend queries, custom zones
# ---------------------------------------------------------------------------

def log_scan_results(city: str, zone_results: list[dict]):
    conn = sqlite3.connect(DB_PATH)
    now = datetime.now().isoformat(timespec="seconds")
    conn.executemany(
        """INSERT INTO scan_log
           (scanned_at, city, zone_name, lat, lon, heat_index, apparent_temp, humidity, median_income, pct_elderly, risk)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        [(now, city, z["name"], z["lat"], z["lon"], z.get("heat_index"), z.get("apparent_temp"),
          z.get("humidity"), z.get("median_income"), z.get("pct_elderly"), z["risk"]) for z in zone_results],
    )
    conn.commit()
    conn.close()


def get_last_risks(city: str) -> dict:
    """{zone_name: risk} from the most recent scan of this city, BEFORE the current one."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        """SELECT zone_name, risk FROM scan_log
           WHERE city = ? AND scanned_at = (SELECT MAX(scanned_at) FROM scan_log WHERE city = ?)""",
        (city, city),
    )
    rows = dict(cur.fetchall())
    conn.close()
    return rows


def get_zone_history(city: str, zone_name: str, limit: int = 100) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """SELECT scanned_at, heat_index, apparent_temp, humidity, risk FROM scan_log
           WHERE city=? AND zone_name=? ORDER BY scanned_at DESC LIMIT ?""",
        conn, params=(city, zone_name, limit),
    )
    conn.close()
    if not df.empty:
        df["scanned_at"] = pd.to_datetime(df["scanned_at"])
        df = df.set_index("scanned_at").sort_index()
    return df


def add_custom_zone(city: str, name: str, lat: float, lon: float, zip_code: str = ""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO custom_zones (city, name, lat, lon, zip, added_at) VALUES (?,?,?,?,?,?)",
        (city, name, lat, lon, zip_code, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def get_custom_zones(city: str) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT name, lat, lon, zip FROM custom_zones WHERE city=?", (city,))
    rows = cur.fetchall()
    conn.close()
    return [{"name": r[0], "lat": r[1], "lon": r[2], "zip": r[3] or ""} for r in rows]


def get_zones_for_city(city: str) -> list[dict]:
    return CITIES[city]["zones"] + get_custom_zones(city)


# ---------------------------------------------------------------------------
# AI narrative
# ---------------------------------------------------------------------------

def _call_gemini_with_retry(prompt: str, max_attempts: int = 3):
    """Retries transient Gemini errors (503 overload, timeouts) with backoff.
    Does NOT retry on auth/quota errors -- those won't fix themselves."""
    import time
    last_err = None
    for attempt in range(max_attempts):
        try:
            return gemini_client.models.generate_content(model="gemini-3.6-flash", contents=prompt)
        except Exception as e:
            last_err = e
            msg = str(e)
            transient = "503" in msg or "UNAVAILABLE" in msg or "overload" in msg.lower() or "timeout" in msg.lower()
            if not transient or attempt == max_attempts - 1:
                raise
            time.sleep(2 ** attempt)  # 1s, 2s, 4s
    raise last_err


def generate_report(city: str, zone_results: list) -> str:
    if gemini_client is None:
        return "_AI narrative disabled: GOOGLE_API_KEY is not set._"
    zones_summary = "\n".join(
        (f"- {z['name']} [computed risk: {z['risk']}]: heat index {z['heat_index']}C, "
         f"apparent temp {z['apparent_temp']}C, humidity {z['humidity']}% | "
         f"Median income: ${z['median_income']:,} | Elderly population: {z['pct_elderly']}%")
        if z['median_income'] and z['pct_elderly'] is not None
        else f"- {z['name']} [computed risk: {z['risk']}]: heat index {z['heat_index']}C | Census data unavailable"
        for z in zone_results
    )
    heat_indices = [z["heat_index"] for z in zone_results if z.get("heat_index") is not None]
    if heat_indices:
        overview_line = (f"Heat Index range across analyzed zones in {city}: "
                          f"{min(heat_indices):.1f}C to {max(heat_indices):.1f}C, average {sum(heat_indices)/len(heat_indices):.1f}C.")
    else:
        overview_line = f"No temperature data was available for analyzed zones in {city} today."

    prompt = f"""
You are a public-health heat-emergency analyst for {city}.

STEP 1 -- CITY-WIDE OVERVIEW: {overview_line}

STEP 2 -- DETAILED NEIGHBORHOOD DATA (real environmental + real US Census data), collected today ({TODAY}, {CHECK_TIME}):
{zones_summary}

Risk levels are computed from the official NWS Heat Index categories (Caution/Extreme Caution/Danger/Extreme
Danger), bumped one tier for zones with median income under $70k or elderly population over 20%. Use these as
your ranking basis but explain the reasoning in your own words.

Task:
1. Briefly summarize the city-wide picture (1-2 sentences).
2. List neighborhoods from HIGHEST to LOWEST risk with a one-line explanation each.
3. For the top 3 highest-risk zones, give a specific, actionable recommendation.
4. Format with clear markdown headers. Keep under 350 words.
"""
    try:
        response = _call_gemini_with_retry(prompt)
        return response.text
    except Exception as e:
        return (f"_AI report temporarily unavailable ({e}). "
                f"Your scan data below is still real and current -- use the 'Regenerate AI report' "
                f"button once Gemini recovers._")


def answer_followup(city: str, report: str, zone_results: list, question: str) -> str:
    if gemini_client is None:
        return "AI chat is disabled because GOOGLE_API_KEY is not set."
    context = f"""
You are the same public-health heat-emergency analyst who just wrote this report for {city}:

{report}

Underlying data: {zone_results}

The user now asks a follow-up question: "{question}"

Answer directly and concisely (2-4 sentences), using the data above.
"""
    try:
        response = _call_gemini_with_retry(context)
        return response.text
    except Exception as e:
        return f"AI chat is temporarily unavailable ({e}). Try again in a moment."


# ── SIDEBAR ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌡️ Controls")

    if not fg_ready:
        st.error(f"FortyGuard client failed to init: {fg_error}")
    if missing_keys:
        with st.expander("⚠️ Missing API keys", expanded=True):
            for k in missing_keys:
                st.write(f"- {k}")
            st.caption("The app still runs, but the features tied to those keys are disabled below.")

    city = st.selectbox("Region", list(CITIES.keys()))
    run_scan = st.button("🔍 Analyze Heat-Emergency Risks", type="primary")

    st.markdown("---")
    st.markdown("### ➕ Add a tracked zone")
    st.caption("Adds a neighborhood/address to this city's dashboard permanently (saved locally).")
    with st.form("add_zone_form", clear_on_submit=True):
        new_zone_label = st.text_input("Zone name")
        new_zone_query = st.text_input("Address, place, or ZIP")
        submitted = st.form_submit_button("Add to dashboard")
        if submitted:
            if not new_zone_query.strip():
                st.warning("Enter an address, place, or ZIP first.")
            else:
                geo = geocode_address(new_zone_query.strip())
                if not geo:
                    st.error("Couldn't geocode that. Try a more specific query.")
                else:
                    label = new_zone_label.strip() or geo["display_name"].split(",")[0]
                    add_custom_zone(city, label, geo["lat"], geo["lon"], geo["zip"])
                    st.success(f"Added '{label}' to {city}.")
                    st.cache_data.clear()

    st.markdown("---")
    st.caption(f"Local history DB: `{DB_PATH.name}`")
    if st.button("🗑️ Clear scan history (this app instance)"):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM scan_log")
        conn.commit()
        conn.close()
        st.success("History cleared.")

# ── HERO BANNER ──────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <h1>🌡️ Heat-Emergency Predictor</h1>
    <p>Combining live FortyGuard heat data with US Census Bureau vulnerability statistics to flag
    neighborhoods where heat exposure and socio-economic resilience intersect -- so limited outreach
    resources go where they matter most.</p>
</div>
""", unsafe_allow_html=True)

tab_dashboard, tab_charts, tab_history, tab_custom_search, tab_resources = st.tabs([
    "🌐 City Dashboard", "📈 Analytical Charts", "🕒 History & Trends", "🔍 Custom Zone Analyzer", "📚 Resource Guide",
])

# ── TAB 1: CITY DASHBOARD ────────────────────────────────────
with tab_dashboard:
    if run_scan:
        if not fg_ready:
            st.error("Can't scan: FortyGuard client isn't initialized. Check your API key.")
        else:
            st.session_state.pop("chat_history", None)
            zones = get_zones_for_city(city)
            previous_risks = get_last_risks(city)  # snapshot BEFORE this scan overwrites it

            with st.spinner(f"Scanning {len(zones)} zones in parallel..."):
                zone_results = scan_zones(zones)

            if zone_results:
                log_scan_results(city, zone_results)
                st.session_state["report"] = generate_report(city, zone_results)
                st.session_state["zone_results"] = zone_results
                st.session_state["city"] = city

                escalations = [
                    z["name"] for z in zone_results
                    if z["risk"] in RISK_ORDER and previous_risks.get(z["name"]) in RISK_ORDER
                    and RISK_ORDER[z["risk"]] > RISK_ORDER[previous_risks[z["name"]]]
                ]
                st.session_state["escalations"] = escalations
                st.success(f"✅ Assessment complete -- {len(zone_results)} zones scanned.")

    if "zone_results" in st.session_state and st.session_state.get("city") == city:
        zone_results = st.session_state["zone_results"]
        report = st.session_state["report"]

        if st.session_state.get("escalations"):
            st.markdown(
                f'<div class="alert-banner">⚠️ Risk increased since the last scan in: '
                f'<b>{", ".join(st.session_state["escalations"])}</b></div>',
                unsafe_allow_html=True,
            )

        heat_indices = [z["heat_index"] for z in zone_results if z.get("heat_index") is not None]
        extreme_count = sum(1 for z in zone_results if z["risk"] == "EXTREME")
        high_count = sum(1 for z in zone_results if z["risk"] == "HIGH")

        s1, s2, s3, s4 = st.columns(4)
        for col, value, label in [
            (s1, f"{min(heat_indices):.1f}-{max(heat_indices):.1f}C" if heat_indices else "N/A", "Heat index range"),
            (s2, f"{(sum(heat_indices)/len(heat_indices)):.1f}C" if heat_indices else "N/A", "City-wide average"),
            (s3, str(extreme_count), "Zones at EXTREME risk"),
            (s4, str(high_count), "Zones at HIGH risk"),
        ]:
            col.markdown(f'<div class="stat-tile"><div class="stat-value">{value}</div><div class="stat-label">{label}</div></div>', unsafe_allow_html=True)

        st.markdown("")
        col_map, col_report = st.columns([1, 1])

        with col_map:
            st.markdown("### 🗺️ Incident Point Mapping")
            map_df = pd.DataFrame(zone_results)
            map_df["color"] = map_df["risk"].map(RISK_COLORS_RGB)
            st.map(map_df, latitude="lat", longitude="lon", color="color", size=300)
            st.caption("🔴 Extreme · 🟠 High · 🟡 Moderate · 🟢 Low")

            st.markdown("### 📊 Neighborhood Snapshot Cards")
            cols = st.columns(2)
            for idx, z in enumerate(zone_results):
                with cols[idx % 2]:
                    income_str = f"${z['median_income']:,}" if z['median_income'] else "N/A"
                    elderly_str = f"{z['pct_elderly']}%" if z['pct_elderly'] is not None else "N/A"
                    risk_color = RISK_COLORS_HEX.get(z['risk'], "#999999")
                    heat_str = f"{z['heat_index']:.1f}°C" if z.get('heat_index') is not None else "N/A"
                    humid_str = f"{z['humidity']:.1f}%" if z.get('humidity') is not None else "N/A"
                    st.markdown(f"""
                    <div class="zone-card">
                        <div class="card-title">{z['name']}<span class="risk-badge" style="background-color: {risk_color};">{z['risk']}</span></div>
                        <div class="metric-row"><span class="metric-label">🌡️ Heat Index</span><span class="metric-value">{heat_str}</span></div>
                        <div class="metric-row"><span class="metric-label">💧 Relative Humidity</span><span class="metric-value">{humid_str}</span></div>
                        <div class="metric-row"><span class="metric-label">💰 Median Income</span><span class="metric-value">{income_str}</span></div>
                        <div class="metric-row" style="border: none;"><span class="metric-label">👵 Elderly Population</span><span class="metric-value">{elderly_str}</span></div>
                    </div>
                    """, unsafe_allow_html=True)

        with col_report:
            report_header_col, report_btn_col = st.columns([3, 1])
            report_header_col.markdown("### 📋 Executive Public-Health Report")
            if report_btn_col.button("🔄 Regenerate"):
                with st.spinner("Retrying AI report..."):
                    st.session_state["report"] = generate_report(city, zone_results)
                    report = st.session_state["report"]
            st.markdown(report)

            download_text = f"# Heat-Emergency Report — {city}\nGenerated: {TODAY} {CHECK_TIME}\n\n{report}"
            st.download_button("📥 Download Report (Markdown)", data=download_text,
                                file_name=f"heat_report_{city.split(',')[0].replace(' ', '_')}_{TODAY}.md",
                                mime="text/markdown")

            st.markdown("---")
            st.markdown("### 💬 Conversational Follow-up Agent")
            if "chat_history" not in st.session_state:
                st.session_state["chat_history"] = []
            for role, msg in st.session_state["chat_history"]:
                with st.chat_message(role):
                    st.markdown(msg)
            question = st.chat_input("Ask details, e.g., 'Compare South LA and Beverly Hills vulnerability factors'")
            if question:
                st.session_state["chat_history"].append(("user", question))
                with st.chat_message("user"):
                    st.markdown(question)
                with st.chat_message("assistant"):
                    with st.spinner("Analyzing parameters..."):
                        answer = answer_followup(city, report, zone_results, question)
                    st.markdown(answer)
                st.session_state["chat_history"].append(("assistant", answer))
    else:
        st.info("💡 Select a region and click 'Analyze Heat-Emergency Risks' in the sidebar to start.")

# ── TAB 2: ANALYTICAL CHARTS ─────────────────────────────────
with tab_charts:
    st.markdown("### 📈 Socioeconomic Heat Vulnerability Distribution")
    if "zone_results" in st.session_state and st.session_state.get("city") == city:
        zone_results = st.session_state["zone_results"]
        df_chart = pd.DataFrame(zone_results)
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown("#### 🔬 Heat Index vs. Household Income (Sized by Elderly %)")
            st.scatter_chart(data=df_chart, x="median_income", y="heat_index", color="risk", size="pct_elderly", use_container_width=True)
            st.caption("Each dot is a neighborhood. Y-axis: heat index (C). X-axis: median household income. Size: elderly %.")
        with col_c2:
            st.markdown("#### 🌡️ Temperature Metrics by Zone")
            st.bar_chart(data=df_chart, x="name", y=["heat_index", "apparent_temp"], use_container_width=True)
            st.caption("Comparative Heat Index and Apparent Temperature across neighborhoods.")
    else:
        st.info("📊 Run a scan in the 'City Dashboard' tab first to populate interactive charts.")

# ── TAB 3: HISTORY & TRENDS ───────────────────────────────────
with tab_history:
    st.markdown("### 🕒 History & Trends")
    st.caption("Longitudinal view across your saved scans, plus today's real intraday trend for one zone (not a forecast).")

    zones = get_zones_for_city(city)
    zone_names = [z["name"] for z in zones]
    if not zone_names:
        st.info("No zones tracked for this city yet.")
    else:
        selected_zone = st.selectbox("Zone", zone_names, key="history_zone")
        hist_df = get_zone_history(city, selected_zone)

        if hist_df.empty:
            st.info(f"No saved scans yet for {selected_zone}. Run a scan in the City Dashboard tab to start building history.")
        else:
            st.markdown(f"#### Heat index over past scans -- {selected_zone}")
            st.line_chart(hist_df[["heat_index", "apparent_temp"]], use_container_width=True)
            st.dataframe(hist_df.tail(20)[["heat_index", "apparent_temp", "humidity", "risk"]], use_container_width=True)

        st.markdown("---")
        st.markdown(f"#### Today's intraday trend -- {selected_zone}")
        zone_obj = next((z for z in zones if z["name"] == selected_zone), None)
        if zone_obj and fg_ready:
            with st.spinner("Fetching today's hourly readings..."):
                try:
                    trend_df = get_intraday_trend(zone_obj["lat"], zone_obj["lon"])
                except Exception as e:
                    trend_df = pd.DataFrame()
                    st.warning(f"Couldn't fetch intraday trend: {e}")
            to_plot = [c for c in ["heat_index_celsius", "apparent_temperature_celsius"] if c in trend_df.columns]
            if to_plot:
                st.line_chart(trend_df[to_plot], use_container_width=True)
            else:
                st.info("No intraday data returned yet for today.")

        st.markdown("---")
        st.markdown(f"#### 🔮 48-Hour Forecast -- {selected_zone}")
        st.caption("Real NWS hourly forecast (temperature + humidity), converted to heat index via the official Rothfusz formula. This is a genuine forecast, not an extrapolation of past readings.")
        if zone_obj:
            with st.spinner("Fetching National Weather Service forecast..."):
                try:
                    forecast_df = get_nws_forecast(zone_obj["lat"], zone_obj["lon"])
                except Exception as e:
                    forecast_df = pd.DataFrame()
                    st.warning(f"Couldn't fetch NWS forecast (it's US-only and occasionally rate-limited): {e}")

            if not forecast_df.empty:
                census_data = get_census_data(zone_obj.get("zip", ""))
                summary = summarize_forecast_risk(forecast_df, census_data.get("median_income"), census_data.get("pct_elderly"))

                if summary["peak_risk"] in ("HIGH", "EXTREME"):
                    hrs = summary["hours_until"]
                    when = "now" if hrs is not None and hrs < 1 else f"in about {hrs:.0f}h" if hrs is not None else "soon"
                    st.markdown(
                        f'<div class="alert-banner">🔮 Forecast: {selected_zone} is expected to reach '
                        f'<b>{summary["peak_risk"]}</b> risk {when} '
                        f'({summary["peak_time"].strftime("%a %I:%M %p") if summary["peak_time"] is not None else ""}).</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.info(f"No Danger-level heat forecasted for {selected_zone} in the next 48 hours.")

                st.line_chart(forecast_df[["heat_index_c"]].dropna(), use_container_width=True)
            else:
                st.info("No forecast data available for this location.")

# ── TAB 4: CUSTOM ZONE ANALYZER ──────────────────────────────
with tab_custom_search:
    st.markdown("### 🔍 Live U.S. ZIP Code Analyzer")
    st.markdown("Enter any U.S. ZIP code for an on-demand risk read, or save it to a city's dashboard for ongoing tracking.")

    zip_col, search_btn_col = st.columns([3, 1])
    with zip_col:
        custom_zip = st.text_input("Enter 5-digit U.S. ZIP Code:", value="85004", max_chars=5)
    with search_btn_col:
        st.write(" ")
        st.write(" ")
        run_custom_search = st.button("Evaluate Target ZIP")

    if run_custom_search:
        if len(custom_zip) != 5 or not custom_zip.isdigit():
            st.error("Please enter a valid 5-digit ZIP code.")
        elif not fg_ready:
            st.error("Can't evaluate: FortyGuard client isn't initialized. Check your API key.")
        else:
            with st.spinner(f"Geocoding ZIP {custom_zip}..."):
                geo = geocode_zip(custom_zip)
            if not geo:
                st.error("Failed to geocode the ZIP code. Please verify it represents a valid US region.")
            else:
                lat, lon, display_name = geo
                st.success(f"Located: {display_name} ({lat:.4f}, {lon:.4f})")
                with st.spinner("Fetching FortyGuard climate data and Census demographics..."):
                    try:
                        heat_data = get_heat_data(lat, lon)
                        census_data = get_census_data(custom_zip)
                        risk = classify_risk(heat_data.get("heat_index"), census_data.get("median_income"), census_data.get("pct_elderly"))
                        custom_results = {"name": f"ZIP {custom_zip}", "lat": lat, "lon": lon, "risk": risk, **heat_data, **census_data}
                        st.session_state["last_custom_result"] = custom_results
                        st.session_state["last_custom_display_name"] = display_name

                        col_c_map, col_c_card = st.columns([2, 1])
                        with col_c_map:
                            st.markdown("#### Zone Location")
                            single_df = pd.DataFrame([custom_results])
                            single_df["color"] = single_df["risk"].map(RISK_COLORS_RGB)
                            st.map(single_df, latitude="lat", longitude="lon", color="color", size=300)
                        with col_c_card:
                            st.markdown("#### Local Risk Index")
                            income_str = f"${census_data['median_income']:,}" if census_data['median_income'] else "N/A"
                            elderly_str = f"{census_data['pct_elderly']}%" if census_data['pct_elderly'] is not None else "N/A"
                            risk_color = RISK_COLORS_HEX.get(risk, "#999999")
                            st.markdown(f"""
                            <div class="zone-card" style="border: 2px solid {risk_color};">
                                <div class="card-title">{display_name.split(',')[0]}<span class="risk-badge" style="background-color: {risk_color};">{risk}</span></div>
                                <div class="metric-row"><span class="metric-label">🌡️ Heat Index</span><span class="metric-value">{heat_data['heat_index']:.1f}°C</span></div>
                                <div class="metric-row"><span class="metric-label">💧 Humidity</span><span class="metric-value">{heat_data['humidity']:.1f}%</span></div>
                                <div class="metric-row"><span class="metric-label">💰 Median Income</span><span class="metric-value">{income_str}</span></div>
                                <div class="metric-row" style="border: none;"><span class="metric-label">👵 Elderly %</span><span class="metric-value">{elderly_str}</span></div>
                            </div>
                            """, unsafe_allow_html=True)

                        if gemini_client is not None:
                            st.markdown("#### AI Risk Synopsis")
                            with st.spinner("Analyzing with Gemini..."):
                                summary_prompt = f"""
                                Provide a short, concise 2-sentence public health risk assessment for a neighborhood named {display_name} (ZIP {custom_zip}).
                                It has a heat index of {heat_data['heat_index']:.1f}C, apparent temperature of {heat_data['apparent_temp']:.1f}C, and relative humidity of {heat_data['humidity']:.1f}%.
                                Demographics show median household income is {income_str} and population aged 65+ is {elderly_str}.
                                Explain why the computed risk index is {risk}.
                                """
                                summary_resp = gemini_client.models.generate_content(model="gemini-3.6-flash", contents=summary_prompt)
                                st.info(summary_resp.text)
                    except Exception as err:
                        st.error(f"Error querying live parameters: {err}")

    if st.session_state.get("last_custom_result"):
        st.markdown("---")
        target_city = st.selectbox("Save this ZIP to which city's dashboard?", list(CITIES.keys()), key="save_zip_city")
        if st.button("➕ Add to dashboard"):
            r = st.session_state["last_custom_result"]
            add_custom_zone(target_city, st.session_state["last_custom_display_name"].split(",")[0], r["lat"], r["lon"], custom_zip)
            st.success(f"Saved to {target_city}. It'll show up next time you scan that region.")
            st.cache_data.clear()

# ── TAB 5: RESOURCE GUIDE ────────────────────────────────────
with tab_resources:
    st.markdown("### 📚 Public Health Extreme Heat Resource Guide")
    st.write("Extreme heat is a leading cause of weather-related deaths in the U.S. Protect yourself and your community with these guidance resources.")
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.markdown("""
        #### 🚨 Physiological Signs of Heat Illness
        - **Heat Exhaustion**: Heavy sweating, cold/pale/clammy skin, fast weak pulse, nausea, muscle cramps, dizziness, headache, fainting.
          *Action*: Move to a cool place, loosen clothing, sip cool water. Seek medical help if symptoms worsen or last more than 1 hour.
        - **Heat Stroke (Emergency)**: High body temp (103F/39.4C or higher), hot/red/dry or damp skin, fast strong pulse, headache, dizziness, nausea, confusion, losing consciousness.
          *Action*: **Call 911 immediately.** Move the person to a cool place, lower body temp with cool cloths or bath. Do NOT give them anything to drink.
        """)
    with col_r2:
        st.markdown("""
        #### 🏡 Actionable Preventative Measures
        - **Stay Hydrated**: Drink plenty of fluids before you feel thirsty. Avoid alcohol, caffeine, or heavily sugared drinks.
        - **Find Cooling**: If your home lacks air conditioning, spend hot hours in public air-conditioned areas (libraries, malls, cooling centers).
        - **Check on Vulnerable Neighbors**: Visit or call elderly relatives, neighbors, and those living alone twice daily during heat events.
        - **Never Leave Kids or Pets in Cars**: Even with cracked windows, car interiors reach lethal temperatures in minutes.
        """)

# ── FOOTER ───────────────────────────────────────────────────
st.markdown(
    '<div class="footer-note">Built for FortyGuard Hackathon 2026 — Track 6 (Agentic)<br>'
    'Powered by FortyGuard Temperature API, Google Gemini, and US Census Bureau data. All live data.</div>',
    unsafe_allow_html=True,
)