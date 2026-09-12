# -*- coding: utf-8 -*-
"""The QuickCampus x BioCore partnership mini-deck (front 6 slides + appendix)."""
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from ds import *

FOOT = "QuickCampus × BioCore"


# ---------------------------------------------------------------- 01 cover
def s01(prs):
    s = blank(prs)
    chrome(s, "PARTNERSHIP PROPOSAL  |  QUICKCAMPUS × BIOCORE", "01", FOOT)

    headline(s, ["Turn existing attendance", "into automatic attendance."],
             2.40, size=46, width=11.40)
    bar(s, M, 4.30)
    deck(s, "QuickCampus already manages the student, the class, the parent and the "
            "attendance record. BioCore identifies who actually entered or left the "
            "campus, and hands you the event.", 4.80, width=11.00)

    hline(s, M, 6.20, 11.00)
    txt(s, M, 6.60, 11.00, 1.40,
        ["No second ERP.", "No second parent app.", "No duplicate attendance database."],
        22, DEEP, LIGHT, ls=1.42)
    txt(s, M, 8.80, 11.00, 0.80,
        "One integration, and the physical world starts filling a register you already sell.",
        15, MUTED, SANS, ls=1.36)

    # the chain: what happens, in order
    nodes = [
        ("AT THE GATE", "A student walks in", "No stopping, no card, no queue.",
         WHITE, RULE, MUTED, INK, MUTED),
        ("BIOCORE", "Identity is verified", "An encrypted template match.",
         TINT, ACCENT, ACCENT, INK, MUTED),
        ("QUICKCAMPUS", "The attendance record fills", "Your module. Your database.",
         INK, None, FAINT, WHITE, PALE),
        ("THE PARENT", "A message from your app", "Arrival, absence or departure.",
         WHITE, RULE, MUTED, INK, MUTED),
    ]
    top = 2.40
    for i, (eb, title, sub, fill, ln, ebc, tc, sc) in enumerate(nodes):
        card(s, 13.00, top, 6.40, 1.55, fill=fill, line=ln,
             lw=1.4 if ln == ACCENT else 1.0, adj=0.06)
        eyebrow_label(s, 13.42, top + 0.28, 5.56, eb, color=ebc, size=10.5)
        card_title(s, 13.42, top + 0.66, 5.56, title, size=17, color=tc)
        txt(s, 13.42, top + 1.06, 5.56, 0.30, sub, 12.5, sc, SANS, ls=1.30)
        if i < 3:
            arrow(s, 16.20, top + 1.55 + 0.225, "down", 0.24)
        top += 2.00
    return s


# ------------------------------------------------- 02 the objection, answered
def s02(prs):
    s = blank(prs)
    chrome(s, "THE FIRST THING THEY WILL SAY", "02", FOOT)
    headline(s, ["You already have attendance.", "Something still has to fill it."], 2.30)
    bar(s, M, 4.45)
    deck(s, "We are not asking to replace the attendance module. Today a teacher, a card "
            "or a device still has to generate the event. BioCore automates that capture "
            "at the gate and sends a verified event into QuickCampus.", 4.90)

    cards = [
        ("WHAT STAYS YOURS", "The record does not move", [
            "Student, class, parent, attendance table, reports",
            "and the app you already ship. We add nothing to it",
            "and we take nothing out of it."]),
        ("WHAT CHANGES", "Only the capture", [
            "No teacher entry, no card, no queue at a device.",
            "The gate produces the event, and the register is",
            "complete before the bell."]),
        ("WHAT IS NEW", "An event nobody had", [
            "Who physically entered, at which gate, at what",
            "time, with what confidence — the thing a paper",
            "register could never prove."]),
    ]
    for x, (eb, title, body) in zip(COL3, cards):
        card(s, x, 6.55, COL3_W, 3.15)
        eyebrow_label(s, x + 0.42, 6.95, 5.19, eb)
        card_title(s, x + 0.42, 7.42, 5.19, title)
        card_body(s, x + 0.42, 8.05, 5.19, body)
    return s


# ------------------------------------------------ 03 module-by-module value
def s03(prs):
    s = blank(prs)
    chrome(s, "WHAT BIOCORE ADDS TO QUICKCAMPUS", "03", FOOT)
    headline(s, "Eight modules you already sell. One layer underneath.", 2.20)
    bar(s, M, 3.45)
    deck(s, "BioCore does not replace a QuickCampus module. It makes more of them "
            "worth buying.", 3.90)

    rows = [
        ("Student Attendance", "Automatic attendance, captured at the gate"),
        ("Parent App", "Arrival, absence and departure events"),
        ("Student Transport", "Bus boarding and deboarding, verified"),
        ("Visitor Management", "Guardian and pickup identity"),
        ("College ERP", "Proxy attendance, materially reduced"),
        ("Hostel Management", "Entry, exit and curfew events"),
        ("Examination", "Candidate verification at the hall door"),
        ("Staff Management", "Touchless staff attendance into payroll"),
    ]
    top, rh = 5.25, 0.50
    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 9.20, 5.12, 10.20, len(rows) * rh + 0.26,
          fill=TINT, adj=0.03)
    eyebrow_label(s, M, 4.72, 8.00, "EXISTING QUICKCAMPUS MODULE", color=MUTED)
    eyebrow_label(s, 9.60, 4.72, 9.00, "WHAT BIOCORE ADDS", color=ACCENT)
    hline(s, M, 5.08, CONTENT_W, RULE)

    for i, (mod, add) in enumerate(rows):
        y = top + i * rh
        txt(s, 1.00, y + 0.11, 7.40, 0.34, mod, 16, INK, SANS, ls=1.20)
        txt(s, 9.60, y + 0.11, 9.40, 0.34, add, 16, DEEP, SANS, ls=1.20)
        if i < len(rows) - 1:
            hline(s, M, y + rh, CONTENT_W, RULE)

    footnote(s, "None of these is a new module. Each one is a module you already have, "
                "given a source of truth it never had.", top=9.60)
    return s


# ------------------------------------------------------------ 04 integration
def s04(prs):
    s = blank(prs)
    chrome(s, "THE INTEGRATION", "04", FOOT)
    headline(s, "One call in. One event back.", 2.20)
    bar(s, M, 3.45)
    deck(s, "No new database on your side, and no new app for the parent. The only new "
            "object in your world is an attendance event whose source happens to be "
            "a camera.", 3.90)

    cols = [
        ("QUICKCAMPUS SENDS", ["Student ID", "Name", "School or campus",
                               "Class and section", "Guardian relationship"]),
        ("BIOCORE HOLDS", ["Parental consent record", "Encrypted biometric template",
                           "Gate and camera map", "Match threshold per site"]),
        ("THE EVENT WE RETURN", ["Student ID", "Gate ID", "IN or OUT",
                                 "Timestamp", "Confidence and status"]),
        ("QUICKCAMPUS DOES", ["Attendance", "Parent notification",
                              "Dashboard", "Reports"]),
    ]
    ct, ch = 4.75, 3.30
    for i, (x, (eb, items)) in enumerate(zip(COL4, cols)):
        hot = (i == 1)
        card(s, x, ct, COL4_W, ch,
             fill=TINT if hot else WHITE, line=ACCENT if hot else RULE,
             lw=1.4 if hot else 1.0)
        eyebrow_label(s, x + 0.42, ct + 0.35, 3.64, eb,
                      color=ACCENT if hot else MUTED)
        hline(s, x + 0.42, ct + 0.78, 3.60, ACCENT if hot else RULE)
        for j, it in enumerate(items):
            y = ct + 0.98 + j * 0.42
            dot(s, x + 0.42, y + 0.09, 0.10, ACCENT if hot else FAINT)
            txt(s, x + 0.68, y, 3.40, 0.32, it, 13.5, INK if hot else MUTED, SANS, ls=1.25)
        if i < 3:
            arrow(s, (x + COL4_W + COL4[i + 1]) / 2, ct + ch / 2, "right", 0.24)

    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, M, 8.35, CONTENT_W, 1.55, fill=TINT, adj=0.05)
    eyebrow_label(s, 1.05, 8.62, 12.00,
                  "WHAT BIOCORE STORES  —  AND WHAT IT DOES NOT", color=DEEP)
    notes = ["The student record stays in QuickCampus.",
             "We receive only the identifier needed to match.",
             "Enrolment and camera images are not retained.",
             "Templates are encrypted. Withdrawal deletes them."]
    for x, n in zip([1.05, 5.70, 10.35, 15.00], notes):
        txt(s, x, 9.05, 4.20, 0.60, n, 12.5, DEEP, SANS, ls=1.30)
    return s


# ---------------------------------------------------------------- 05 phases
def s05(prs):
    s = blank(prs)
    chrome(s, "FOUR PHASES, FOUR THINGS TO SELL", "05", FOOT)
    headline(s, "Four things to sell, not one.", 2.30, size=44)
    bar(s, M, 4.45)
    deck(s, "Attendance starts the conversation. Guardian pickup is the one a principal "
            "actually loses sleep over — and it is a different problem from the "
            "register.", 4.90)

    phases = [
        ("01", "PHASE ONE", "Automatic attendance", [
            "Gate capture into the attendance module",
            "you already ship — the easiest yes, and",
            "the one every institution understands."]),
        ("02", "PHASE TWO", "Guardian pickup", [
            "Who physically collected this child",
            "today? Your visitor module knows the",
            "parent. This gives it a face."]),
        ("03", "PHASE THREE", "Bus attendance", [
            "Boarding and deboarding against the",
            "transport module, so a parent sees the",
            "child on and off the bus."]),
        ("04", "PHASE FOUR", "Hostel, exam, campus", [
            "Curfew, candidate verification and",
            "restricted areas — the college and",
            "hostel modules, finally enforceable."]),
    ]
    ct, ch = 6.25, 3.35
    for x, (num, eb, title, body) in zip(COL4, phases):
        card(s, x, ct, COL4_W, ch)
        shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x + 0.42, ct + 0.40, 0.62, 0.62,
              fill=TINT, adj=0.22)
        txt(s, x + 0.42, ct + 0.57, 0.62, 0.30, num, 13, ACCENT, MONO,
            align=PP_ALIGN.CENTER, spc=0.8)
        eyebrow_label(s, x + 0.42, ct + 1.25, 3.64, eb)
        card_title(s, x + 0.42, ct + 1.62, 3.64, title)
        card_body(s, x + 0.42, ct + 2.15, 3.64, body)

    footnote(s, "Each phase is a separate line on the same invoice, sold to institutions "
                "you already have.", top=9.85)
    return s


# ------------------------------------------------------ 06 the pilot + models
def s06(prs):
    s = blank(prs)
    chrome(s, "HOW WE WOULD START", "06", FOOT)
    headline(s, "One school first. The model can wait.", 2.20, size=44)
    bar(s, M, 3.45)
    deck(s, "Do not commit your customer base. Give us one cooperative school, and settle "
            "the commercial shape after you have both seen the numbers.", 3.90)

    # left: the ask
    card(s, M, 5.05, 9.20, 4.85, fill=TINT, line=None, adj=0.05)
    eyebrow_label(s, 1.10, 5.40, 8.00, "THE PILOT WE ARE ASKING FOR", color=DEEP, size=12)
    txt(s, 1.10, 5.78, 8.00, 0.55, "One school. One gate. Two weeks.",
        26, DEEP, LIGHT, ls=1.10)
    specs = ["One cooperative school, chosen by you",
             "One gate, 150–250 enrolled students",
             "Your attendance module runs unchanged, in parallel",
             "Two weeks, then a joint read of the numbers"]
    for i, sp in enumerate(specs):
        y = 6.45 + i * 0.33
        dot(s, 1.10, y + 0.08, 0.14, ACCENT)
        txt(s, 1.42, y, 7.60, 0.30, sp, 13.5, DEEP, SANS, ls=1.25)
    hline(s, 1.10, 7.88, 7.60, FAINT)
    eyebrow_label(s, 1.10, 8.04, 8.00, "WHAT WE MEASURE TOGETHER", color=DEEP)
    meas_a = ["Capture rate at the gate", "False accept and false reject",
              "Students processed per minute", "Teacher time recovered"]
    meas_b = ["Manual exceptions per day", "Reconciliation accuracy",
              "Parent notification latency", "Absence alerts correctly raised"]
    txt(s, 1.10, 8.40, 3.70, 1.10, meas_a, 12.5, MUTED, SANS, ls=1.32)
    txt(s, 5.10, 8.40, 4.30, 1.10, meas_b, 12.5, MUTED, SANS, ls=1.32)

    # right: how to package it
    card(s, 10.20, 5.05, 9.20, 4.85)
    eyebrow_label(s, 10.70, 5.45, 8.20, "THEN CHOOSE HOW TO PACKAGE IT",
                  color=MUTED, size=12)
    models = [
        ("01  WHITE-LABEL", "QuickCampus Smart Attendance",
         "You sell it under your own name. We charge you per student, campus or gate."),
        ("02  REVENUE SHARE", "A premium safeguarding add-on",
         "You price it into the school contracts you already hold, and we split the line."),
        ("03  TECHNOLOGY PARTNER", "SDK, APIs and the gate app",
         "You own sales and implementation. We provide the engine, consent service "
         "and recognition."),
    ]
    for i, (lbl, title, body) in enumerate(models):
        y = 5.85 + i * 1.22
        eyebrow_label(s, 10.70, y, 8.20, lbl, color=ACCENT, size=10.5)
        card_title(s, 10.70, y + 0.30, 8.20, title, size=16)
        txt(s, 10.70, y + 0.70, 8.20, 0.50, body, 12.5, MUTED, SANS, ls=1.32)
    return s


# --------------------------------------------- appendix: questions for them
def appendix(prs):
    s = blank(prs)
    chrome(s, "APPENDIX  —  FOR THE DISCUSSION", "20", FOOT)
    headline(s, "What we want to learn from you", 2.20)
    bar(s, M, 3.45)
    deck(s, "More useful in a first meeting than any slide in front of it.", 3.90)

    qs = [
        "How is student attendance captured in QuickCampus today — teacher entry, "
        "RFID, a biometric device, QR or an integration?",
        "Do your schools use the parent app for attendance and absence notifications?",
        "Does the attendance module expose an API that accepts an external attendance event?",
        "Do you already integrate biometric hardware vendors?",
        "Who sells and installs attendance hardware for your schools today?",
        "How many of your institutions need gate-based attendance rather than "
        "classroom attendance?",
        "Is guardian pickup or child handover handled inside QuickCampus today?",
        "Would you prefer white-label, API integration, or a marketplace add-on?",
        "Can we pick one Delhi/NCR school for a joint pilot?",
    ]
    for i, q in enumerate(qs):
        x = COL3[i % 3]
        y = 4.60 + (i // 3) * 1.72
        hot = (i == 3)          # the question that decides the architecture answer
        card(s, x, y, COL3_W, 1.62,
             fill=TINT if hot else WHITE, line=ACCENT if hot else RULE,
             lw=1.4 if hot else 1.0)
        eyebrow_label(s, x + 0.42, y + 0.24, 2.00, "%02d" % (i + 1),
                      color=ACCENT if hot else FAINT)
        txt(s, x + 0.42, y + 0.56, 5.19, 0.92, q, 13, INK if hot else BODY, SANS, ls=1.28)

    footnote(s, "If the answer to question four is yes, we are not asking anyone to change "
                "an architecture — only to add a source.", top=9.82)
    return s


BUILDERS = [s01, s02, s03, s04, s05, s06]
