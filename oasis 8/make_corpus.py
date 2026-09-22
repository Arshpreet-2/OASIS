"""Generate the synthetic demo corpus. Run: python make_corpus.py"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                               TableStyle, PageBreak)

OUT = "corpus"
os.makedirs(OUT, exist_ok=True)

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Title"], fontSize=15, spaceAfter=4,
                    alignment=0, fontName="Helvetica-Bold")
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=11, spaceBefore=11,
                    spaceAfter=4, fontName="Helvetica-Bold")
BODY = ParagraphStyle("BODY", parent=ss["Normal"], fontSize=9.5, leading=13.5,
                      spaceAfter=5)
SMALL = ParagraphStyle("SMALL", parent=ss["Normal"], fontSize=7.5, leading=10,
                       textColor=colors.HexColor("#666666"))
BANNER = ParagraphStyle("BANNER", parent=ss["Normal"], fontSize=8,
                        fontName="Helvetica-Bold",
                        textColor=colors.HexColor("#A63D3D"), spaceAfter=8)

NOTE = ("SYNTHETIC DOCUMENT - created for a Smart India Hackathon prototype "
        "demonstration. Not real plant data. No sponsor information is used.")


def doc(name, title):
    d = SimpleDocTemplate(os.path.join(OUT, name), pagesize=A4,
                          leftMargin=20 * mm, rightMargin=20 * mm,
                          topMargin=18 * mm, bottomMargin=18 * mm,
                          title=title)
    return d


def tbl(data, widths):
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFEFEF")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BBBBBB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


# =========================================================== 1 PUMP MANUAL
s = []
s.append(Paragraph("Centrifugal Pump P-101", H1))
s.append(Paragraph("Operation and Maintenance Manual &mdash; Crude Charge Service &mdash; "
                   "Document PM-P101 Rev. 4", BODY))
s.append(Paragraph(NOTE, SMALL))
s.append(Spacer(1, 8))

s.append(Paragraph("1. Equipment Data", H2))
s.append(tbl([
    ["Parameter", "Value"],
    ["Tag number", "P-101 / P-101A (standby)"],
    ["Service", "Crude charge to atmospheric distillation"],
    ["Type", "Horizontal centrifugal, single stage, API 610 OH2"],
    ["Rated flow", "420 m3/h"],
    ["Rated head", "185 m"],
    ["Design pressure", "28 bar g"],
    ["Normal suction pressure", "2.1 bar g"],
    ["Operating temperature", "185 deg C"],
    ["Driver", "Induction motor, 315 kW, 2970 rpm"],
], [150, 260]))

s.append(Paragraph("2. Mechanical Seal", H2))
s.append(Paragraph(
    "P-101 is fitted with a single cartridge mechanical seal to API 682 "
    "Category 2, Arrangement 1, with Plan 32 external flush. The seal faces are "
    "silicon carbide against carbon.", BODY))
s.append(Paragraph(
    "<b>The seal flush shall be maintained at 3 bar above suction pressure, "
    "measured at the flush line inlet.</b> Flush flow rate shall not fall below "
    "8 litres per minute. Operation outside these limits will cause the seal "
    "faces to run dry and fail prematurely.", BODY))
s.append(Paragraph(
    "Flush liquid shall be filtered to 25 micron. A blocked or partially "
    "restricted flush line is the most common cause of repeat seal failure in "
    "this service, and should be the first item checked when the interval "
    "between failures is observed to be shortening.", BODY))

s.append(Paragraph("3. Inspection Intervals", H2))
s.append(tbl([
    ["Item", "Interval", "Method"],
    ["Mechanical seal assembly", "6 months", "Visual, leak check"],
    ["Seal flush line and filter", "3 months", "Differential pressure"],
    ["Bearing vibration", "Monthly", "Handheld analyser"],
    ["Coupling alignment", "12 months", "Laser alignment"],
    ["Casing wear ring clearance", "36 months", "Dismantle and measure"],
], [170, 90, 150]))
s.append(Paragraph(
    "The mechanical seal inspection interval of six months applies to crude "
    "service. Where the interval between unplanned seal failures falls below "
    "120 days, the cause shall be investigated before the seal is replaced "
    "again.", BODY))

s.append(PageBreak())
s.append(Paragraph("4. Start-up Procedure", H2))
for i, line in enumerate([
    "Confirm suction and discharge valve positions.",
    "Establish seal flush and confirm 3 bar differential before starting.",
    "Vent casing at the high point until liquid appears.",
    "Confirm standby pump P-101A is isolated.",
    "Start driver and confirm discharge pressure within 10 percent of rated.",
    "Log start time, suction pressure and flush differential in the shift log.",
], 1):
    s.append(Paragraph(f"{i}. {line}", BODY))

s.append(Paragraph("5. Fault Finding", H2))
s.append(tbl([
    ["Symptom", "Likely cause", "Action"],
    ["Seal leakage within 90 days", "Flush line restriction", "Check filter dP, clean strainer"],
    ["High bearing vibration", "Misalignment or cavitation", "Check alignment, confirm NPSH"],
    ["Low discharge pressure", "Wear ring clearance", "Measure clearance at next shutdown"],
    ["Seal face scoring", "Solids in flush liquid", "Verify 25 micron filtration"],
], [120, 140, 150]))
doc("pump_manual_p101.pdf", "Pump P-101 Manual").build(s)


# =========================================================== 2 MAINTENANCE LOG
s = []
s.append(Paragraph("Maintenance History Log", H1))
s.append(Paragraph("Equipment P-101 &mdash; Crude Charge Pump &mdash; "
                   "Extract covering 2024 to 2026", BODY))
s.append(Paragraph(NOTE, SMALL))
s.append(Spacer(1, 8))

s.append(Paragraph("1. Work Orders Raised", H2))
s.append(tbl([
    ["WO number", "Date", "Description", "Downtime (h)"],
    ["WO-24118", "2024-04-12", "Mechanical seal replaced, routine", "14"],
    ["WO-24406", "2024-10-16", "Mechanical seal replaced, leakage", "18"],
    ["WO-25077", "2025-03-02", "Bearing replaced, high vibration", "22"],
    ["WO-25214", "2025-06-19", "Mechanical seal replaced, leakage", "16"],
    ["WO-25390", "2025-09-21", "Seal flush strainer cleaned", "4"],
    ["WO-25502", "2025-12-24", "Mechanical seal replaced, leakage", "19"],
    ["WO-26041", "2026-03-28", "Mechanical seal replaced, leakage", "17"],
    ["WO-26129", "2026-06-30", "Coupling alignment check", "6"],
], [75, 75, 190, 70]))

s.append(Paragraph("2. Seal Failure Intervals", H2))
s.append(tbl([
    ["Failure", "Date", "Days since previous", "Note"],
    ["1", "2024-04-12", "-", "Routine replacement"],
    ["2", "2024-10-16", "187", "Leakage observed at gland"],
    ["3", "2025-06-19", "246", "Leakage, flush dP not recorded"],
    ["4", "2025-12-24", "188", "Leakage, strainer found fouled"],
    ["5", "2026-03-28", "94", "Leakage, interval halved"],
], [50, 80, 110, 170]))
s.append(Paragraph(
    "The interval between seal failures has reduced from 187 days to 94 days "
    "over the period covered. Flush line differential pressure was not recorded "
    "consistently before September 2025.", BODY))

s.append(Paragraph("3. Consumables Used", H2))
s.append(tbl([
    ["Part number", "Description", "Quantity", "Unit cost (Rs.)"],
    ["SEAL-682-C2", "Cartridge mechanical seal", "5", "184000"],
    ["FLT-25M-04", "Flush filter element 25 micron", "9", "3200"],
    ["BRG-7312-BG", "Angular contact bearing", "2", "26500"],
], [110, 180, 60, 90]))
doc("maintenance_log_p101.pdf", "P-101 Maintenance Log").build(s)


# =========================================================== 3 HAZOP (RESTRICTED)
s = []
s.append(Paragraph("CONFIDENTIAL - RESTRICTED DISTRIBUTION", BANNER))
s.append(Paragraph("HAZOP Study Report", H1))
s.append(Paragraph("Crude Distillation Unit &mdash; Node 4, Column Overhead and "
                   "Charge Pump Circuit &mdash; Report HZ-CDU-04 Rev. 2", BODY))
s.append(Paragraph(NOTE, SMALL))
s.append(Spacer(1, 8))

s.append(Paragraph("1. Distribution", H2))
s.append(Paragraph(
    "This report is classified RESTRICTED. Distribution is limited to the "
    "process safety group, the unit manager, and nominated members of the "
    "operations team. It shall not be issued to contractors or third parties "
    "without written authorisation from the head of process safety.", BODY))

s.append(Paragraph("2. Safety Instrumented Functions", H2))
s.append(tbl([
    ["Tag", "Function", "Set point", "SIL"],
    ["PSHH-401", "Column overhead high pressure trip", "4.2 bar g", "SIL 2"],
    ["", "Deadband", "0.3 bar", ""],
    ["LSLL-412", "Column bottom low level trip", "18 percent", "SIL 2"],
    ["TSHH-430", "Furnace outlet high temperature trip", "372 deg C", "SIL 3"],
    ["FSLL-104", "P-101 low flow trip", "95 m3/h", "SIL 1"],
], [70, 200, 90, 60]))
s.append(Paragraph(
    "<b>The interlock set point for the crude distillation column is 4.2 bar "
    "with a 0.3 bar deadband.</b> The trip initiates overhead vapour routing to "
    "flare and simultaneously trips the charge pump P-101. Override of this "
    "interlock requires written authorisation from the unit manager and is "
    "permitted only during commissioning.", BODY))

s.append(PageBreak())
s.append(Paragraph("3. Selected Deviations", H2))
s.append(tbl([
    ["Node", "Deviation", "Cause", "Consequence", "Safeguard"],
    ["4.1", "High pressure", "Overhead condenser fouling",
     "Column relief lift, product loss", "PSHH-401 at 4.2 bar, PSV-403"],
    ["4.2", "No flow", "P-101 seal failure",
     "Furnace tube overheating", "FSLL-104 trip, standby P-101A"],
    ["4.3", "Low level", "Bottoms pump runaway",
     "Pump cavitation, vapour breakthrough", "LSLL-412 trip"],
    ["4.4", "High temperature", "Burner control failure",
     "Tube rupture, fire", "TSHH-430 at 372 deg C"],
], [40, 75, 95, 110, 110]))

s.append(Paragraph("4. Actions Arising", H2))
s.append(tbl([
    ["Action", "Description", "Owner", "Due"],
    ["A-04-01", "Confirm PSHH-401 proof test interval is 12 months",
     "Process safety", "2026-09-30"],
    ["A-04-02", "Record flush differential pressure on P-101 each shift",
     "Operations", "2026-08-15"],
    ["A-04-03", "Review seal failure trend against flush filter changes",
     "Reliability", "2026-10-31"],
], [60, 210, 80, 65]))
doc("hazop_report.pdf", "HAZOP Study CDU Node 4").build(s)


# =========================================================== 4 SOP
s = []
s.append(Paragraph("Standard Operating Procedure", H1))
s.append(Paragraph("Mechanical Seal Replacement on Rotating Equipment &mdash; "
                   "SOP-MNT-118 Rev. 6", BODY))
s.append(Paragraph(NOTE, SMALL))
s.append(Spacer(1, 8))

s.append(Paragraph("1. Scope", H2))
s.append(Paragraph(
    "This procedure covers replacement of cartridge mechanical seals on "
    "centrifugal pumps in hydrocarbon service. It does not cover double seals "
    "with barrier fluid systems, which are covered by SOP-MNT-121.", BODY))

s.append(Paragraph("2. Permits Required", H2))
s.append(tbl([
    ["Permit", "Issued by", "Validity"],
    ["Hot work permit (if welding)", "Area authority", "One shift"],
    ["Confined space entry (if applicable)", "Safety officer", "One shift"],
    ["Equipment isolation certificate", "Operations", "Until work complete"],
    ["Line breaking permit", "Area authority", "One shift"],
], [190, 120, 100]))

s.append(Paragraph("3. Procedure", H2))
for i, line in enumerate([
    "Obtain equipment isolation certificate and confirm electrical isolation at the motor control centre.",
    "Depressurise and drain the pump casing to the closed drain system.",
    "Purge with nitrogen until hydrocarbon content is below 1 percent LEL.",
    "Record flush line differential pressure before dismantling. This value is required for failure analysis.",
    "Remove coupling guard and disconnect coupling.",
    "Withdraw the cartridge seal as an assembly. Do not dismantle in the field.",
    "Inspect the seal faces and photograph any scoring or deposits.",
    "Fit the replacement cartridge, torquing gland bolts evenly to 45 Nm.",
    "Re-establish flush and confirm 3 bar differential before releasing for start-up.",
    "Complete the work order and attach the failure photographs.",
], 1):
    s.append(Paragraph(f"{i}. {line}", BODY))

s.append(Paragraph("4. Records", H2))
s.append(Paragraph(
    "A completed work order, the recorded flush differential pressure, and "
    "photographs of the failed seal faces shall be attached to the equipment "
    "history file within two working days of completion.", BODY))
doc("sop_seal_replacement.pdf", "SOP Seal Replacement").build(s)


# =========================================================== 5 INSPECTION REPORT
s = []
s.append(Paragraph("Equipment Inspection Report", H1))
s.append(Paragraph("P-101 Crude Charge Pump &mdash; Report INS-2026-0412 &mdash; "
                   "Inspection date 28 March 2026", BODY))
s.append(Paragraph(NOTE, SMALL))
s.append(Spacer(1, 8))

s.append(Paragraph("1. Inspection Details", H2))
s.append(tbl([
    ["Field", "Detail"],
    ["Equipment", "P-101, crude charge pump"],
    ["Work order", "WO-26041"],
    ["Reason", "Mechanical seal leakage at gland"],
    ["Inspector", "K. Nair, Reliability Engineer"],
    ["Downtime", "17 hours"],
], [130, 280]))

s.append(Paragraph("2. Findings", H2))
for line in [
    "The cartridge mechanical seal was found leaking at the gland face. Seal faces showed circumferential scoring consistent with dry running.",
    "The seal flush line strainer was found approximately 60 percent blocked with scale and particulate. Differential pressure across the filter was not recorded prior to shutdown.",
    "Measured flush differential at the point of isolation was 1.4 bar, against a required minimum of 3 bar above suction pressure.",
    "Bearing condition was satisfactory. Vibration readings taken before shutdown were within limits.",
    "Coupling alignment was checked and found within tolerance.",
]:
    s.append(Paragraph("&bull; " + line, BODY))

s.append(Paragraph("3. Assessment", H2))
s.append(Paragraph(
    "The failure is attributed to inadequate seal flush caused by strainer "
    "fouling, rather than to the seal itself. This is the fourth leakage "
    "failure on this equipment, and the interval between failures has reduced "
    "from 187 days to 94 days. The pattern is consistent with a progressive "
    "restriction in the flush circuit.", BODY))

s.append(Paragraph("4. Recommendations", H2))
for i, line in enumerate([
    "Replace the mechanical seal with a like-for-like cartridge unit, part SEAL-682-C2.",
    "Reduce the flush filter element change interval from 6 months to 3 months.",
    "Record flush differential pressure on each shift, per HAZOP action A-04-02.",
    "Review the upstream source of particulate in the flush liquid.",
], 1):
    s.append(Paragraph(f"{i}. {line}", BODY))
s.append(Spacer(1, 10))
s.append(Paragraph("Approval for the above work is requested from the "
                   "maintenance manager.", BODY))
doc("inspection_report_2026.pdf", "Inspection Report P-101").build(s)

print("written to", OUT + "/")
for f in sorted(os.listdir(OUT)):
    if f.endswith(".pdf"):
        print("  ", f, os.path.getsize(os.path.join(OUT, f)), "bytes")
