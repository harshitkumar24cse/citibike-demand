# Stage 2 – Step-by-step summary (plain language)

Group 14 · Decoding Citi Bike Demand. This file explains every Stage 2 step in simple words.
Scripts: `stage2_eda.py` (steps 1–3) and `stage2_tests.py` (steps 4–6). All results are in `outputs/`.

> All trip counts come from our **25% sample**. Multiply by about 4 for the real number of trips.
> Percentages (like "rain cuts trips by 33%") are the same either way.

---

## Step 1 – Data-quality check (trip level)
**What we did:** checked the final dataset before analysing it, and made a `dfSummary` report
(from the `summarytools` package) for both the trip dataset and the hourly table. `dfSummary`
shows, for every column: its type, missing values, number of distinct values, basic statistics
and a small chart. Open `outputs/dfsummary_ssot.html` and `outputs/dfsummary_hourly.html` in a browser.
**Result** (`outputs/data_quality.txt`):
- 3,822,094 trips, 41 columns, **0 duplicate ride IDs**.
- 83% of trips are by members, 17% by casual riders; 71% are on e-bikes.
- Typical trip: **8.7 minutes** (median), 1.5 km.
- Missing values are small: station capacity 3–5% (stations not in today's list), end location 0.25%.

**Why:** to make sure the data is clean and complete enough to trust the results.

## Step 2 – Aggregation: trips → trips per hour
**What we did:** grouped trips by the hour they started and counted them. Each of the **2,928 hours**
(4 months × ~732 hours) now has: total trips, member trips, casual trips, casual share, that hour's
weather and calendar information (hour, weekday, season, weekend/holiday).
**Result:** `outputs/hourly_demand.csv` – every trip is counted exactly once; no hour has zero trips.
**Why:** demand means *trips per hour*, and weather is measured per hour, so the hour is the fair
unit for comparing weather with demand.

## Step 3 – Exploratory data analysis (charts)
**What we did:** drew 7 charts (`outputs/figures/01`–`07`) to see the patterns before testing.
**What they show:**
| Chart | What we see |
|---|---|
| 01 Daily profile | Working days have two big peaks (8 am and 5–6 pm); weekends have one smooth midday hump |
| 02 Trips vs temperature | Both groups ride more when warmer; casual riders rise much more steeply |
| 03 Rain vs dry | Rainy hours have fewer trips in every season (−7% to −56%) |
| 04 By season | Summer and autumn busiest, winter about half as busy |
| 05 Trip duration | Casual trips are longer (median 12.4 vs 8.2 minutes) |
| 06 Casual share by hour | Casual share is higher on weekends/holidays at almost every hour |
| 07 Weather correlations | Temperature has the strongest link (+0.49); humidity negative (−0.45) |
| 09 Holidays | All 3 holidays had fewer trips than a normal day of the same weekday (see Step 7) |

**Why:** to understand the data and check our hypotheses make sense before formal testing.

## Step 4 – Main test: multiple regression
**What we did:** one equation that explains trips per hour using temperature, rain, wind and humidity,
while **holding fixed** the hour of day, working/non-working day, day of week and month.
We used the **log** of trips so each result reads as a **% change**. Confidence intervals use
Newey-West standard errors, because neighbouring hours are similar and would otherwise make us
look more certain than we are.
**Result:** the model explains **93%** of the ups and downs in hourly demand (R² = 0.93).

| Effect on trips per hour | All riders | Members | Casual riders |
|---|---|---|---|
| +1 °C warmer | **+2.5%** [1.8, 3.2] | +2.1% [1.5, 2.8] | **+4.4%** [3.4, 5.3] |
| Rainy hour | **−33%** [−41, −24] | −31% [−39, −22] | **−40%** [−47, −31] |
| +1 m/s wind | −3.7% | −3.5% | −4.6% |
| +1% humidity | −0.3% | −0.3% | −0.5% |

*(Numbers in brackets = 95% confidence interval.)*

**Why:** weather and the calendar are mixed together (summer is warm *and* touristy). Regression
separates them, so "rain −33%" means *rain alone, at the same temperature, hour and day*.

**A problem we fixed:** the first version also had a separate holiday variable. But "non-working day"
already includes holidays, so the two overlapped and broke the October calculation. We removed the
extra holiday variable.

## Step 5 – Tests for each hypothesis
| Hypothesis | Tests used | Key result | Verdict |
|---|---|---|---|
| **H1** Warmer → more trips | Spearman correlation, regression, each month separately, working days only | +2.5% per °C; positive in all 4 months | ✅ **Supported** |
| **H2** Rain → fewer trips (same temperature) | Welch t-test, Mann–Whitney U, regression, robustness | −33% in rainy hours; negative in all 4 months | ✅ **Supported** |
| **H3** Casual riders more weather-sensitive | Separate regressions for members and casual riders | Temperature: casual clearly stronger (+4.4% vs +2.1%). Rain: casual larger (−40% vs −31%) but the intervals overlap | ❓ **Inconclusive** (supported for temperature only) |
| **H4** Casual trips longer | Mann–Whitney U, Cohen's d, working days only | Median 12.4 vs 8.2 min; medium effect (d = 0.60) | ✅ **Supported** |
| **H5** Weekends: weaker peaks, more casual riders | Peak ratio, Mann–Whitney U, chi-square, Cramér's V | Peak ratio 2.0 on working days vs 0.84 on weekends; casual share 15% vs 23% | ✅ **Supported** |
| Season effect | Kruskal–Wallis, epsilon-squared | Median trips per hour: summer 1,649, autumn 1,485, spring 1,193, winter 550 | Clear difference (ε² = 0.12) |

**How a verdict is decided:** *supported* = the main result is in the expected direction with a 95%
interval that excludes zero **and** the robustness check agrees; *inconclusive* = only one of the
two holds; *not supported* = neither holds.

## Step 6 – Robustness checks
**What we did:** reran the regression for **each month on its own** and for **working days only**.
**Result:** warm weather increases trips and rain decreases them in **every** month:
- Rain: April −31%, June −17%, October −42%, December −42%.
- Temperature: strongest in December (+8.4% per °C) – each degree matters most when it is cold.
**Why:** if a result holds in every month, it is not caused by one unusual month.

## Step 7 – Holidays (described, not tested)
**What we did:** only 3 holidays fall in our months, too few for a fair test. So we compared each
holiday with the normal days of the **same weekday in the same month** (`outputs/holidays_described.csv`, chart 09).
| Holiday | Trips vs a normal day | Casual share | Weather that day |
|---|---|---|---|
| Juneteenth (Thu, 19 Jun) | −24% | 20.7% vs 18.1% | 25.6 °C, 7 rainy hours |
| Columbus Day (Mon, 13 Oct) | −58% | 11.0% vs 13.9% | 13.5 °C, 18 rainy hours |
| Christmas (Thu, 25 Dec) | −75% | 20.0% vs 9.6% | 1.9 °C, dry |

**What it means:** holidays have fewer trips, because commuters stay home. But each holiday also had
its own weather (Columbus Day was very rainy), so we cannot separate the holiday effect from the
weather with only 3 days. That is why holidays stay *descriptive* – and why our regression counts them
together with weekends as "non-working days".

## Step 8 – Machine-learning check: gradient boosting + SHAP
**What we did:** trained a **gradient boosting** model (course topic: Advanced ML) to predict trips per
hour from weather and calendar features, and explained it with **SHAP** (course topic: Explainable AI).
We trained on the first ~3 weeks of each month and tested on the **last 7 days**, which the model never saw.
**Result** (`outputs/model_results.txt`, charts 10–11):
- It predicts unseen days well: **R² = 0.89**, average error 246 trips per hour – half the error of a
  simple "average for that hour and day type" (R² 0.60).
- SHAP shows the biggest drivers are **hour of day**, then **temperature**, then humidity and day type.
- Directions agree with the regression: **warmer pushes demand up**, **rain pushes it down**.
- The model's rain effect is smaller (about −17% vs −33% in the regression) because humidity rises
  when it rains and the model gives part of rain's effect to humidity.

**Why:** a second, independent method that agrees with the regression makes the findings stronger
(the guidelines ask for "multiple lines of evidence").

## Revised analysis plan (Stage 2 → Stage 3)
- **Done:** H1–H5 tested; season effect confirmed; holidays described; ML check agrees.
- **Unresolved:** H3 is supported for temperature but not clearly for rain; holidays cannot be
  separated from weather with 3 days.
- **Next (Stage 3):** turn effect sizes into demand scenarios the team can use, find which stations
  empty or fill fastest, and write recommendations with an implementation roadmap.
- **Future work beyond this project:** a full year of data (more holidays), and station availability
  data to measure demand that is lost when stations are empty.

---

## What this means for the stakeholder (first look, Stage 3 will develop it)
- **Rain is the biggest single factor:** a rainy hour cuts demand by about a third → fewer trucks needed.
- **Warm weather adds demand**, especially from casual riders → extra bikes at leisure areas on warm days.
- **Working days need rush-hour rebalancing** (8 am, 5–6 pm); **weekends need a midday plan** with
  more casual riders.
- **Winter demand is about half of summer** → winter staffing can be lighter.

## Files produced
| File | What it is |
|---|---|
| `outputs/data_quality.txt` | Step 1 results |
| `outputs/hourly_demand.csv` | Step 2 – the hourly table (2,928 rows) |
| `outputs/figures/01–07` | Step 3 – EDA charts |
| `outputs/test_results.txt` | Steps 4–6 – every test, effect size and verdict |
| `outputs/regression_effects.csv` | Regression effects with confidence intervals |
| `outputs/figures/08` | Weather effects for members vs casual riders |
| `outputs/dfsummary_ssot.html`, `outputs/dfsummary_hourly.html` | dfSummary reports |
| `outputs/holidays_described.csv`, `outputs/figures/09` | Step 7 – holidays |
| `outputs/model_results.txt`, `outputs/figures/10–11` | Step 8 – gradient boosting + SHAP |

Stage 3 continues in `stage3_summary.md`.
