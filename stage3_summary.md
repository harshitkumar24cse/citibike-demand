# Stage 3 – Final inference and decision impact (plain language)

Group 14 · Decoding Citi Bike Demand. Script: `stage3_decisions.py`. Results in `outputs/`.
This follows the four Stage 3 parts of the project guidelines.

---

## 1. Final findings
| Hypothesis | Finding | Status |
|---|---|---|
| **H1** Warmer hours have more trips | +2.5% trips per +1 °C (95% CI 1.8–3.2%), positive in every month; ML model agrees | ✅ Supported |
| **H2** Rain → fewer trips at similar temperatures | −33% in a rainy hour (95% CI −41% to −24%), negative in every month; ML model agrees on direction | ✅ Supported |
| **H3** Casual riders more weather-sensitive | Temperature: casual +4.4% vs members +2.1% per °C (clearly larger). Rain: −40% vs −31% (intervals overlap) | ❓ Inconclusive – supported for temperature, not for rain |
| **H4** Casual trips are longer | Median 12.4 vs 8.2 minutes; medium effect (Cohen's d = 0.60) | ✅ Supported |
| **H5** Weekends: weaker commute peaks, higher casual share | Peak ratio 2.0 on working days vs 0.84 on weekends; casual share 23% vs 15% | ✅ Supported |
| Season | Winter median demand is about a third of summer's; clear difference between seasons | Confirmed |
| Holidays | All 3 holidays had fewer trips (−24% to −75%), but too few days to separate from weather | Described only |

**In one sentence:** demand is driven mainly by the **time of day and day type**, then by
**temperature** and **rain**; casual riders react more strongly to temperature than members.

## 2. Business implications – what the rebalancing team should do
**a) Plan with the weather forecast, not a fixed routine.** Expected trips per hour for the whole
system (`outputs/demand_scenarios.csv`, chart 12):

| Weather | Weekday 8 am | Weekday 5 pm | Weekend 2 pm |
|---|---|---|---|
| Warm & dry (25 °C) | 15,700 | 17,900 | 11,900 |
| Mild & dry (12 °C) | 10,400 | 11,700 | 7,500 |
| Mild & rainy (12 °C) | 6,300 | 7,100 | 4,500 |
| Cold & dry (0 °C) | 5,900 | 6,600 | 4,100 |

- A warm, dry weekend afternoon has about **2.9×** the demand of a cold one.
- A rainy weekday morning has about **39% fewer** trips than a dry one at the same temperature.

**Recommendations:**
1. **Warm, dry days → extra rebalancing capacity**, especially on weekend afternoons, when the casual
   share rises to about 27% and riders go to parks and waterfronts.
2. **Rainy or freezing hours → lighter truck dispatch** (about a third less demand); use the freed
   staff time for bike maintenance and station repairs.
3. **Working days → rebalance before the rush hours:** refill residential stations before 7 am and
   clear Midtown office stations, which fill up by 10 am.
4. **Weekends → shift the plan to midday**, because there is no commute peak.
5. **Winter → plan for about half of summer demand** (smaller crews, fewer trucks).

**b) Know which stations to fix first.** On working-day mornings (7–10 am), **45 stations lose at least
half their dock capacity** in bikes (`outputs/station_priority.csv`). Examples:
- **Empty fastest** (need bikes delivered): W 43 St & 10 Ave (−60 bikes per morning), FDR Drive & E 35 St,
  Grand St & Samuel Dickstein Plaza, Riverside Blvd & W 67 St.
- **Fill fastest** (need bikes removed): E 47 St & Park Ave (+92 bikes), 9 Ave & W 33 St, Broadway & W 25 St.

So the morning plan is simple: **move bikes from Midtown office stations back to residential stations**.

## 3. Impact and limitations
**Plausible benefits** (not measured, because we have no cost data):
- Fewer empty stations at the busiest times → fewer lost trips and happier riders.
- Fewer unnecessary truck runs on rainy and cold days → lower fuel and staff cost.
- A clear, explainable rule set the team can use every day with a weather forecast.

**Uncertainty and assumptions:**
- Effect sizes come with 95% confidence intervals (e.g. rain −24% to −41%) – plans should use ranges.
- The ML model gives a smaller rain effect (−17%) than the regression (−33%), because rain and humidity
  overlap; the true effect is likely in between.
- One weather point for the whole city; rain under 0.1 mm/h counted as dry; trips of 1–180 min kept.

**Analytical constraints:**
- One month per season (2025 only); results may differ in other months or years.
- Trips are not true demand: when a station is empty, the rider who could not ride is not recorded,
  so our numbers **underestimate** peak demand.
- Station capacity comes from today's station list (3.4% of trips not matched).
- Only 3 holidays – described, not tested.
- **Association, not causation:** we observed the data, we did not run an experiment.

## 4. Implementation roadmap
| Priority | Action | When | Who is responsible | How to measure success |
|---|---|---|---|---|
| 1 | Daily dispatch plan using tomorrow's weather forecast and the scenario table | Weeks 1–4 | Operations planning manager | Truck-hours per 1,000 trips; minutes stations are empty |
| 2 | Morning pre-positioning: refill the 45 fastest-emptying stations, clear Midtown office stations | Weeks 1–8 | Dispatch team lead | % of 7–10 am minutes the priority stations are empty or full |
| 3 | Rain and cold rule: cut dispatch by about a third, move staff to maintenance | Months 1–3 | Operations manager + crew supervisors | Cost per truck run; bikes repaired per week |
| 4 | Warm-weekend leisure plan for parks and waterfront stations | Months 2–3 (before summer) | Operations + marketing | Weekend empty-station minutes at leisure stations; casual trips |
| 5 | **Pilot test before full roll-out:** use the new plan in some areas and the old plan in similar areas, then compare | Months 3–6 | Data analytics team | Difference in lost trips and truck-hours between pilot and comparison areas |
| 6 | Collect better data: a full year, and station availability (empty/full) records | Months 6–12 | Data analytics team | Data available; model updated |

Step 5 matters because our results show **association, not causation**: a pilot (an A/B test, a course
topic) checks that the new plan really causes the improvement before it is used everywhere.
