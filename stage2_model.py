"""
stage2_model.py - Stage 2, part 3: a second line of evidence using machine learning.

We train a gradient boosting model (course topic: Advanced Machine Learning) to predict trips per
hour, then explain it with SHAP (course topic: Explainable AI). If the model agrees with the
regression about which weather factors matter and in which direction, the findings are stronger.

Input:   outputs/hourly_demand.csv
Run:     python stage2_model.py
Output:  outputs/model_results.txt
         outputs/figures/10_shap_importance.png
         outputs/figures/11_shap_temperature_rain.png
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score

OUT = "outputs"
C1, C2, INK, INK2, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df"
lines = []


def log(msg=""):
    print(msg)
    lines.append(msg)


# ----------------------------- 1. DATA -----------------------------------------
hourly = pd.read_csv(os.path.join(OUT, "hourly_demand.csv"), parse_dates=["hour_ts"])
FEATURES = ["temp_c", "is_raining", "precip_mm", "wind_speed_ms", "humidity_pct", "cloud_cover_pct",
            "hour", "day_of_week", "is_non_working_day", "month"]
NAMES = {"temp_c": "Temperature", "is_raining": "Rain (yes/no)", "precip_mm": "Rain amount",
         "wind_speed_ms": "Wind speed", "humidity_pct": "Humidity", "cloud_cover_pct": "Cloud cover",
         "hour": "Hour of day", "day_of_week": "Day of week", "is_non_working_day": "Weekend/holiday",
         "month": "Month"}

# Time-based split: the last 7 days of every month are the test set, so the model is
# checked on days it has never seen (a random split would leak neighbouring hours).
day_of_month = hourly["hour_ts"].dt.day
days_in_month = hourly["hour_ts"].dt.days_in_month
test = day_of_month > days_in_month - 7
X_train, X_test = hourly.loc[~test, FEATURES], hourly.loc[test, FEATURES]
y_train, y_test = hourly.loc[~test, "total_trips"], hourly.loc[test, "total_trips"]
log(f"Training hours: {len(X_train):,}   test hours (last 7 days of each month): {len(X_test):,}")

# ----------------------------- 2. MODEL ----------------------------------------
model = GradientBoostingRegressor(n_estimators=400, learning_rate=0.05, max_depth=4,
                                  subsample=0.8, random_state=42)
model.fit(X_train, y_train)
pred = model.predict(X_test)

# Baseline to beat: the average for that hour of day and day type in the training data
base = hourly.loc[~test].groupby(["hour", "is_non_working_day"])["total_trips"].mean()
base_pred = X_test.set_index(["hour", "is_non_working_day"]).index.map(base)

log("\n== How well does it predict unseen days? ==")
log(f"  Gradient boosting: R-squared {r2_score(y_test, pred):.3f}, "
    f"mean absolute error {mean_absolute_error(y_test, pred):.0f} trips per hour")
log(f"  Baseline (hour + day type average): R-squared {r2_score(y_test, base_pred):.3f}, "
    f"mean absolute error {mean_absolute_error(y_test, base_pred):.0f} trips per hour")

# ----------------------------- 3. SHAP -----------------------------------------
# SHAP splits each prediction into how much each feature pushed it up or down.
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_test)
importance = pd.Series(np.abs(shap_values).mean(axis=0), index=FEATURES).rename(NAMES).sort_values()

log("\n== Which features matter most? (mean |SHAP|, trips per hour) ==")
for name, v in importance.sort_values(ascending=False).items():
    log(f"  {name:<16} {v:6.0f}")

# direction check: does a higher temperature push predictions up, and rain push them down?
sv = pd.DataFrame(shap_values, columns=FEATURES, index=X_test.index)
temp_dir = np.corrcoef(X_test["temp_c"], sv["temp_c"])[0, 1]
# rain is split over two features (yes/no and amount), so add their SHAP values together
sv["rain_total"] = sv["is_raining"] + sv["precip_mm"]
rain_effect = sv.loc[X_test["is_raining"] == 1, "rain_total"].mean()
rainy_pred = pred[X_test["is_raining"].values == 1].mean()
log("\n== Do the directions agree with the regression? ==")
log(f"  Temperature: correlation between temperature and its SHAP value = {temp_dir:+.2f} "
    f"(positive = warmer pushes demand up)")
log(f"  Rain: in rainy hours, the two rain features change the prediction by {rain_effect:+.0f} trips per hour "
    f"(about {rain_effect / (rainy_pred - rain_effect) * 100:+.0f}% of what the model would predict without rain)")

with open(os.path.join(OUT, "model_results.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))

# ----------------------------- 4. CHARTS ---------------------------------------
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False})

fig, ax = plt.subplots(figsize=(8, 4.2))
ax.barh(importance.index, importance.values, color=C1, height=0.6)
for i, v in enumerate(importance.values):
    ax.text(v + 5, i, f"{v:.0f}", va="center", fontsize=9, color=INK2)
ax.set_title("What drives the model's predictions (mean |SHAP|)", loc="left", fontweight="bold", color=INK)
ax.set_xlabel("Average effect on predicted trips per hour")
ax.grid(axis="x", color=GRID)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "figures", "10_shap_importance.png"), dpi=150, facecolor="white")
plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(10, 4))
axes[0].scatter(X_test["temp_c"], sv["temp_c"], s=6, color=C1, alpha=0.4, lw=0)
axes[0].set(xlabel="Temperature (C)", ylabel="SHAP value (trips per hour)")
axes[0].set_title("Temperature: warmer pushes demand up", loc="left", fontweight="bold", color=INK)
groups = [sv.loc[X_test["is_raining"] == 0, "rain_total"], sv.loc[X_test["is_raining"] == 1, "rain_total"]]
axes[1].boxplot(groups, widths=0.5, showfliers=False, medianprops=dict(color=INK))
axes[1].set_xticks([1, 2], ["Dry hour", "Rainy hour"])
axes[1].set_ylabel("SHAP value of rain features (trips per hour)")
axes[1].set_title("Rain: pushes demand down", loc="left", fontweight="bold", color=INK)
for ax in axes:
    ax.axhline(0, color=INK2, lw=1)
    ax.grid(color=GRID)
    ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "figures", "11_shap_temperature_rain.png"), dpi=150, facecolor="white")
plt.close(fig)
print("\nSaved outputs/model_results.txt and charts 10-11.")
