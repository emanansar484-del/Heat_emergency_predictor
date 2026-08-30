# Heat-Emergency Predictor

Multi-city, point-based heat-emergency risk dashboard combining live **FortyGuard Temperature API** data with **US Census Bureau** demographics, so that limited public-health outreach resources go where they matter most.

Built for **FortyGuard Hackathon'26**.

---

##  How to run it from scratch

### 1. Clone the repo
```bash
git clone https://github.com/emanansar484-del/Heat_emergency_predictor.git
cd Heat_emergency_predictor
```

### 2. Install dependencies
Requires Python 3.10+ (uses modern type hints like `float | None`).
```bash
pip install -r requirements.txt
```

### 3. Set up environment variables
Create a `.env` file in the project root (this file is git-ignored and must **never** be committed):
```
GOOGLE_API_KEY=your_google_gemini_api_key
CENSUS_API_KEY=your_census_bureau_api_key
FORTYGUARD_API_KEY=your_fortyguard_api_key
```
- Get a FortyGuard API key from your Hackathon'26 dashboard access.
- Get a free Census Bureau key at https://api.census.gov/data/key_signup.html
- Get a Gemini API key at https://aistudio.google.com/apikey

> The app still runs without these keys — missing-key warnings appear in the sidebar, and the relevant features (AI narrative reports, demographic scoring) are disabled gracefully rather than crashing.

### 4. Run the app
```bash
streamlit run app.py
```
The app opens at `http://localhost:8501`. On first run, it auto-creates a local `heat_history.db` SQLite file for scan history — no manual setup needed.

---

## ⚠️ What doesn't work yet / known limitations

- **NWS forecast is US-only** — the 48-hour forecast tab (`api.weather.gov`) only returns data for US coordinates. Custom ZIP/address zones outside the US will fail gracefully with a warning.
- **Census data depends on ZIP-level ACS coverage** — very small or newly-created ZCTAs sometimes return no income/elderly data; the app falls back to "N/A" and still computes risk from heat index alone.
- **Gemini AI report/chat can fail under provider load** — retried automatically with backoff, but if it keeps failing, the report panel shows a fallback message and the raw scan data is still shown/downloadable.
- **No authentication/multi-user support** — this is a single-instance demo app; scan history is shared across whoever uses that deployed instance, not per-user.
- **Not yet tested on very narrow/mobile screens** — the two-column dashboard layout is optimized for desktop widths.

---

## 🌡️ Real FortyGuard API example

Captured directly from a live local run (`streamlit run app.py`), scanning the Los Angeles zones on 2026-08-30.

**Request** (via `FortyGuardClient.environmental_parameters`, as called in `get_heat_data()` for the Beverly Hills zone):
```python
response = fg_client.environmental_parameters(
    latitude=34.0736,
    longitude=-118.4004,
    temperature=35.0,
    start_date="2026-08-30",
    start_time="15:00",
    end_date="2026-08-30",
    end_time="15:00",
    filter_type=1,
)
```

**Response:**
```json
{
  "activity_id": "7b369e8a-46f4-4e07-892b-81c3223e9b37",
  "result": {
    "metadata": {
      "timezone": "GMT-8",
      "timezone_offset_hours": -8,
      "time_range": {
        "start": "2026-08-30T15:00:00-08:00",
        "end": "2026-08-30T15:00:00-08:00",
        "interval": "1h",
        "count": 1
      },
      "timestamps": ["2026-08-30T15:00:00-08:00"]
    },
    "locations": [
      {
        "lat": 34.0736,
        "lon": -118.4004,
        "elevation": 83.0,
        "temperature": 35.0,
        "parameters": {
          "heat_index_celsius": [37.5],
          "apparent_temperature_celsius": [33.0],
          "relative_humidity_percent": [41.1],
          "precipitation_mm": [0.0],
          "cloud_cover_octas": [0.0],
          "wet_bulb_temperature_celsius": [21.8],
          "air_quality:idx": [99.9],
          "air_quality_pm2p5:idx": [99.9],
          "air_quality_pm10:idx": [35.6],
          "air_quality_no2:idx": [2.4],
          "aqi_us_co": [1.9],
          "air_quality_o3:idx": [44.3],
          "air_quality_so2:idx": [2.4],
          "methane_ppb": [2030.9],
          "co2_ppm": [443.0]
        },
        "solar_irradiance": {
          "clear_sky": {
            "ghi": 576.71,
            "dni": 683.92,
            "dhi": 132.82
          },
          "description": "The above values provide insights into the solar energy available at the specific location at 2026-08-30 15:00. GHI represents the total solar energy, DNI focuses on direct sunlight, and DHI accounts for scattered and diffuse radiation."
        }
      }
    ]
  }
}
```

The app extracts `heat_index_celsius` (37.5°C here), `apparent_temperature_celsius`, and `relative_humidity_percent` from this response and feeds them into `classify_risk()` alongside Census demographics to produce the zone's risk tier.

---

## Security note
No API keys are committed to this repository. All keys are loaded from environment variables via `.env` (git-ignored) locally, or from **Streamlit Secrets** in the deployed version.

## Tech stack
Streamlit · FortyGuard Temperature API · US Census Bureau ACS API · Google Gemini · SQLite · pandas
