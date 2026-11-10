"""
stage2_eda.py - Stage 2, part 1: hourly aggregation, data-quality summary and EDA charts.

Input:   ssot.parquet (from build_ssot.py), datasets/2_weather_hourly_newyork.csv,
         datasets/5_holidays_2025.csv
Run:     python stage2_eda.py
Output:  outputs/hourly_demand.csv      one row per hour (2,928 hours)
         outputs/data_quality.txt       data-quality summary
         outputs/dfsummary_ssot.html    dfSummary of the final trip dataset (open in a browser)
         outputs/dfsummary_hourly.html  dfSummary of the hourly table
         outputs/holidays_described.csv the 3 holidays vs a normal day
         outputs/figures/*.png          EDA charts
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from summarytools import dfSummary

OUT = "outputs"
FIG = os.path.join(OUT, "figures")
os.makedirs(FIG, exist_ok=True)

SEASONS = {4: "spring", 6: "summer", 10: "autumn", 12: "winter"}
SEASON_ORDER = ["spring", "summer", "autumn", "winter"]

# chart style: two-series charts use categorical slots 1 and 2 of the reference palette
C1, C2 = "#2a78d6", "#eb6834"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.titlesize": 12,
    "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.titlelocation": "left",
    "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "axes.axisbelow": True, "axes.spines.top": False,
    "axes.spines.right": False, "legend.frameon": False, "figure.dpi": 150,
})

report = []  # lines for data_quality.txt


def log(msg=""):
    print(msg)
    report.append(msg)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, name), bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ----------------------------- 1. LOAD -----------------------------------------
trips = pd.read_parquet("ssot.parquet")
weather = pd.read_csv("datasets/2_weather_hourly_newyork.csv", parse_dates=["hour_ts"])
holidays = pd.read_csv("datasets/5_holidays_2025.csv", parse_dates=["date"])

# ----------------------------- 2. DATA QUALITY ---------------------------------
log("== Data-quality summary (trip level) ==")
log(f"Rows: {len(trips):,}   columns: {trips.shape[1]}")
log(f"Duplicate ride_id: {trips['ride_id'].duplicated().sum():,}")
log(f"Trips per month: {trips.groupby('month').size().to_dict()}")
log(f"Member / casual: {trips['member_casual'].value_counts().to_dict()}")
log(f"Bike type: {trips['rideable_type'].value_counts().to_dict()}")
d = trips["duration_min"]
log(f"Duration (min): median {d.median():.1f}, mean {d.mean():.1f}, "
    f"p95 {d.quantile(.95):.1f}, max {d.max():.1f}")
log(f"Distance (km): median {trips['distance_km'].median():.2f}, "
    f"missing {trips['distance_km'].isna().mean():.2%}")
log(f"Round trips (same start and end station): {trips['same_station'].mean():.2%}")
miss = trips.isna().mean().sort_values(ascending=False)
log("Columns with missing values:")
for c, v in miss[miss > 0].items():
    log(f"  {c}: {v:.2%}")

# dfSummary: one table with type, missing values, distinct values and a mini chart per column
with open(os.path.join(OUT, "dfsummary_ssot.html"), "w", encoding="utf-8") as fh:
    fh.write(dfSummary(trips).to_html())
log("Saved dfSummary of the trip dataset: outputs/dfsummary_ssot.html")

# ----------------------------- 3. HOURLY AGGREGATION ---------------------------
counts = (trips.groupby(["start_hour_ts", "member_casual"], observed=True).size()
          .unstack(fill_value=0).rename(columns={"member": "member_trips", "casual": "casual_trips"}))
hourly = weather.set_index("hour_ts").join(counts, how="left")
hourly[["member_trips", "casual_trips"]] = hourly[["member_trips", "casual_trips"]].fillna(0).astype(int)
hourly["total_trips"] = hourly["member_trips"] + hourly["casual_trips"]
hourly["casual_share"] = hourly["casual_trips"] / hourly["total_trips"].replace(0, np.nan)

ts = hourly.index
hourly["date"] = ts.normalize()
hourly["month"] = ts.month
hourly["season"] = hourly["month"].map(SEASONS)
hourly["hour"] = ts.hour
hourly["day_of_week"] = ts.dayofweek  # Mon=0
hourly["is_weekend"] = (hourly["day_of_week"] >= 5).astype(int)
hourly["is_holiday"] = hourly["date"].isin(holidays["date"]).astype(int)
hourly["is_non_working_day"] = ((hourly["is_weekend"] == 1) | (hourly["is_holiday"] == 1)).astype(int)
hourly["is_rush_hour"] = ((hourly["is_non_working_day"] == 0) &
                          hourly["hour"].isin([7, 8, 9, 16, 17, 18, 19])).astype(int)
hourly = hourly.reset_index().rename(columns={"index": "hour_ts"})
hourly.to_csv(os.path.join(OUT, "hourly_demand.csv"), index=False)
with open(os.path.join(OUT, "dfsummary_hourly.html"), "w", encoding="utf-8") as fh:
    fh.write(dfSummary(hourly).to_html())

log("\n== Hourly demand table ==")
log(f"Hours: {len(hourly):,}  (trips summed: {hourly['total_trips'].sum():,})")
log(f"Hours with zero trips: {(hourly['total_trips'] == 0).sum()}")
t = hourly["total_trips"]
log(f"Trips per hour: mean {t.mean():.0f}, median {t.median():.0f}, min {t.min()}, max {t.max()}")
log(f"Rainy hours (>= 0.1 mm): {hourly['is_raining'].sum()} of {len(hourly)} "
    f"({hourly['is_raining'].mean():.1%})")
log("Mean trips per hour by season: " +
    str(hourly.groupby("season")["total_trips"].mean().reindex(SEASON_ORDER).round(0).to_dict()))
log("Mean temperature by season (C): " +
    str(hourly.groupby("season")["temp_c"].mean().reindex(SEASON_ORDER).round(1).to_dict()))

# ----------------------------- 4. EDA CHARTS -----------------------------------
# 4.1 Daily profile: weekday vs weekend (H5)
prof = hourly.groupby(["is_non_working_day", "hour"])["total_trips"].mean().unstack(0)
fig, ax = plt.subplots(figsize=(8, 4.2))
ax.plot(prof.index, prof[0], color=C1, lw=2, marker="o", ms=4, label="Working day")
ax.plot(prof.index, prof[1], color=C2, lw=2, marker="o", ms=4, label="Weekend / holiday")
ax.set(title="Average trips per hour across the day", xlabel="Hour of day",
       ylabel="Trips per hour (25% sample)", xticks=range(0, 24, 2))
ax.set_ylim(bottom=0)
ax.legend(loc="upper left")
save(fig, "01_daily_profile_weekday_weekend.png")

# 4.2 Trips vs temperature, members and casual riders (H1, H3) - small multiples, own scales
hourly["temp_bin"] = (hourly["temp_c"] // 2) * 2 + 1  # 2 C bins, labelled by mid-point
tb = hourly.groupby("temp_bin").agg(member=("member_trips", "mean"), casual=("casual_trips", "mean"),
                                   n=("total_trips", "size"))
tb = tb[tb["n"] >= 10]
fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharex=True)
for ax, col, color, name in [(axes[0], "member", C1, "Members"), (axes[1], "casual", C2, "Casual riders")]:
    ax.scatter(hourly["temp_c"], hourly[f"{col}_trips"], s=4, color=color, alpha=0.15, lw=0)
    ax.plot(tb.index, tb[col], color=color, lw=2, marker="o", ms=4)
    ax.set(title=name, xlabel="Temperature (C)", ylabel="Trips per hour")
    ax.set_ylim(bottom=0)
fig.suptitle("Trips per hour vs temperature (dots = hours, line = average per 2 C)",
             x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
save(fig, "02_trips_vs_temperature_member_casual.png")

# 4.3 Rain vs dry by season (H2)
rd = hourly.groupby(["season", "is_raining"])["total_trips"].mean().unstack().reindex(SEASON_ORDER)
x = np.arange(len(rd))
fig, ax = plt.subplots(figsize=(8, 4.2))
ax.bar(x - 0.2, rd[0], width=0.38, color=C1, label="Dry hour")
ax.bar(x + 0.2, rd[1], width=0.38, color=C2, label="Rainy hour (>= 0.1 mm)")
for i, (dry, wet) in enumerate(zip(rd[0], rd[1])):
    ax.text(i + 0.2, wet, f"{(wet / dry - 1):+.0%}", ha="center", va="bottom", fontsize=9, color=INK2)
ax.set(title="Average trips per hour: dry vs rainy hours, by season", ylabel="Trips per hour",
       xticks=x, xticklabels=[s.title() for s in rd.index])
ax.grid(axis="x", visible=False)
ax.legend(loc="upper right")
save(fig, "03_rain_vs_dry_by_season.png")

# 4.4 Distribution of hourly demand by season (seasons, Kruskal-Wallis later)
fig, ax = plt.subplots(figsize=(8, 4.2))
data = [hourly.loc[hourly["season"] == s, "total_trips"] for s in SEASON_ORDER]
bp = ax.boxplot(data, patch_artist=True, widths=0.5, showfliers=False,
                medianprops=dict(color=INK, lw=1.5))
for b in bp["boxes"]:
    b.set(facecolor="#9ec5f4", edgecolor=C1)
ax.set(title="Trips per hour by season", ylabel="Trips per hour",
       xticks=range(1, 5), xticklabels=[f"{s.title()}\n({m})" for s, m in
                                         zip(SEASON_ORDER, ["Apr", "Jun", "Oct", "Dec"])])
ax.grid(axis="x", visible=False)
save(fig, "04_hourly_demand_by_season.png")

# 4.5 Trip duration, members vs casual riders (H4) - trip level
fig, ax = plt.subplots(figsize=(8, 4.2))
bins = np.arange(0, 61, 1)
for rider, color, name in [("member", C1, "Members"), ("casual", C2, "Casual riders")]:
    dd = trips.loc[trips["member_casual"] == rider, "duration_min"]
    over = (dd > 60).mean()
    ax.hist(dd[dd <= 60], bins=bins, density=True, histtype="step", lw=2, color=color,
            label=f"{name}: median {dd.median():.1f} min ({over:.1%} over 60 min not shown)")
ax.set(title="Trip duration: members vs casual riders", xlabel="Trip duration (minutes)",
       ylabel="Share of trips")
ax.legend(loc="upper right")
save(fig, "05_trip_duration_member_casual.png")

# 4.6 Casual share across the day, working vs non-working days (H5)
cs = (hourly.groupby(["is_non_working_day", "hour"])[["casual_trips", "total_trips"]].sum())
cs = (cs["casual_trips"] / cs["total_trips"]).unstack(0)
fig, ax = plt.subplots(figsize=(8, 4.2))
ax.plot(cs.index, cs[0] * 100, color=C1, lw=2, marker="o", ms=4, label="Working day")
ax.plot(cs.index, cs[1] * 100, color=C2, lw=2, marker="o", ms=4, label="Weekend / holiday")
ax.set(title="Share of trips by casual riders across the day", xlabel="Hour of day",
       ylabel="Casual share (%)", xticks=range(0, 24, 2))
ax.set_ylim(bottom=0)
ax.legend(loc="lower right")
save(fig, "06_casual_share_by_hour.png")

# 4.7 Correlation of hourly trips with weather variables
wvars = {"temp_c": "Temperature", "humidity_pct": "Humidity", "precip_mm": "Precipitation",
         "wind_speed_ms": "Wind speed", "cloud_cover_pct": "Cloud cover",
         "sea_level_pressure_hpa": "Pressure"}
corr = hourly[list(wvars) + ["total_trips"]].corr(method="spearman")["total_trips"].drop("total_trips")
corr = corr.rename(wvars).sort_values()
fig, ax = plt.subplots(figsize=(8, 3.8))
ax.barh(corr.index, corr.values, color=[C2 if v < 0 else C1 for v in corr.values], height=0.6)
for i, v in enumerate(corr.values):
    ax.text(v + (0.02 if v >= 0 else -0.02), i, f"{v:+.2f}", va="center",
            ha="left" if v >= 0 else "right", fontsize=9, color=INK2)
ax.axvline(0, color=INK2, lw=1)
ax.set(title="Correlation of trips per hour with weather (Spearman)", xlim=(-1, 1),
       xlabel="Correlation (-1 to +1)")
ax.grid(axis="y", visible=False)
save(fig, "07_weather_correlations.png")

# 4.8 Holidays: only 3 in our months, so we describe them instead of testing them.
# Each holiday is compared with the normal days of the same weekday in the same month.
daily = hourly.groupby("date").agg(trips=("total_trips", "sum"), casual=("casual_trips", "sum"),
                                   temp=("temp_c", "mean"), rain_hours=("is_raining", "sum"),
                                   holiday=("is_holiday", "max"))
daily["weekday"] = daily.index.dayofweek
daily["month"] = daily.index.month
rows = []
for day, h in daily[daily["holiday"] == 1].iterrows():
    normal = daily[(daily["holiday"] == 0) & (daily["weekday"] == h["weekday"]) & (daily["month"] == h["month"])]
    name = holidays.loc[holidays["date"] == day, "holiday_name"].iloc[0]
    rows.append({"date": day.date(), "holiday": name, "weekday": day.day_name(),
                 "holiday_trips": int(h["trips"]), "normal_day_trips": round(normal["trips"].mean()),
                 "change_pct": round((h["trips"] / normal["trips"].mean() - 1) * 100, 1),
                 "holiday_casual_share_pct": round(h["casual"] / h["trips"] * 100, 1),
                 "normal_casual_share_pct": round(normal["casual"].sum() / normal["trips"].sum() * 100, 1),
                 "holiday_temp_c": round(h["temp"], 1), "holiday_rain_hours": int(h["rain_hours"])})
hol = pd.DataFrame(rows)
hol.to_csv(os.path.join(OUT, "holidays_described.csv"), index=False)

fig, ax = plt.subplots(figsize=(8, 4.2))
x = np.arange(len(hol))
ax.bar(x - 0.2, hol["normal_day_trips"], width=0.38, color=C1, label="Normal day (same weekday, same month)")
ax.bar(x + 0.2, hol["holiday_trips"], width=0.38, color=C2, label="Holiday")
for i, c in enumerate(hol["change_pct"]):
    ax.text(i + 0.2, hol["holiday_trips"][i], f"{c:+.0f}%", ha="center", va="bottom", fontsize=9, color=INK2)
ax.set(title="Trips on the 3 holidays vs a normal day", ylabel="Trips per day (25% sample)", xticks=x,
       xticklabels=[f"{n}\n{d}" for n, d in zip(["Juneteenth", "Columbus Day", "Christmas"], hol["weekday"])])
ax.grid(axis="x", visible=False)
ax.legend(loc="upper right")
save(fig, "09_holidays_vs_normal_day.png")

log("\nHolidays (described, not tested):")
for _, r in hol.iterrows():
    log(f"  {r['holiday']} ({r['weekday']}): {r['holiday_trips']:,} trips vs {r['normal_day_trips']:,} "
        f"on a normal {r['weekday']} ({r['change_pct']:+.1f}%); casual share {r['holiday_casual_share_pct']}% "
        f"vs {r['normal_casual_share_pct']}%; {r['holiday_temp_c']} C, {r['holiday_rain_hours']} rainy hours")

log("\nSpearman correlation of trips per hour with weather:")
for k, v in corr.sort_values(ascending=False).items():
    log(f"  {k}: {v:+.2f}")

with open(os.path.join(OUT, "data_quality.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(report))
print(f"\nSaved outputs/hourly_demand.csv, outputs/data_quality.txt and {len(os.listdir(FIG))} charts.")
