"""
build_ssot.py - Builds the Single Source of Truth (SSOT) for the Citi Bike 2025 project.

Sources
  1. Citi Bike trip data (manual download, trips/ folder, Apr + Jun + Oct + Dec 2025)
  2. Open-Meteo historical hourly weather, Central Park grid point
     (validated against NOAA NCEI daily summaries, Central Park USW00094728)
  3. Citi Bike GBFS station_information (live snapshot, NOT 2025)
  4. US + New York State holidays (python 'holidays' library)

Install:  pip install pandas numpy requests holidays pyarrow
Run:      python build_ssot.py
Output:   ssot.parquet (or ssot.csv.gz if pyarrow is missing) + sources_summary.txt
"""

import glob
import io
import json
import os
import sys
from datetime import date

import numpy as np
import pandas as pd
import requests

# ----------------------------- CONFIG ---------------------------------------
TRIPS_DIR = "trips"
MONTHS = [("2025-04-01", "2025-04-30"), ("2025-06-01", "2025-06-30"),
          ("2025-10-01", "2025-10-31"), ("2025-12-01", "2025-12-31")]
SEASONS = {4: "spring", 6: "summer", 10: "autumn", 12: "winter"}
SAMPLE_FRAC = 0.25      # share of trips kept (8 GB RAM). Set 1.0 to keep all trips.
RANDOM_STATE = 42
CHUNK = 500_000
MIN_DURATION_MIN = 1    # shorter rides treated as false starts / docking errors
MAX_DURATION_MIN = 180  # longer rides treated as lost/unreturned bikes
TZ = "America/New_York"

WEATHER_RAW = "weather_openmeteo.csv"
STATIONS_RAW = "station_information.json"
# Open-Meteo historical archive (reanalysis), grid point nearest Central Park
OPENMETEO_URL = "https://archive-api.open-meteo.com/v1/archive"
OPENMETEO_PARAMS = {
    "latitude": 40.7789, "longitude": -73.9692, "timezone": "GMT",
    "wind_speed_unit": "ms",
    "hourly": "temperature_2m,relative_humidity_2m,dew_point_2m,precipitation,"
              "pressure_msl,cloud_cover,wind_speed_10m,wind_direction_10m",
}
OPENMETEO_VARS = {  # Open-Meteo name -> SSOT column
    "temperature_2m": "temp_c", "relative_humidity_2m": "humidity_pct",
    "dew_point_2m": "dew_point_c", "precipitation": "precip_mm",
    "pressure_msl": "sea_level_pressure_hpa", "cloud_cover": "cloud_cover_pct",
    "wind_speed_10m": "wind_speed_ms", "wind_direction_10m": "wind_dir_deg",
}
RAIN_THRESHOLD_MM = 0.1
# NOAA daily summaries, Central Park (GHCN USW00094728) - used only to validate Open-Meteo
NOAA_DAILY_URL = (
    "https://www.ncei.noaa.gov/access/services/data/v1"
    "?dataset=daily-summaries&stations=USW00094728&dataTypes=TMAX,TMIN,PRCP"
    "&startDate={s}&endDate={e}&format=csv&units=metric"
)
GBFS_URL = "https://gbfs.citibikenyc.com/gbfs/en/station_information.json"

TRIP_COLS = [
    "ride_id", "rideable_type", "started_at", "ended_at",
    "start_station_name", "start_station_id", "end_station_name", "end_station_id",
    "start_lat", "start_lng", "end_lat", "end_lng", "member_casual",
]
TRIP_DTYPES = {
    "ride_id": "string",
    "rideable_type": "category",
    "start_station_name": "category",
    "start_station_id": "category",
    "end_station_name": "category",
    "end_station_id": "category",
    "member_casual": "category",
    "start_lat": "float32", "start_lng": "float32",
    "end_lat": "float32", "end_lng": "float32",
}

summary = []  # lines for sources_summary.txt


def log(msg):
    print(msg)
    summary.append(msg)


# ----------------------------- 1. TRIPS -------------------------------------
def load_trips():
    files = sorted(glob.glob(os.path.join(TRIPS_DIR, "**", "*.csv"), recursive=True))
    if not files:
        sys.exit(f"No CSV files found in {TRIPS_DIR}/")
    parts, raw_total = [], 0
    for f in files:
        header = pd.read_csv(f, nrows=0).columns
        missing = [c for c in TRIP_COLS if c not in header]
        if missing:
            sys.exit(f"{f} is missing columns {missing}. Found: {list(header)}")
        n_file = 0
        for chunk in pd.read_csv(f, usecols=TRIP_COLS, dtype=TRIP_DTYPES, chunksize=CHUNK):
            n_file += len(chunk)
            if SAMPLE_FRAC < 1:
                chunk = chunk.sample(frac=SAMPLE_FRAC, random_state=RANDOM_STATE)
            # parse timestamps per chunk: datetimes take far less memory than strings
            for c in ("started_at", "ended_at"):
                chunk[c] = pd.to_datetime(chunk[c], errors="coerce")
            parts.append(chunk)
        raw_total += n_file
        log(f"  {os.path.basename(f)}: {n_file:,} raw rows")
    trips = pd.concat(parts, ignore_index=True)
    del parts
    # concat turns categories that differ between chunks into plain strings -> restore
    for c, t in TRIP_DTYPES.items():
        if t == "category":
            trips[c] = trips[c].astype("category")
    trips.attrs["raw_total"] = raw_total
    return trips


def clean_trips(trips):
    n0 = len(trips)
    trips = trips.drop_duplicates(subset="ride_id")
    n_dup = n0 - len(trips)

    trips["started_at"] = pd.to_datetime(trips["started_at"], errors="coerce")
    trips["ended_at"] = pd.to_datetime(trips["ended_at"], errors="coerce")
    n1 = len(trips)
    trips = trips.dropna(subset=["started_at", "ended_at"])
    n_bad_time = n1 - len(trips)

    trips["duration_min"] = (trips["ended_at"] - trips["started_at"]).dt.total_seconds() / 60
    n2 = len(trips)
    trips = trips[trips["duration_min"].between(MIN_DURATION_MIN, MAX_DURATION_MIN)]
    n_dur = n2 - len(trips)

    # keep only trips that start inside the chosen months
    in_range = np.zeros(len(trips), dtype=bool)
    for s, e in MONTHS:
        in_range |= trips["started_at"].between(s, pd.Timestamp(e) + pd.Timedelta(days=1)).to_numpy()
    n3 = len(trips)
    trips = trips[in_range]
    n_range = n3 - len(trips)

    log(f"  Removed: {n_dup:,} duplicate ride_id, {n_bad_time:,} unparseable times, "
        f"{n_dur:,} durations outside {MIN_DURATION_MIN}-{MAX_DURATION_MIN} min, "
        f"{n_range:,} outside study months")
    return trips.reset_index(drop=True)


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def add_trip_features(trips):
    t = trips["started_at"]
    trips["start_hour_ts"] = t.dt.floor("h")
    trips["date"] = t.dt.normalize()
    trips["month"] = t.dt.month.astype("int8")
    trips["day_of_week"] = t.dt.dayofweek.astype("int8")  # Mon=0
    trips["hour"] = t.dt.hour.astype("int8")
    trips["is_weekend"] = (trips["day_of_week"] >= 5).astype("int8")
    trips["is_rush_hour"] = (
        (trips["is_weekend"] == 0) & trips["hour"].isin([7, 8, 9, 16, 17, 18, 19])
    ).astype("int8")
    trips["season"] = trips["month"].map(SEASONS).astype("category")
    trips["distance_km"] = haversine_km(
        trips["start_lat"].astype("float64"), trips["start_lng"].astype("float64"),
        trips["end_lat"].astype("float64"), trips["end_lng"].astype("float64"),
    ).astype("float32")
    trips["avg_speed_kmh"] = (trips["distance_km"] / (trips["duration_min"] / 60)).astype("float32")
    trips["same_station"] = (
        trips["start_station_id"].astype("string") == trips["end_station_id"].astype("string")
    ).fillna(False).astype("int8")  # missing end station -> not a round trip
    return trips


# ----------------------------- 2. WEATHER -----------------------------------
def fetch_weather():
    if os.path.exists(WEATHER_RAW):
        cached = pd.read_csv(WEATHER_RAW)
        months = set(pd.to_datetime(cached["time"]).dt.strftime("%Y-%m"))
        if all(s[:7] in months for s, _ in MONTHS):
            log(f"  Using existing {WEATHER_RAW}")
            return cached
        log(f"  {WEATHER_RAW} does not cover the study months -> re-downloading")
    frames = []
    for s, e in MONTHS:
        log(f"  Fetching Open-Meteo {s} to {e}")
        # pad one day each side: UTC days do not line up with New York days
        pad = pd.Timedelta(days=1)
        params = dict(OPENMETEO_PARAMS,
                      start_date=(pd.Timestamp(s) - pad).date().isoformat(),
                      end_date=(pd.Timestamp(e) + pad).date().isoformat())
        r = requests.get(OPENMETEO_URL, params=params, timeout=120)
        r.raise_for_status()
        frames.append(pd.DataFrame(r.json()["hourly"]))
    raw = pd.concat(frames, ignore_index=True)
    raw.to_csv(WEATHER_RAW, index=False)
    return raw


def build_weather(raw):
    w = pd.DataFrame()
    # Open-Meteo is requested in UTC (GMT); trips are New York local time -> convert
    ts = pd.to_datetime(raw["time"]).dt.tz_localize("UTC")
    w["hour_ts"] = ts.dt.tz_convert(TZ).dt.tz_localize(None)
    for src, dst in OPENMETEO_VARS.items():
        w[dst] = raw[src]
    hourly = w.groupby("hour_ts").mean()

    # complete hourly grid over the study months
    idx = pd.DatetimeIndex([])
    for s, e in MONTHS:
        idx = idx.append(pd.date_range(s, pd.Timestamp(e) + pd.Timedelta(hours=23), freq="h"))
    hourly = hourly.reindex(idx)
    hourly.index.name = "hour_ts"

    n_missing_hours = int(hourly["temp_c"].isna().sum())
    cont = [c for c in hourly.columns if c != "precip_mm"]
    hourly[cont] = hourly[cont].interpolate(limit=3, limit_area="inside")  # short gaps only
    hourly["precip_mm"] = hourly["precip_mm"].fillna(0)
    # reanalysis spreads tiny drizzle amounts widely; below 0.1 mm/h counts as dry
    hourly["is_raining"] = (hourly["precip_mm"] >= RAIN_THRESHOLD_MM).astype("int8")
    hourly["temp_band"] = pd.cut(
        hourly["temp_c"], [-100, 0, 10, 20, 30, 100],
        labels=["freezing", "cold", "mild", "warm", "hot"]).astype("string")
    log(f"  Weather: {len(raw):,} Open-Meteo hours -> {len(hourly):,} hourly rows; "
        f"{n_missing_hours} hours had no temperature before gap filling (<=3 h interpolated)")
    return hourly.reset_index()


def check_weather_against_noaa(hourly):
    """Compare daily max/min temperature and rain totals with NOAA Central Park daily records."""
    frames = []
    for s, e in MONTHS:
        r = requests.get(NOAA_DAILY_URL.format(s=s, e=e), timeout=120)
        r.raise_for_status()
        frames.append(pd.read_csv(io.StringIO(r.text)))
    noaa = pd.concat(frames, ignore_index=True)
    noaa["date"] = pd.to_datetime(noaa["DATE"])
    noaa = noaa.set_index("date")[["TMAX", "TMIN", "PRCP"]]

    om = hourly.set_index("hour_ts")
    om = om.groupby(om.index.normalize()).agg(
        TMAX=("temp_c", "max"), TMIN=("temp_c", "min"), PRCP=("precip_mm", "sum"))
    both = om.join(noaa, lsuffix="_om", rsuffix="_noaa", how="inner").dropna()
    log(f"  Cross-check with NOAA daily (Central Park, {len(both)} days):")
    for v in ["TMAX", "TMIN", "PRCP"]:
        a, b = both[f"{v}_om"], both[f"{v}_noaa"]
        log(f"    {v}: correlation {a.corr(b):.2f}, mean abs difference {(a - b).abs().mean():.1f}, "
            f"mean bias (Open-Meteo - NOAA) {(a - b).mean():+.1f}")
    wet_om, wet_noaa = both["PRCP_om"] >= 1, both["PRCP_noaa"] >= 1
    log(f"    Wet days (>=1 mm) agree on {(wet_om == wet_noaa).mean():.0%} of days")



# ----------------------------- 3. STATIONS ----------------------------------
def load_stations():
    if os.path.exists(STATIONS_RAW):
        with open(STATIONS_RAW, encoding="utf-8") as fh:
            data = json.load(fh)
    else:
        log(f"  Fetching {GBFS_URL}")
        r = requests.get(GBFS_URL, timeout=60)
        r.raise_for_status()
        data = r.json()
        with open(STATIONS_RAW, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    st = pd.DataFrame(data["data"]["stations"])
    st = st[["short_name", "station_id", "capacity", "lat", "lon"]].dropna(subset=["short_name"])
    st["short_name"] = st["short_name"].astype(str)
    st = st.drop_duplicates("short_name")
    log(f"  Stations: {len(st):,} rows (live snapshot, not 2025)")
    return st


# ----------------------------- 4. HOLIDAYS ----------------------------------
def load_holidays():
    import holidays
    h = holidays.country_holidays("US", subdiv="NY", years=2025)
    df = pd.DataFrame({"date": pd.to_datetime(list(h.keys())), "holiday_name": list(h.values())})
    df = df.drop_duplicates("date")
    log(f"  Holidays: {len(df)} US/NY holidays in 2025")
    return df


# ----------------------------- MAIN -----------------------------------------
def main():
    log("== 1. Trips ==")
    trips = load_trips()
    raw_total = trips.attrs["raw_total"]
    log(f"  Raw rows across files: {raw_total:,}; kept after {SAMPLE_FRAC:.0%} sampling: {len(trips):,}")
    trips = clean_trips(trips)
    trips = add_trip_features(trips)
    log(f"  Clean trips: {len(trips):,}")

    log("== 2. Weather ==")
    weather = build_weather(fetch_weather())
    check_weather_against_noaa(weather)

    log("== 3. Stations ==")
    stations = load_stations()

    log("== 4. Holidays ==")
    hol = load_holidays()

    log("== Integration ==")
    n0 = len(trips)
    trips = trips.merge(weather, left_on="start_hour_ts", right_on="hour_ts", how="left")
    trips = trips.drop(columns=["hour_ts"])

    cap = stations.set_index("short_name")["capacity"]
    trips["start_station_capacity"] = trips["start_station_id"].astype("string").map(cap)
    trips["end_station_capacity"] = trips["end_station_id"].astype("string").map(cap)
    trips["start_station_in_gbfs"] = trips["start_station_capacity"].notna().astype("int8")

    trips = trips.merge(hol, on="date", how="left")
    trips["is_holiday"] = trips["holiday_name"].notna().astype("int8")
    trips["is_non_working_day"] = ((trips["is_weekend"] == 1) | (trips["is_holiday"] == 1)).astype("int8")
    trips["holiday_name"] = trips["holiday_name"].fillna("none")
    assert len(trips) == n0, "Row count changed during merge (duplicate join keys)!"

    log("== Quality checks ==")
    log(f"  Final rows: {len(trips):,}   columns: {trips.shape[1]}")
    log(f"  Trips with no matched weather: {trips['temp_c'].isna().mean():.2%}")
    log(f"  Trips whose start station is in GBFS snapshot: {trips['start_station_in_gbfs'].mean():.2%}")
    log(f"  Rows per month: {trips.groupby('month').size().to_dict()}")
    miss = trips.isna().mean().sort_values(ascending=False)
    log("  Top missing-value shares:")
    for c, v in miss.head(8).items():
        log(f"    {c}: {v:.2%}")

    try:
        trips.to_parquet("ssot.parquet", index=False)
        log("Saved ssot.parquet")
    except Exception as exc:  # pyarrow missing
        trips.to_csv("ssot.csv.gz", index=False, compression="gzip")
        log(f"Saved ssot.csv.gz ({exc.__class__.__name__}: parquet unavailable)")

    log(f"\nDownload/build date: {date.today().isoformat()}")
    with open("sources_summary.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(summary))
    print("\nWrote sources_summary.txt - send me this file's contents.")


if __name__ == "__main__":
    main()
