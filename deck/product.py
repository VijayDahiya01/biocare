# -*- coding: utf-8 -*-
"""Slides 1-10: BioCore explained as a standalone product, then the join to
QuickCampus. Nothing here assumes the audience has heard of BioCore before.
"""
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from ds import *

FOOT = "QuickCampus × BioCore"


# ------------------------------------------------------- 01 what is BioCore
def p01(prs):
    s = blank(prs)
    chrome(s, "WHAT IS BIOCORE?", "01", FOOT)

    txt(s, M, 2.15, 11.40, 1.30, "BIOCORE", 58, INK, LIGHT, ls=1.06, spc=3.0)
    txt(s, M, 3.45, 12.00, 0.60, "Face-based identity for schools & colleges",
        24, DEEP, LIGHT, ls=1.15)
    bar(s, M, 4.40)
    deck(s, "BioCore identifies students, staff and authorised guardians using a face at "
            "physical touchpoints across a campus.", 4.85)

    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, M, 6.05, CONTENT_W, 1.95, fill=TINT, adj=0.04)
    txt(s, 1.10, 6.35, 12.00, 0.55,
        "A student can walk through the school gate normally.", 24, DEEP, LIGHT, ls=1.15)
    for x, item in zip([1.10, 5.70, 10.30, 14.90],
                       ["No card", "No fingerprint machine",
                        "No QR code", "No stopping in a queue"]):
        dot(s, x, 7.33, 0.12, ACCENT)
        txt(s, x + 0.30, 7.25, 4.00, 0.32, item, 15, DEEP, SANS, ls=1.30)

    txt(s, M, 8.35, 16.20, 0.40,
        "BioCore recognises the student and creates a verified IN / OUT event "
        "automatically.", 17, BODY, SANS, ls=1.30)
    txt(s, M, 8.95, 14.00, 0.50, "Attendance is only the first use case.",
        20, INK, LIGHT, ls=1.20)

    footnote(s, "One identity layer for attendance, pickup, transport, hostels, exams "
                "and controlled campus areas.")
    return s


# ---------------------------------------------------- 02 the simplest example
def p02(prs):
    s = blank(prs)
    chrome(s, "THE SIMPLEST EXAMPLE", "02", FOOT)
    headline(s, "A student walks into school. BioCore knows who arrived.", 2.20)
    bar(s, M, 3.45)
    deck(s, "The whole sequence below happens while the student keeps walking.", 3.90)

    steps = [
        ("07:45", "Student enters",
         ["The camera sees the", "student as they walk", "through the gate."], None),
        ("STEP TWO", "BioCore verifies",
         ["The face is matched", "against the enrolled", "biometric template."], None),
        ("STEP THREE", "An arrival event", None,
         ["Student ID", "Gate", "Time", "IN"]),
        ("STEP FOUR", "Attendance fills",
         ["The student is marked", "present in the", "school's system."], None),
        ("STEP FIVE", "The parent knows",
         ["“Aarav arrived at", "school at 07:45.”"], None),
    ]
    xs = [0.60, 4.45, 8.30, 12.15, 16.00]
    ct, cw, ch = 4.90, 3.40, 3.00
    for i, (x, (eb, title, body, payload)) in enumerate(zip(xs, steps)):
        hot = (i == 1)
        card(s, x, ct, cw, ch,
             fill=TINT if hot else WHITE, line=ACCENT if hot else RULE,
             lw=1.4 if hot else 1.0)
        eyebrow_label(s, x + 0.32, ct + 0.35, 2.76, eb, color=ACCENT if hot else MUTED)
        card_title(s, x + 0.32, ct + 0.80, 2.76, title, size=16)
        if body:
            txt(s, x + 0.32, ct + 1.45, 2.76, 1.00, body, 13, MUTED, SANS, ls=1.36)
        else:
            for j, it in enumerate(payload):
                y = ct + 1.42 + j * 0.36
                dot(s, x + 0.32, y + 0.08, 0.10, ACCENT)
                txt(s, x + 0.56, y, 2.40, 0.30, it, 12.5, INK, MONO, ls=1.25)
        if i < 4:
            arrow(s, (x + cw + xs[i + 1]) / 2, ct + ch / 2, "right", 0.24)

    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, M, 8.45, CONTENT_W, 1.30, fill=TINT, adj=0.05)
    txt(s, 1.10, 8.80, 16.00, 0.60, "The child does not need to do anything.",
        26, DEEP, LIGHT, ls=1.10)
    return s


# ------------------------------ 03 why this is not a biometric attendance machine
def p03(prs):
    s = blank(prs)
    chrome(s, "WHY THIS IS NOT AN ATTENDANCE MACHINE", "03", FOOT)
    headline(s, "Students should not queue at an attendance machine.", 2.20)
    bar(s, M, 3.45)
    deck(s, "Every other system makes the child stop and do something. That is what "
            "creates the queue at the gate.", 3.90)

    eyebrow_label(s, M, 4.98, 4.00, "SYSTEM", color=MUTED)
    eyebrow_label(s, 4.60, 4.98, 10.00, "WHAT THE STUDENT DOES", color=MUTED)
    hline(s, M, 5.32, CONTENT_W)

    rows = [
        ("Fingerprint",  "Touch the machine   →   Wait your turn   →   Attendance", False),
        ("RFID card",    "Carry a card   →   Tap it   →   Attendance", False),
        ("QR code",      "Open the code   →   Scan it   →   Attendance", False),
        ("Face machine", "Stand one-by-one   →   Look at the device   →   Attendance", False),
        ("BioCore",      "Walk normally   →   Recognised automatically   →   Attendance", True),
    ]
    top, rh = 5.48, 0.56
    for i, (name, steps, hot) in enumerate(rows):
        y = top + i * rh
        if hot:
            shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, M, y - 0.06, CONTENT_W, rh,
                  fill=TINT, adj=0.12)
        txt(s, 1.00, y + 0.06, 3.40, 0.34, name, 14.5, DEEP if hot else INK,
            SANS, bold=hot, ls=1.20)
        txt(s, 4.60, y + 0.06, 14.20, 0.34, steps, 14.5, DEEP if hot else MUTED,
            SANS, ls=1.20)

    facts = [("No queue", "Students can enter in groups."),
             ("Nothing to carry", "No ID card, QR code or device."),
             ("No teacher action", "The event exists before the class begins.")]
    for x, (title, body) in zip(COL3, facts):
        card(s, x, 8.30, COL3_W, 1.55)
        txt(s, x + 0.42, 8.62, 5.19, 0.50, title, 20, INK, SANS, bold=True, ls=1.14)
        txt(s, x + 0.42, 9.16, 5.19, 0.40, body, 13.5, MUTED, SANS, ls=1.30)
    return s


# ------------------------------------------------ 04 not only attendance
def p04(prs):
    s = blank(prs)
    chrome(s, "BIOCORE IS NOT ONLY ATTENDANCE", "04", FOOT)
    headline(s, "One identity. Multiple campus workflows.", 2.20)
    bar(s, M, 3.45)
    deck(s, "The same enrolment answers a different question at every touchpoint on "
            "a campus.", 3.90)

    uses = [
        ("01  GATE ATTENDANCE",      "Who entered school, and when?"),
        ("02  GUARDIAN PICKUP",      "Who is authorised to collect this child?"),
        ("03  SCHOOL TRANSPORT",     "Did the child board or leave the bus?"),
        ("04  STAFF ATTENDANCE",     "Teachers and staff, without a separate machine."),
        ("05  HOSTEL",               "Student entry, exit and curfew records."),
        ("06  EXAMINATION",          "Is this the correct candidate?"),
        ("07  LABS & RESTRICTED",    "Who may enter this room?"),
    ]
    for i, (eb, q) in enumerate(uses):
        x = COL4[i % 4]
        y = 5.20 + (i // 4) * 2.35
        card(s, x, y, COL4_W, 2.15)
        eyebrow_label(s, x + 0.42, y + 0.32, 3.64, eb)
        txt(s, x + 0.42, y + 0.78, 3.64, 1.10, q, 16, INK, SANS, bold=True, ls=1.14)

    x, y = COL4[3], 5.20 + 2.35
    card(s, x, y, COL4_W, 2.15, fill=TINT, line=None)
    txt(s, x + 0.42, y + 0.42, 3.64, 1.40,
        "BioCore creates a verified identity event wherever an institution needs to "
        "know who was physically here.", 14, DEEP, SANS, ls=1.34)
    return s


# --------------------------------------------------- 05 a complete school day
def p05(prs):
    s = blank(prs)
    chrome(s, "A COMPLETE SCHOOL DAY", "05", FOOT)
    headline(s, "Morning to afternoon, one identity layer.", 2.20)
    bar(s, M, 3.45)
    deck(s, "Every one of these moments is the same recognition, asked a different "
            "question.", 3.90)

    moments = [
        ("07:30", "School bus",  ["Student boards. The", "boarding is recorded."]),
        ("07:45", "School gate", ["Student walks in.", "Arrival is recorded", "automatically."]),
        ("08:00", "Classroom",   ["The teacher already", "has attendance. Only", "exceptions remain."]),
        ("08:30", "Absence",     ["Who has not arrived", "is known, and the", "parent can be told."]),
        ("15:00", "Pickup",      ["The adult collecting", "the child can be", "verified."]),
        ("16:00", "Late stay",   ["Who is still inside", "campus after hours."]),
        ("ANY TIME", "Emergency", ["A live campus", "headcount, on", "demand."]),
    ]
    hline(s, M, 5.80, CONTENT_W, FAINT)
    for i, (when, title, body) in enumerate(moments):
        x = 0.60 + i * 2.72
        eyebrow_label(s, x, 5.35, 2.50, when, color=ACCENT, size=11)
        dot(s, x, 5.73, 0.16, ACCENT)
        txt(s, x, 6.10, 2.50, 0.40, title, 15, INK, SANS, bold=True, ls=1.14)
        txt(s, x, 6.75, 2.50, 1.00, body, 12.5, MUTED, SANS, ls=1.36)

    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, M, 8.20, CONTENT_W, 1.40, fill=TINT, adj=0.05)
    txt(s, 1.10, 8.60, 17.00, 0.55,
        "One identity layer, from the bus at 07:30 to a headcount in a drill.",
        24, DEEP, LIGHT, ls=1.15)
    return s


# ------------------------------------------------ 06 open and controlled mode
def p06(prs):
    s = blank(prs)
    chrome(s, "OPEN MODE AND CONTROLLED MODE", "06", FOOT)
    headline(s, "Not every camera needs to become a security gate.", 2.20)
    bar(s, M, 3.45)
    deck(s, "Many people hear “face recognition” and assume the system exists to "
            "stop children. It does not have to.", 3.90)

    panels = [
        (M, TINT, None, DEEP, DEEP, "OPEN MODE", "Identify, don't block.",
         ["Main school entrance", "Attendance", "Bus boarding", "Live headcount"],
         "Students continue walking normally."),
        (10.20, WHITE, RULE, MUTED, INK, "CONTROLLED MODE", "Verify before access.",
         ["Hostel", "Exam hall", "Lab", "Server room", "Restricted campus area"],
         "The door opens only for authorised people."),
    ]
    for (x, fill, ln, ebc, tc, eb, big, items, close) in panels:
        card(s, x, 5.05, 9.20, 4.55, fill=fill, line=ln, adj=0.05)
        eyebrow_label(s, x + 0.50, 5.45, 8.00, eb, color=ebc, size=12)
        txt(s, x + 0.50, 5.83, 8.20, 0.55, big, 26, tc, LIGHT, ls=1.10)
        for j, it in enumerate(items):
            y = 6.75 + j * 0.36
            dot(s, x + 0.50, y + 0.08, 0.14, ACCENT if fill == TINT else MUTED)
            txt(s, x + 0.82, y, 7.60, 0.30, it, 13.5, tc, SANS, ls=1.25)
        hline(s, x + 0.50, 8.65, 7.60, FAINT)
        txt(s, x + 0.50, 8.85, 8.00, 0.40, close, 14, ebc, SANS, ls=1.30)

    footnote(s, "The same BioCore platform supports both. The institution decides what "
                "each location should do.")
    return s


# ------------------------------------------------------- 07 privacy by design
def p07(prs):
    s = blank(prs)
    chrome(s, "PRIVACY BY DESIGN", "07", FOOT)
    headline(s, ["A face is used for identity.",
                 "The photograph does not need to become the database."], 2.15, size=38)
    bar(s, M, 4.05)
    deck(s, "Face recognition and photo storage are not the same thing. BioCore keeps "
            "the measurement, not the picture.", 4.45)

    eyebrow_label(s, M, 5.30, 6.00, "DURING ENROLMENT", color=MUTED)
    steps = ["The face is captured at enrolment.",
             "Measurements become an encrypted biometric template.",
             "The image is discarded per the configured enrolment flow.",
             "The encrypted template is what future matching uses."]
    vline(s, 1.00, 5.90, 3.35, FAINT)
    for j, st in enumerate(steps):
        y = 5.85 + j * 1.10
        dot(s, 0.93, y + 0.10, 0.16, ACCENT)
        txt(s, 1.50, y, 7.80, 0.40, st, 15, INK, SANS, ls=1.30)

    card(s, 10.20, 5.05, 9.20, 4.30, fill=TINT, line=None)
    eyebrow_label(s, 10.70, 5.42, 8.00, "FOR CHILDREN", color=DEEP, size=12)
    for j, it in enumerate(["Verifiable parental consent",
                            "A consent record and timestamp",
                            "The ability to withdraw",
                            "A non-biometric alternative",
                            "Purpose-limited use",
                            "No behavioural profiling"]):
        y = 5.95 + j * 0.52
        dot(s, 10.70, y + 0.09, 0.14, ACCENT)
        txt(s, 11.05, y, 7.80, 0.36, it, 14, DEEP, SANS, ls=1.28)

    footnote(s, "Designed to identify a person for an approved campus purpose — not to "
                "build a surveillance history.")
    return s


# --------------------------------------------------------- 08 how to deploy it
def p08(prs):
    s = blank(prs)
    chrome(s, "HOW A SCHOOL CAN DEPLOY IT", "08", FOOT)
    headline(s, "You do not need to rebuild the school gate.", 2.20)
    bar(s, M, 3.45)
    deck(s, "Start small, and use the infrastructure that is already there wherever "
            "possible.", 3.90)

    options = [
        ("01  TABLET", "A tablet on a stand", [
            "A tablet and a floor stand at the",
            "entrance. No civil work, no wiring,",
            "nothing drilled."], "Best for: a pilot."),
        ("02  EXISTING CCTV", "The camera you own", [
            "Where the angle and the light are",
            "suitable, we read the school's",
            "existing camera feed."], "Best for: a gate already covered."),
        ("03  EXISTING GATE", "The gate you own", [
            "Integrate with the sliding gate,",
            "boom barrier or access door that is",
            "already installed."], "Best for: a gate that works."),
        ("04  CONTROLLED ACCESS", "Turnstile or flap barrier", [
            "One person per pass, physically —",
            "only where access control is",
            "genuinely required."], "Best for: hostels, labs, exam halls."),
    ]
    ct, ch = 5.40, 3.60
    for x, (eb, title, body, best) in zip(COL4, options):
        card(s, x, ct, COL4_W, ch)
        eyebrow_label(s, x + 0.42, ct + 0.40, 3.64, eb)
        card_title(s, x + 0.42, ct + 0.88, 3.64, title)
        card_body(s, x + 0.42, ct + 1.50, 3.64, body)
        txt(s, x + 0.42, ct + 3.05, 3.64, 0.32, best, 12.5, ACCENT, SANS, ls=1.30)

    footnote(s, "A turnstile is rarely right for a school gate — it creates exactly the "
                "queue you are trying to remove.")
    return s


# ------------------------------------------------- 09 what BioCore provides
def p09(prs):
    s = blank(prs)
    chrome(s, "WHAT BIOCORE ACTUALLY PROVIDES", "09", FOOT)
    headline(s, "BioCore is the identity-event engine.", 2.20)
    bar(s, M, 3.45)
    deck(s, "It does one job: turn a face at a camera into a verified event that some "
            "other system can consume.", 3.90)

    cols = [
        ("INPUT", ["Student / staff ID", "Face enrolment", "Consent", "Camera / gate"]),
        ("BIOCORE", ["Face detection", "Face matching", "Identity verification",
                     "IN / OUT logic", "Gate & camera management",
                     "Consent management", "Event generation"]),
        ("OUTPUT", ["Student ID", "Timestamp", "Location / Gate ID", "IN / OUT",
                    "Verification status"]),
        ("ANY ERP OR SCHOOL SYSTEM", ["Attendance", "Parent notification", "Transport",
                                      "Reports", "Payroll", "Access control"]),
    ]
    ct, ch = 4.90, 4.10
    for i, (x, (eb, items)) in enumerate(zip(COL4, cols)):
        hot = (i == 1)
        card(s, x, ct, COL4_W, ch,
             fill=TINT if hot else WHITE, line=ACCENT if hot else RULE,
             lw=1.4 if hot else 1.0)
        eyebrow_label(s, x + 0.42, ct + 0.35, 3.64, eb, color=ACCENT if hot else MUTED)
        hline(s, x + 0.42, ct + 0.78, 3.60, ACCENT if hot else RULE)
        for j, it in enumerate(items):
            y = ct + 1.00 + j * 0.40
            dot(s, x + 0.42, y + 0.08, 0.10, ACCENT if hot else FAINT)
            txt(s, x + 0.68, y, 3.40, 0.32, it, 13, INK if hot else MUTED, SANS, ls=1.25)
        if i < 3:
            arrow(s, (x + COL4_W + COL4[i + 1]) / 2, ct + ch / 2, "right", 0.24)

    footnote(s, "The same engine, whichever system the institution already runs and "
                "wants the event to land in.")
    return s


# ------------------------------------------- 10 now bring QuickCampus in
def p10(prs):
    s = blank(prs)
    chrome(s, "WHERE QUICKCAMPUS COMES IN", "10", FOOT)
    headline(s, "This is where QuickCampus and BioCore fit together.", 2.20)
    bar(s, M, 3.45)
    deck(s, "Everything so far has been BioCore on its own. Here is the join.", 3.90)

    card(s, M, 4.75, 9.20, 2.90)
    eyebrow_label(s, 1.10, 5.10, 8.00, "QUICKCAMPUS ALREADY MANAGES", color=MUTED, size=12)
    owns = ["Student", "Class", "Parent", "Attendance",
            "Transport", "Hostel", "Communication", "Reports"]
    for j, it in enumerate(owns):
        x = 1.10 + (j // 4) * 4.20
        y = 5.60 + (j % 4) * 0.42
        dot(s, x, y + 0.09, 0.12, FAINT)
        txt(s, x + 0.30, y, 3.70, 0.32, it, 14, INK, SANS, ls=1.25)

    card(s, 10.20, 4.75, 9.20, 2.90, fill=TINT, line=ACCENT, lw=1.4)
    eyebrow_label(s, 10.70, 5.10, 8.00, "BIOCORE ADDS", color=ACCENT, size=12)
    txt(s, 10.70, 5.60, 8.20, 1.30,
        "Physical identity at the point where the real-world event happens.",
        22, DEEP, LIGHT, ls=1.20)

    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, M, 8.00, CONTENT_W, 1.00, fill=INK, adj=0.06)
    txt(s, 1.10, 8.32, 8.50, 0.45, "QuickCampus  =  system of record",
        20, WHITE, SANS, ls=1.20)
    txt(s, 10.70, 8.32, 8.50, 0.45, "BioCore  =  identity & event capture",
        20, PALE, SANS, ls=1.20)

    txt(s, M, 9.20, 18.00, 0.50,
        "No second ERP.    No second parent app.    No duplicate attendance database.",
        20, DEEP, LIGHT, ls=1.20)
    return s


BUILDERS = [p01, p02, p03, p04, p05, p06, p07, p08, p09, p10]
