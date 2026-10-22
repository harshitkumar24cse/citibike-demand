"""
make_summary_pdf.py - Builds the one-page pre-submission summary PDF.
Sections follow the 8 headings of the ADS pre-submission guidelines.

Install:  pip install reportlab
Run:      python make_summary_pdf.py
Output:   ADS_Pre_Submission_Summary.pdf
"""
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, HRFlowable)

OUT = sys.argv[1] if len(sys.argv) > 1 else "ADS_Pre_Submission_Summary.pdf"
INK = colors.HexColor("#1F2933")
MUTED = colors.HexColor("#616E7C")
ACCENT = colors.HexColor("#1D3F72")
RULE = colors.HexColor("#CBD2D9")
FILL = colors.HexColor("#F2F4F7")

title = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=INK)
sub = ParagraphStyle("s", fontName="Helvetica", fontSize=8.5, leading=11, textColor=MUTED)
h = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=9.2, leading=11.5,
                   textColor=ACCENT, spaceBefore=7, spaceAfter=2)
body = ParagraphStyle("b", fontName="Helvetica", fontSize=8.8, leading=11.4, textColor=INK)
bullet = ParagraphStyle("bl", parent=body, leftIndent=9, bulletIndent=0, spaceAfter=0.6)
cell = ParagraphStyle("c", parent=body, fontSize=8.3, leading=10.2)
cellb = ParagraphStyle("cb", parent=cell, fontName="Helvetica-Bold")


def section(name, *items):
    return [Paragraph(name.upper(), h)] + list(items)


def bullets(*lines):
    return [Paragraph(l, bullet, bulletText="•") for l in lines]


def table(rows, widths, header=True):
    t = Table([[Paragraph(c, cellb if (header and i == 0) or j == 0 and not header else cell)
                for j, c in enumerate(r)] for i, r in enumerate(rows)],
              colWidths=[w * mm for w in widths])
    style = [
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), FILL))
    t.setStyle(TableStyle(style))
    return t


story = [
    Paragraph("Decoding Citi Bike Demand: The Impact of Weather, Seasonality and Holidays in NYC", title),
    Spacer(1, 2),
    Paragraph("Advanced Data Science &middot; Project Pre-Submission", sub),
    Spacer(1, 3),
    HRFlowable(width="100%", thickness=0.8, color=ACCENT),
]

story += section(
    "1. Project and group",
    Paragraph("<b>Group 14:</b> Harshit Kumar (240470) &middot; Ishaan Jatain (240484) &middot; "
              "Himanshu Yadav (__________) &middot; <b>Code:</b> "
              "github.com/harshitkumar24cse/citibike-demand", body),
)

story += section(
    "2. Stakeholder and problem",
    Paragraph(
        "<b>Stakeholder:</b> Citi Bike operations and rebalancing team (NYC). <b>Problem:</b> demand "
        "swings with weather, season and holidays, but bikes are rebalanced on fixed routines, so "
        "stations run empty or full. <b>Why it matters:</b> this causes lost trips and wasted truck "
        "runs; knowing how demand shifts lets the team move bikes ahead of time.", body),
)

story += section(
    "3. Research questions and hypotheses",
    Paragraph("<b>RQ1</b> How much do weather and the calendar change hourly demand? "
              "<b>RQ2</b> Do members and casual riders respond differently?", body),
    *bullets(
        "<b>H1</b> Warmer hours have more trips. "
        "<b>H2</b> Rainy hours have fewer trips than dry hours at similar temperatures.",
        "<b>H3</b> Casual riders are more weather-sensitive than members. "
        "<b>H4</b> Casual trips are longer than member trips.",
        "<b>H5</b> Weekends have weaker commute peaks and a higher casual share than weekdays.",
    ),
)

story += section(
    "4. Data sources",
    table([
        ["Source and link", "Coverage and rows", "Key variables"],
        ["Citi Bike trips &middot; citibikenyc.com/system-data",
         "Apr, Jun, Oct, Dec 2025; 15.3 M trips, 25% sample",
         "Times, stations, coordinates, bike type, rider type"],
        ["Open-Meteo weather &middot; open-meteo.com", "Same months, 2,928 hours",
         "Temperature, rain, wind, humidity, pressure, cloud"],
        ["NOAA daily records &middot; ncei.noaa.gov", "Same months, 122 days",
         "Max/min temperature, rain (validation only)"],
        ["Citi Bike GBFS stations &middot; gbfs.citibikenyc.com", "~2,500 stations (current)",
         "Capacity, location"],
        ["US/NY holidays &middot; Python holidays", "14 in 2025 (3 in study months)",
         "Holiday date and name"],
    ], [64, 52, 58]),
    Spacer(1, 2.5),
    Paragraph("<b>Rows:</b> 3,822,094 trips &times; 41 variables. <b>Constraints:</b> ~3 GB of trip "
              "files (seeded 25% sample for 8 GB RAM); no NOAA hourly data for Dec 2025, so Open-Meteo "
              "is used throughout and checked against NOAA (temperature r = 0.99, wet days agree 92%); "
              "station data is a current snapshot (96.6% match).", body),
)

story += section(
    "5. Integration plan (SSOT)",
    *bullets(
        "<b>Keys:</b> one row per trip; start hour &rarr; weather; station ID &rarr; capacity; "
        "date &rarr; holiday. Weather converted from UTC to New York time.",
        "<b>Cleaning:</b> duplicate ride IDs dropped (0); trips under 1 or over 180 min (4,410) and "
        "outside the study months (361) removed.",
        "<b>Missing values:</b> weather gaps up to 3 h interpolated (none); unmatched stations and "
        "coordinates left empty.",
        "<b>Units:</b> &deg;C, mm, m/s, hPa, %, km, min, km/h. <b>Checks:</b> row count unchanged "
        "after joins; unmatched weather 0%, stations 3.4%.",
    ),
)

story += section(
    "6. Methods and BADIR workflow",
    table([
        ["Business question", "When, and by how much, do weather and the calendar shift demand?"],
        ["Analysis plan", "Trips per hour; EDA and correlation; t-test, Mann-Whitney U, Kruskal-Wallis, "
                          "chi-square; multiple regression on weather and calendar."],
        ["Data collection", "build_ssot.py pipeline builds the SSOT (done)."],
        ["Insights", "Effect sizes with confidence intervals; hypotheses rated supported, not "
                     "supported or inconclusive."],
        ["Recommendations", "Rebalancing and staffing rules for the operations team."],
    ], [32, 142], header=False),
)

story += section(
    "7. Validation and decision value",
    Paragraph(
        "Each hypothesis gets a test with effect size, a chart and a robustness check (per month, "
        "weekdays only, non-parametric); unsupported results are valid outcomes. <b>Decision "
        "value:</b> change in trips per &deg;C, rainy hour and day type &rarr; extra rebalancing "
        "before warm, dry weekends; lighter dispatch in rain or freezing cold; priority for large "
        "stations.", body),
)

story += section(
    "8. Limitations and next steps",
    *bullets(
        "<b>Assumptions:</b> one weather point for the city; under 0.1 mm/h counts as dry; "
        "1-180 min trips are genuine.",
        "<b>Constraints:</b> one month per season; trips understate demand at empty or full stations; "
        "station snapshot; only 3 holidays (described, not tested); association, not causation.",
        "<b>Milestones:</b> Stage 1 problem, data, SSOT (done) &rarr; Stage 2 quality report, EDA, "
        "tests &rarr; Stage 3 findings, recommendations, roadmap.",
        "<b>Deviations:</b> none; all requirements met (&ge;100,000 rows, &ge;20 variables, "
        "multiple sources, no Kaggle).",
    ),
)

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                        topMargin=12 * mm, bottomMargin=10 * mm,
                        title="ADS Pre-Submission Summary")
doc.build(story)
