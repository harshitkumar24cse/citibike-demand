"""
stage3_decisions.py - Stage 3: turn the Stage 2 results into numbers the rebalancing team can use.

1. Demand scenarios: expected trips per hour for typical weather and day types, from the
   Stage 2 regression (members and casual riders separately).
2. Station priority: the busiest stations and how unbalanced they get on working-day mornings
   (more bikes leaving than arriving = the station empties and needs bikes delivered).

Input:   outputs/hourly_demand.csv, ssot.parquet
Run:     python stage3_decisions.py
Output:  outputs/demand_scenarios.csv, outputs/station_priority.csv, outputs/stage3_results.txt
         outputs/figures/12_demand_scenarios.png
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

OUT = "outputs"
SCALE = 4  # our data is a 25% sample, so multiply by 4 for the whole system
C1, C2, INK, INK2, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df"
lines = []


def log(msg=""):
    print(msg)
    lines.append(msg)


# ----------------------------- 1. DEMAND SCENARIOS ----------------------------
hourly = pd.read_csv(os.path.join(OUT, "hourly_demand.csv"), parse_dates=["hour_ts"])
for col in ["member_trips", "casual_trips"]:
    hourly["log_" + col] = np.log(hourly[col] + 1)

# same regression as stage2_tests.py, so the numbers match the hypothesis results
FORMULA = ("{y} ~ temp_c + is_raining + wind_speed_ms + humidity_pct"
           " + C(hour) * is_non_working_day + C(day_of_week) + C(month)")
members = smf.ols(FORMULA.format(y="log_member_trips"), data=hourly).fit()
casual = smf.ols(FORMULA.format(y="log_casual_trips"), data=hourly).fit()

# typical conditions; wind and humidity are set to their usual values for each case
weather = {
    "Warm & dry (25 C)": dict(temp_c=25, is_raining=0, humidity_pct=60, wind_speed_ms=3, month=6),
    "Mild & dry (12 C)": dict(temp_c=12, is_raining=0, humidity_pct=65, wind_speed_ms=3.5, month=4),
    "Mild & rainy (12 C)": dict(temp_c=12, is_raining=1, humidity_pct=90, wind_speed_ms=4.5, month=4),
    "Cold & dry (0 C)": dict(temp_c=0, is_raining=0, humidity_pct=60, wind_speed_ms=4, month=12),
}
moments = {
    "Weekday 8 am": dict(hour=8, is_non_working_day=0, day_of_week=2),
    "Weekday 5 pm": dict(hour=17, is_non_working_day=0, day_of_week=2),
    "Weekend 2 pm": dict(hour=14, is_non_working_day=1, day_of_week=5),
}
rows = []
for w_name, w in weather.items():
    for m_name, m in moments.items():
        case = pd.DataFrame([{**w, **m}])
        mem = (np.exp(members.predict(case)[0]) - 1) * SCALE
        cas = (np.exp(casual.predict(case)[0]) - 1) * SCALE
        rows.append({"weather": w_name, "moment": m_name, "member_trips": round(mem),
                     "casual_trips": round(cas), "total_trips": round(mem + cas),
                     "casual_share_pct": round(cas / (mem + cas) * 100, 1)})
scen = pd.DataFrame(rows)
scen.to_csv(os.path.join(OUT, "demand_scenarios.csv"), index=False)

log("== Expected trips per hour, whole system (sample x 4) ==")
table = scen.pivot(index="weather", columns="moment", values="total_trips").loc[list(weather), list(moments)]
log(table.to_string())
log("\nCasual share (%):")
log(scen.pivot(index="weather", columns="moment", values="casual_share_pct").loc[list(weather), list(moments)].to_string())

warm_we = table.loc["Warm & dry (25 C)", "Weekend 2 pm"]
cold_we = table.loc["Cold & dry (0 C)", "Weekend 2 pm"]
dry_am = table.loc["Mild & dry (12 C)", "Weekday 8 am"]
wet_am = table.loc["Mild & rainy (12 C)", "Weekday 8 am"]
log(f"\nWeekend 2 pm: warm & dry {warm_we:,} vs cold & dry {cold_we:,} trips per hour "
    f"({warm_we / cold_we:.1f}x as many)")
log(f"Weekday 8 am at 12 C: rainy {wet_am:,} vs dry {dry_am:,} trips per hour "
    f"({(wet_am / dry_am - 1) * 100:+.0f}%)")

# chart: grouped bars, one group per weather, one bar per moment (colours = moments)
fig, ax = plt.subplots(figsize=(9, 4.4))
x = np.arange(len(weather))
colors = [C1, C2, "#1baf7a"]
for i, (m_name, color) in enumerate(zip(moments, colors)):
    vals = table[m_name].values
    ax.bar(x + (i - 1) * 0.27, vals, width=0.25, color=color, label=m_name)
ax.set_title("Expected trips per hour across the whole system, by weather and time",
             loc="left", fontweight="bold", color=INK)
ax.set(xticks=x, xticklabels=list(weather), ylabel="Trips per hour (whole system)")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.grid(axis="y", color=GRID)
ax.set_axisbelow(True)
ax.legend(frameon=False, loc="upper right")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "figures", "12_demand_scenarios.png"), dpi=150, facecolor="white")
plt.close(fig)

# ----------------------------- 2. STATION PRIORITY ----------------------------
trips = pd.read_parquet("ssot.parquet", columns=["start_station_id", "start_station_name", "end_station_id",
                                                 "hour", "is_non_working_day", "start_station_capacity"])
trips["start_station_id"] = trips["start_station_id"].astype(str)
trips["end_station_id"] = trips["end_station_id"].astype(str)
n_days = hourly.loc[hourly["is_non_working_day"] == 0, "date"].nunique()

# working-day mornings (7-10 am): bikes leaving vs bikes arriving at each station
am = trips[(trips["is_non_working_day"] == 0) & trips["hour"].isin([7, 8, 9])]
leaving = am.groupby("start_station_id").size()
arriving = am.groupby("end_station_id").size()
flow = pd.DataFrame({"leaving": leaving, "arriving": arriving}).fillna(0)
# per morning, whole system: net bikes lost (positive = station empties)
flow["net_bikes_lost_per_morning"] = (flow["leaving"] - flow["arriving"]) * SCALE / n_days

info = (trips.groupby("start_station_id")
        .agg(name=("start_station_name", "first"), capacity=("start_station_capacity", "first"),
             trips_total=("start_station_name", "size")))
st = info.join(flow, how="left").fillna({"net_bikes_lost_per_morning": 0})
st["trips_per_day"] = (st["trips_total"] * SCALE / hourly["date"].nunique()).round()
# a station is a top priority if it loses more bikes in one morning than it can hold
st["lost_vs_capacity_pct"] = (st["net_bikes_lost_per_morning"] / st["capacity"] * 100).round()
st = st.sort_values("net_bikes_lost_per_morning", ascending=False)
cols = ["name", "capacity", "trips_per_day", "net_bikes_lost_per_morning", "lost_vs_capacity_pct"]
st[cols].round(1).to_csv(os.path.join(OUT, "station_priority.csv"))

log("\n== Stations that empty fastest on working-day mornings (7-10 am), whole system ==")
top = st[cols].head(10).copy()
top["net_bikes_lost_per_morning"] = top["net_bikes_lost_per_morning"].round()
log(top.to_string())
log(f"\nStations losing at least half their capacity in one morning: "
    f"{(st['lost_vs_capacity_pct'] >= 50).sum()}")
fill = st.sort_values("net_bikes_lost_per_morning").head(10)[cols].copy()
fill["net_bikes_lost_per_morning"] = fill["net_bikes_lost_per_morning"].round()
log("\n== Stations that fill fastest on working-day mornings (negative = more bikes arrive) ==")
log(fill.to_string())

with open(os.path.join(OUT, "stage3_results.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))
print("\nSaved demand_scenarios.csv, station_priority.csv, stage3_results.txt and chart 12.")
