"""
make_summary_pdf.py - Builds the one-page pre-submission summary PDF.

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
                                TableStyle, HRFlowable, KeepTogether)

OUT = sys.argv[1] if len(sys.argv) > 1 else "ADS_Pre_Submission_Summary.pdf"
INK = colors.HexColor("#1F2933")
MUTED = colors.HexColor("#616E7C")
ACCENT = colors.HexColor("#1D3F72")
RULE = colors.HexColor("#CBD2D9")
FILL = colors.HexColor("#F2F4F7")

title = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=INK)
sub = ParagraphStyle("s", fontName="Helvetica", fontSize=9, leading=12, textColor=MUTED)
h = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=9.5, leading=12,
                   textColor=ACCENT, spaceBefore=9, spaceAfter=3)
body = ParagraphStyle("b", fontName="Helvetica", fontSize=9, leading=12.5, textColor=INK)
bullet = ParagraphStyle("bl", parent=body, leftIndent=10, bulletIndent=0, spaceAfter=1.5)
cell = ParagraphStyle("c", parent=body, fontSize=8.5, leading=11)
cellb = ParagraphStyle("cb", parent=cell, fontName="Helvetica-Bold")


def section(name, *items):
    return [Paragraph(name.upper(), h)] + list(items)


def bullets(*lines):
    return [Paragraph(l, bullet, bulletText="•") for l in lines]


story = [
    Paragraph("Decoding Citi Bike Demand: The Impact of Weather, Seasonality and Holidays in NYC", title),
    Spacer(1, 3),
    Paragraph("Advanced Data Science &middot; End-Term Project &middot; Pre-Submission Summary", sub),
    Paragraph("Group 14 &middot; Harshit Kumar &middot; Ishaan Jatain &middot; Himanshu Yadav", sub),
    Paragraph("Code: github.com/harshitkumar24cse/citibike-demand", sub),
    Spacer(1, 6),
    HRFlowable(width="100%", thickness=0.8, color=ACCENT),
]

story += section(
    "1. Problem and stakeholder",
    Paragraph(
        "<b>Stakeholder:</b> Citi Bike operations and rebalancing team. "
        "<b>Problem:</b> demand changes sharply with weather, season and holidays, but bike "
        "rebalancing follows fixed schedules, so stations run empty or full. Measuring these "
        "effects lets the team move bikes and staff ahead of demand.", body),
)

story += section(
    "2. Research questions and hypotheses",
    Paragraph("<b>RQ1</b> How much do weather and the calendar change hourly demand? "
              "<b>RQ2</b> Do members and casual riders respond differently?", body),
    Spacer(1, 2),
    *bullets(
        "<b>H1</b> Warmer hours have more trips.",
        "<b>H2</b> Rainy hours have fewer trips than dry hours at similar temperatures.",
        "<b>H3</b> Casual riders are more weather-sensitive than members.",
        "<b>H4</b> Casual trips are longer than member trips.",
        "<b>H5</b> Weekends have weaker commute peaks and a higher casual share than weekdays.",
    ),
)

rows = [
    ["Source", "Coverage", "Used for"],
    ["Citi Bike trip data (citibikenyc.com)", "Apr, Jun, Oct, Dec 2025 (one month per season), 15.3 M trips; 25% random sample",
     "Trips, times, stations, rider type"],
    ["Hourly weather, Central Park (Open-Meteo archive; checked against NOAA daily)",
     "Same months, 2,928 hours", "Temperature, rain, wind"],
    ["Citi Bike GBFS station feed", "~2,500 stations (current snapshot)", "Station capacity"],
    ["US / NY public holidays (Python holidays)", "14 dates in 2025 (3 in study months)", "Holiday flag"],
]
tbl = Table([[Paragraph(c, cellb if i == 0 else cell) for c in r] for i, r in enumerate(rows)],
            colWidths=[66 * mm, 60 * mm, 48 * mm])
tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), FILL),
    ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 3.5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ("LEFTPADDING", (0, 0), (-1, -1), 4),
]))
story += section(
    "3. Data sources",
    tbl,
    Spacer(1, 4),
    Paragraph("<b>Final dataset:</b> 3,822,094 trips &times; 41 variables (accessed 22 Oct 2026). "
              "<b>Weather check:</b> daily max/min temperature correlate 0.99 with NOAA records; "
              "wet vs dry days agree on 92% of days.", body),
)

story += section(
    "4. Integration (single source of truth)",
    *bullets(
        "One row per trip. Trip start hour joins weather; station ID joins capacity; date joins holidays.",
        "Duplicate ride IDs removed; trips under 1 or over 180 minutes removed; removal counts logged.",
        "Weather gaps up to 3 hours interpolated; row count asserted unchanged after the joins.",
        "Derived fields: duration, distance, speed, hour, weekday, rush hour, season, temperature band.",
    ),
)

story += section(
    "5. Method",
    Paragraph(
        "Aggregate to trips per hour; exploratory analysis and correlation; two-sample and "
        "non-parametric tests for season, rain, weekday and rider type; multiple regression of "
        "hourly demand on weather and calendar. Each hypothesis is judged with a test, an effect "
        "size and a robustness check (each month separately, weekdays only).", body),
)

story += section(
    "6. Limitations",
    *bullets(
        "<b>One month per season:</b> April, June, October and December stand for the four "
        "seasons; other months and other years are not covered.",
        "<b>Season and temperature are linked:</b> temperature effects are also checked within "
        "each month, so they are not just season differences.",
        "<b>Modelled weather:</b> one Open-Meteo grid point for the whole city; short local "
        "showers can be missed (wet/dry days match NOAA on 92% of days).",
        "<b>Trips are not true demand:</b> empty stations and full docks hide riders who could not ride.",
        "<b>Station data:</b> capacity is a current snapshot; 3.4% of start stations do not match it.",
        "<b>Few holidays:</b> only Juneteenth, Columbus Day and Christmas fall in the study months.",
        "<b>Association, not causation:</b> events, tourism and transit disruptions are not measured.",
    ),
)

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                        topMargin=16 * mm, bottomMargin=14 * mm,
                        title="ADS Pre-Submission Summary")
doc.build(story)
