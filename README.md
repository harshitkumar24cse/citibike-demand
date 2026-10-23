# Decoding Citi Bike Demand: The Impact of Weather, Seasonality and Holidays in NYC

Advanced Data Science, end-term project. Team: Harshit Kumar, Ishaan Jatain, Himanshu Yadav.

**Question:** how much do weather, season and holidays change hourly Citi Bike demand in New York City, and do members and casual riders respond differently? The stakeholder is the Citi Bike operations and rebalancing team.

## Data

| Source | Coverage | Used for |
|---|---|---|
| [Citi Bike trip data](https://citibikenyc.com/system-data) | April, June, October, December 2025 (one month per season), 15.3 M trips, 25% random sample | Trips, times, stations, rider type |
| [Open-Meteo historical weather](https://open-meteo.com/en/docs/historical-weather-api), Central Park | Same months, hourly (2,928 hours) | Temperature, rain, wind, humidity |
| [NOAA NCEI daily summaries](https://www.ncei.noaa.gov/), Central Park USW00094728 | Same months, daily | Checking the Open-Meteo weather |
| [Citi Bike GBFS station feed](https://gbfs.citibikenyc.com/gbfs/en/station_information.json) | ~2,500 stations (current snapshot) | Station capacity |
| US / New York holidays (`holidays` Python library) | 2025 | Holiday flag |

**Final dataset (`ssot.parquet`):** 3,822,094 trips × 41 variables, one row per trip. Cleaning counts and the weather check are in [`sources_summary.txt`](sources_summary.txt).

## Files

| File | What it does |
|---|---|
| `build_ssot.py` | Cleans the trips, joins weather, stations and holidays, and writes `ssot.parquet` and `sources_summary.txt` |
| `ADS_Pre_Submission_Group_14.pdf` | One-page pre-submission summary (final) |
| `make_summary_pdf.py` | Builds an earlier draft of the summary PDF |
| `sources_summary.txt` | Build log: row counts, removals, weather check, missing values |
| `ssot_sample_1000.csv` | 1,000 random rows of the final dataset (all 41 columns), to preview it without rebuilding |
| `weather_openmeteo.csv`, `station_information.json` | Saved copies of the downloaded weather and station data, so rebuilds give the same result |

## How to run

1. Install Python 3.10+ and the packages:
   ```bash
   pip install -r requirements.txt
   ```
2. Download the trip data. The files are too large for GitHub (about 3 GB). From <https://s3.amazonaws.com/tripdata/index.html> download these four files, unzip them and put the CSV files in a folder named `trips/`:
   - `202504-citibike-tripdata.zip`
   - `202506-citibike-tripdata.zip`
   - `202510-citibike-tripdata.zip`
   - `202512-citibike-tripdata.zip`
3. Build the dataset (about 5–10 minutes, works on 8 GB RAM):
   ```bash
   python build_ssot.py
   ```
4. Optional, rebuild the earlier draft of the summary PDF:
   ```bash
   python make_summary_pdf.py
   ```

## Main cleaning steps

- Duplicate ride IDs removed; trips shorter than 1 minute or longer than 180 minutes removed.
- Weather timestamps converted from UTC to New York time before joining on the trip's start hour.
- Weather gaps up to 3 hours interpolated; an hour counts as rainy from 0.1 mm.
- Row count checked to be unchanged after the joins.
