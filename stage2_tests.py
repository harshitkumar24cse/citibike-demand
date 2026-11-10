"""
stage2_tests.py - Stage 2, part 2: hypothesis tests for H1-H5 and the season effect.

Input:   outputs/hourly_demand.csv (from stage2_eda.py), ssot.parquet (for trip durations)
Run:     python stage2_tests.py
Output:  outputs/test_results.txt          every test, effect size and verdict
         outputs/regression_effects.csv    weather effects from the regressions
         outputs/figures/08_weather_effects_member_casual.png

The main tool is a multiple regression of log(trips per hour) on weather, with hour of day,
day type, day of week and month as controls. Using the log means each effect reads as a
percentage change in trips. Standard errors are Newey-West (HAC) because neighbouring hours
are similar, which would otherwise make the results look more certain than they are.
"""

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

OUT = "outputs"
C1, C2, INK, INK2, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df"
lines = []


def log(msg=""):
    print(msg)
    lines.append(msg)


def pct(b):
    """Turn a regression coefficient on log(trips) into a % change."""
    return (np.exp(b) - 1) * 100


# ----------------------------- LOAD -------------------------------------------
hourly = pd.read_csv(os.path.join(OUT, "hourly_demand.csv"), parse_dates=["hour_ts"])
# log(trips + 1) so an hour with very few trips still works
for col in ["total_trips", "member_trips", "casual_trips"]:
    hourly["log_" + col] = np.log(hourly[col] + 1)

# ----------------------------- MAIN REGRESSION --------------------------------
# weather variables + controls for time of day, day type, weekday and month
# is_non_working_day already includes holidays, so no separate holiday term
FORMULA = ("{y} ~ temp_c + is_raining + wind_speed_ms + humidity_pct"
           " + C(hour) * is_non_working_day + C(day_of_week) + C(month)")


def fit(y, data):
    model = smf.ols(FORMULA.format(y=y), data=data)
    return model.fit(cov_type="HAC", cov_kwds={"maxlags": 24})


def effect(res, var):
    """% change in trips for one unit of var, with 95% confidence interval."""
    b = res.params[var]
    lo, hi = res.conf_int().loc[var]
    return pct(b), pct(lo), pct(hi)


log("== Main regression: log(trips per hour) on weather + calendar controls ==")
models = {"total": fit("log_total_trips", hourly),
          "member": fit("log_member_trips", hourly),
          "casual": fit("log_casual_trips", hourly)}
rows = []
for name, res in models.items():
    log(f"\n{name.title()} trips: R-squared {res.rsquared:.3f}, hours {int(res.nobs)}")
    for var, label in [("temp_c", "per +1 C"), ("is_raining", "rainy hour"),
                       ("wind_speed_ms", "per +1 m/s wind"), ("humidity_pct", "per +1% humidity")]:
        e, lo, hi = effect(res, var)
        p = res.pvalues[var]
        log(f"  {label:<18} {e:+6.1f}%   95% CI [{lo:+.1f}%, {hi:+.1f}%]   p = {p:.3g}")
        rows.append({"riders": name, "variable": var, "effect_pct": e, "ci_low": lo, "ci_high": hi, "p": p})
pd.DataFrame(rows).to_csv(os.path.join(OUT, "regression_effects.csv"), index=False)

# robustness: same regression for total trips, one month at a time (month control dropped)
log("\nRobustness - total trips, each month separately:")
monthly = {}
for m, season in [(4, "April"), (6, "June"), (10, "October"), (12, "December")]:
    sub = hourly[hourly["month"] == m]
    res = smf.ols(FORMULA.format(y="log_total_trips").replace(" + C(month)", ""), data=sub).fit(
        cov_type="HAC", cov_kwds={"maxlags": 24})
    t = effect(res, "temp_c")
    r = effect(res, "is_raining")
    monthly[m] = (t, r)
    log(f"  {season:<9} temp {t[0]:+5.1f}% [{t[1]:+.1f}, {t[2]:+.1f}]   "
        f"rain {r[0]:+6.1f}% [{r[1]:+.1f}, {r[2]:+.1f}]")

# robustness: working days only
res_wd = smf.ols(FORMULA.format(y="log_total_trips").replace(" + C(hour) * is_non_working_day", " + C(hour)"),
                 data=hourly[hourly["is_non_working_day"] == 0]).fit(cov_type="HAC", cov_kwds={"maxlags": 24})
twd, rwd = effect(res_wd, "temp_c"), effect(res_wd, "is_raining")
log(f"  Working days only: temp {twd[0]:+.1f}% [{twd[1]:+.1f}, {twd[2]:+.1f}]   "
    f"rain {rwd[0]:+.1f}% [{rwd[1]:+.1f}, {rwd[2]:+.1f}]")


def verdict(ok_main, ok_robust):
    if ok_main and ok_robust:
        return "SUPPORTED"
    if ok_main or ok_robust:
        return "INCONCLUSIVE"
    return "NOT SUPPORTED"


# ----------------------------- H1: temperature --------------------------------
log("\n== H1: warmer hours have more trips ==")
rho, p = stats.spearmanr(hourly["temp_c"], hourly["total_trips"])
log(f"  Spearman correlation (raw): rho = {rho:+.2f}, p = {p:.3g}")
t = effect(models["total"], "temp_c")
log(f"  Regression: {t[0]:+.1f}% trips per +1 C, 95% CI [{t[1]:+.1f}%, {t[2]:+.1f}%]")
h1 = verdict(t[1] > 0, all(monthly[m][0][1] > 0 for m in monthly) and twd[1] > 0)
log(f"  Verdict H1: {h1}")

# ----------------------------- H2: rain ---------------------------------------
log("\n== H2: rainy hours have fewer trips than dry hours at similar temperatures ==")
wet = hourly.loc[hourly["is_raining"] == 1, "total_trips"]
dry = hourly.loc[hourly["is_raining"] == 0, "total_trips"]
tt = stats.ttest_ind(wet, dry, equal_var=False)
mw = stats.mannwhitneyu(wet, dry, alternative="two-sided")
rbc = 1 - 2 * mw.statistic / (len(wet) * len(dry))  # rank-biserial: >0 means dry hours busier
log(f"  Raw means: rainy {wet.mean():.0f} vs dry {dry.mean():.0f} trips per hour")
log(f"  Welch t-test: t = {tt.statistic:.2f}, p = {tt.pvalue:.3g}")
log(f"  Mann-Whitney U: p = {mw.pvalue:.3g}, rank-biserial r = {rbc:+.2f}")
r = effect(models["total"], "is_raining")
log(f"  Regression (temperature, time and day held fixed): rain {r[0]:+.1f}%, "
    f"95% CI [{r[1]:+.1f}%, {r[2]:+.1f}%]")
h2 = verdict(r[2] < 0, all(monthly[m][1][2] < 0 for m in monthly) and rwd[2] < 0)
log(f"  Verdict H2: {h2}")

# ----------------------------- H3: casual vs member sensitivity ----------------
log("\n== H3: casual riders are more weather-sensitive than members ==")
for var, label in [("temp_c", "per +1 C"), ("is_raining", "rainy hour")]:
    m_e, c_e = effect(models["member"], var), effect(models["casual"], var)
    log(f"  {label:<11} members {m_e[0]:+.1f}% [{m_e[1]:+.1f}, {m_e[2]:+.1f}]   "
        f"casual {c_e[0]:+.1f}% [{c_e[1]:+.1f}, {c_e[2]:+.1f}]")
mt, ct = effect(models["member"], "temp_c"), effect(models["casual"], "temp_c")
mr, cr = effect(models["member"], "is_raining"), effect(models["casual"], "is_raining")
temp_stronger = ct[1] > mt[2]      # casual CI entirely above member CI
rain_stronger = cr[2] < mr[1]      # casual CI entirely below member CI
log(f"  Casual temperature effect clearly larger (CIs do not overlap): {temp_stronger}")
log(f"  Casual rain effect clearly larger (CIs do not overlap): {rain_stronger}")
h3 = verdict(temp_stronger, rain_stronger)
log(f"  Verdict H3: {h3}")

# ----------------------------- H4: trip duration ------------------------------
log("\n== H4: casual trips are longer than member trips (trip level) ==")
trips = pd.read_parquet("ssot.parquet", columns=["member_casual", "duration_min", "is_non_working_day"])
cas = trips.loc[trips["member_casual"] == "casual", "duration_min"]
mem = trips.loc[trips["member_casual"] == "member", "duration_min"]
mw4 = stats.mannwhitneyu(cas, mem, alternative="greater")
rbc4 = 2 * mw4.statistic / (len(cas) * len(mem)) - 1  # >0 means casual trips longer
pooled = np.sqrt(((len(cas) - 1) * cas.var() + (len(mem) - 1) * mem.var()) / (len(cas) + len(mem) - 2))
d4 = (cas.mean() - mem.mean()) / pooled
log(f"  Median: casual {cas.median():.1f} min vs member {mem.median():.1f} min")
log(f"  Mean:   casual {cas.mean():.1f} min vs member {mem.mean():.1f} min")
log(f"  Mann-Whitney U (casual > member): p = {mw4.pvalue:.3g}, rank-biserial r = {rbc4:+.2f}")
log(f"  Cohen's d = {d4:.2f}")
wd = trips[trips["is_non_working_day"] == 0]
wd_c = wd.loc[wd["member_casual"] == "casual", "duration_min"].median()
wd_m = wd.loc[wd["member_casual"] == "member", "duration_min"].median()
log(f"  Robustness, working days only: median casual {wd_c:.1f} vs member {wd_m:.1f} min")
h4 = verdict(mw4.pvalue < 0.05 and rbc4 > 0, wd_c > wd_m)
log(f"  Verdict H4: {h4}")
del trips

# ----------------------------- H5: weekends -----------------------------------
log("\n== H5: weekends have weaker commute peaks and a higher casual share ==")
# (a) peak strength = trips at 8 am and 5-6 pm divided by the average trips 10 am-3 pm
day_type = {0: "working", 1: "non-working"}
peak = {}
for k, name in day_type.items():
    h = hourly[hourly["is_non_working_day"] == k].groupby("hour")["total_trips"].mean()
    peak[name] = h[[8, 17, 18]].mean() / h[10:15].mean()
    log(f"  Peak ratio ({name} days): {peak[name]:.2f}  (1.0 = no commute peak)")
rush = hourly[hourly["hour"].isin([8, 17, 18])]
mw5 = stats.mannwhitneyu(rush.loc[rush["is_non_working_day"] == 0, "total_trips"],
                         rush.loc[rush["is_non_working_day"] == 1, "total_trips"], alternative="greater")
log(f"  Mann-Whitney, trips at 8 am / 5-6 pm, working > non-working: p = {mw5.pvalue:.3g}")
# (b) casual share: chi-square on the counts of member/casual trips by day type
table = hourly.groupby("is_non_working_day")[["member_trips", "casual_trips"]].sum()
chi2, p_chi, _, _ = stats.chi2_contingency(table.values)
cramers_v = np.sqrt(chi2 / table.values.sum())  # 2x2 table, so min(r, c) - 1 = 1
share = table["casual_trips"] / table.sum(axis=1)
log(f"  Casual share: working {share[0]:.1%} vs non-working {share[1]:.1%}")
log(f"  Chi-square: chi2 = {chi2:,.0f}, p = {p_chi:.3g}, Cramer's V = {cramers_v:.3f}")
h5 = verdict(peak["non-working"] < peak["working"] and mw5.pvalue < 0.05,
             share[1] > share[0] and p_chi < 0.05)
log(f"  Verdict H5: {h5}")

# ----------------------------- Season effect ----------------------------------
log("\n== Season effect: does hourly demand differ between the four seasons? ==")
groups = [g["total_trips"].values for _, g in hourly.groupby("season")]
kw = stats.kruskal(*groups)
eps2 = (kw.statistic - len(groups) + 1) / (len(hourly) - len(groups))  # epsilon-squared
log(f"  Median trips per hour: {hourly.groupby('season')['total_trips'].median().to_dict()}")
log(f"  Kruskal-Wallis: H = {kw.statistic:.1f}, p = {kw.pvalue:.3g}, epsilon-squared = {eps2:.3f}")

# ----------------------------- SUMMARY ----------------------------------------
log("\n== Summary of verdicts ==")
for h, v in [("H1 warmer -> more trips", h1), ("H2 rain -> fewer trips", h2),
             ("H3 casual more weather-sensitive", h3), ("H4 casual trips longer", h4),
             ("H5 weekends: weaker peaks, more casual", h5)]:
    log(f"  {h:<40} {v}")

with open(os.path.join(OUT, "test_results.txt"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines))

# ----------------------------- CHART: weather effects by rider type -----------
eff = pd.DataFrame(rows)
eff = eff[eff["riders"].isin(["member", "casual"]) & eff["variable"].isin(["temp_c", "is_raining"])]
fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
for ax, var, title in [(axes[0], "temp_c", "Change in trips per +1 C"),
                       (axes[1], "is_raining", "Change in trips in a rainy hour")]:
    # one dot per rider type: the estimate, with a bar for its 95% confidence interval
    for y, who, color in [(1, "member", C1), (0, "casual", C2)]:
        row = eff[(eff["variable"] == var) & (eff["riders"] == who)].iloc[0]
        left = row["effect_pct"] - row["ci_low"]
        right = row["ci_high"] - row["effect_pct"]
        ax.errorbar(row["effect_pct"], y, xerr=[[left], [right]], fmt="o", ms=8, color=color, capsize=4, lw=2)
        ax.text(row["effect_pct"], y + 0.22, f"{row['effect_pct']:+.1f}%", ha="center", fontsize=9, color=INK2)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_title(title, loc="left", fontweight="bold", color=INK)
    ax.set(yticks=[1, 0], yticklabels=["Members", "Casual riders"], ylim=(-0.6, 1.6),
           xlabel="% change (dot = estimate, bar = 95% CI)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="x", color=GRID)
    ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "figures", "08_weather_effects_member_casual.png"), dpi=150,
            bbox_inches="tight", facecolor="white")
print("\nSaved outputs/test_results.txt, outputs/regression_effects.csv and chart 08.")
