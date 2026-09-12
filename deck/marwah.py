# -*- coding: utf-8 -*-
"""BioCore for Marwah Sports Pvt. Ltd. - 11 slides, aimed at an Operations
Manager whose job is designing, implementing and refining procedures.

So the argument is operational rather than commercial: what a door procedure
can and cannot enforce today, what exactly changes in the run-sheet, what
happens when the system cannot read somebody, and what the gate hands back at
the end of the night. Palette, grid and type come from ds.py, i.e. from the
decks that already exist.
"""
from pptx.enum.shapes import MSO_SHAPE
from ds import *

FOOT = "For Marwah Sports"

# ------------------------------------------------------------------ 01 cover
def s01(prs):
    s = blank(prs)
    chrome(s, "BIOCORE  |  IDENTITY FOR ESPORTS", "01", FOOT)

    txt(s, M, 2.60, 11.40, 2.60,
        ["Your rules are good.", "The door is where they", "stop being enforced."],
        54, INK, LIGHT, ls=1.06)
    bar(s, M, 7.10)
    txt(s, M, 7.60, 11.00, 1.60,
        ["Walk-through entry. Passes that cannot be lent.",
         "Players who are who they say they are. Nothing kept afterwards."],
        18, BODY, SANS, ls=1.36)

    for t, (big, cap) in zip([2.60, 5.00, 7.40], [
            ("~0.35 sec", "Per person at the gate, on a tablet"),
            ("0 photos",  "Kept. On the device, or anywhere else"),
            ("1 hour",    "To stand up on site. No rack, no cabling")]):
        card(s, 13.00, t, 6.40, 2.00)
        txt(s, 13.50, t + 0.42, 5.40, 0.80, big, 36, ACCENT, LIGHT, ls=1.10)
        txt(s, 13.50, t + 1.30, 5.40, 0.40, cap, 13, MUTED, SANS, ls=1.30)
    return s


# ------------------------------------------------------ 02 the gap in the SOP
def s02(prs):
    s = blank(prs)
    chrome(s, "WHERE A PROCEDURE RUNS OUT", "02", FOOT)
    headline(s, ["A pass can be checked.", "A person cannot — not today."], H1)
    bar(s, M, BAR2)
    deck(s, "Every entry rule you write ends in the same two seconds: a staff member "
            "holding a pass, deciding by eye, with no way to establish that the holder "
            "is the buyer. Everything downstream inherits that gap.", DECK2)

    trio(s, [
        ("The pass is the identity",
         ["A band, a QR, a name on a list. Whoever",
          "holds it is admitted. The object cannot",
          "tell you who is carrying it."]),
        ("A lent pass is invisible",
         ["It scans clean the second time. Nothing in",
          "the log separates a genuine re-entry from",
          "a second person on one pass."]),
        ("The record says “scanned”",
         ["When a dispute reaches your desk on Monday",
          "there is a record of a pass being read,",
          "and none of a person walking in."]),
    ])
    footnote(s, "None of this is a staffing failure. It is what happens when the "
                "credential is an object instead of a person.", FOOT_Y)
    return s


# ----------------------------------------------------------------- 03 esports
def s03(prs):
    s = blank(prs)
    chrome(s, "ESPORTS", "03", FOOT)
    headline(s, ["The prize money is verified.", "The player at the keyboard is not."], H1)
    bar(s, M, BAR2)
    deck(s, "A roster is a contract, and a qualifier seat decides who advances. Both rest "
            "on somebody at the venue confirming that the person in the chair is the "
            "person on the sheet — the one check still made by eye.", DECK2)

    trio(s, [
        ("A ringer in the seat",
         ["A stronger player substituted in at a",
          "qualifier, or on the online-to-LAN handoff.",
          "Today nobody at the venue can disprove it."]),
        ("Ban evasion",
         ["A banned player returns on a new account",
          "under a new tag. An account resets in a",
          "minute. A face does not reset at all."]),
        ("A bracket that holds",
         ["A verified player in a verified seat, on a",
          "timestamped record. Payout attaches to a",
          "person rather than to a username."]),
    ])
    footnote(s, "Pre-match identity checks are becoming ordinary in tier-one esports — "
                "the referee checking the gloves before the bout.", FOOT_Y)
    return s


# ---------------------------------------------------------- 04 the arithmetic
def s04(prs):
    s = blank(prs)
    chrome(s, "WHAT AN UNCHECKED PASS COSTS", "04", FOOT)
    headline(s, "Every lent pass is a seat you did not sell", H1)
    bar(s, M, BAR1)
    deck(s, "We have not invented your numbers. The lending rate is the one thing only you "
            "can know, so it stays a variable — and the unit below is deliberately "
            "small, because it scales to whatever a real weekend looks like.", DECK1)

    card(s, M, 6.30, 11.60, 3.30)
    for x, head in zip([1.15, 4.75, 8.35],
                       ["IF THIS SHARE IS LENT", "PER 1,000 ADMISSIONS",
                        "AT ₹500 A PASS"]):
        txt(s, x, 6.70, 3.40, 0.34, head, 11.5, MUTED, MONO, spc=1.8)
    hline(s, 1.15, 7.22, 10.50)
    for i, (pct, n, money, hot) in enumerate(
            [("2%", "20", "₹10,000", False),
             ("5%", "50", "₹25,000", True),
             ("10%", "100", "₹50,000", False)]):
        y = 7.45 + i * 0.68
        col = ACCENT if hot else INK
        txt(s, 1.15, y, 3.40, 0.44, pct, 22, col, LIGHT, ls=1.20)
        txt(s, 4.75, y + 0.05, 3.40, 0.40, n, 17, col, SANS, ls=1.20)
        txt(s, 8.35, y + 0.05, 3.40, 0.40, money, 17, col, SANS, bold=hot, ls=1.20)

    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 12.90, 6.30, 6.50, 3.30, fill=TINT, adj=0.05)
    txt(s, 13.40, 6.72, 5.50, 0.40, "AND THE SECOND EFFECT", 11.5, DEEP, MONO, spc=1.8)
    txt(s, 13.40, 7.20, 5.50, 2.00,
        ["Minutes spent queueing outside",
         "are minutes not spent at merch,",
         "F&B or a sponsor booth inside.",
         "",
         "A faster door moves the crowd",
         "to the floor where it spends."], 13.5, DEEP, SANS, ls=1.36)

    footnote(s, "₹500 and 1,000 are placeholders, not a claim. Put your own gate "
                "price and your own admissions in, and the third column is yours.",
             FOOT_Y)
    return s


# ------------------------------------------------------ 05 the procedure delta
def s05(prs):
    s = blank(prs)
    chrome(s, "THE PROCEDURE, BEFORE AND AFTER", "05", FOOT)
    headline(s, "Your SOP gains one line. It does not gain a department.", H1)
    bar(s, M, BAR1)
    deck(s, "This is the whole operational delta on event day. Same posts, same shifts, "
            "same escalation path — what changes is what the door is able to prove.",
         DECK1)

    for x, fill, dotcol, label, rows in [
            (M, WHITE, FAINT, "TODAY", [
                "Staff match a pass to a face, by eye",
                "A lent pass scans clean and walks in",
                "Re-entry is a second manual judgement",
                "Disputes are settled from memory",
                "The headcount is an estimate at close"]),
            (10.30, TINT, ACCENT, "WITH BIOCORE", [
                "The gate confirms the person, in ~0.35 sec",
                "A pass that is not the buyer does not open",
                "Re-entry is the same walk-through",
                "Disputes carry a timestamped record",
                "The headcount is live, gate by gate"])]:
        dark = fill == TINT
        card(s, x, 5.30, 9.10, 4.30, fill=fill, line=TINT if dark else RULE)
        txt(s, x + 0.55, 5.72, 6.00, 0.34, label, 11.5, DEEP if dark else MUTED,
            MONO, spc=1.8)
        hline(s, x + 0.55, 6.18, 8.00, color=PALE if dark else RULE)
        for i, row in enumerate(rows):
            y = 6.48 + i * 0.60
            dot(s, x + 0.55, y + 0.09, 0.12, dotcol)
            txt(s, x + 0.85, y, 7.70, 0.34, row, 15, INK if dark else BODY,
                SANS, ls=1.30)

    footnote(s, "No new counter, no new role, and no second system for your staff to "
                "learn on the morning of the event.", FOOT_Y)
    return s


# ------------------------------------------------------------ 06 the exceptions
def s06(prs):
    s = blank(prs)
    chrome(s, "EXCEPTIONS, BY DESIGN", "06", FOOT)
    headline(s, ["The real test of an entry system", "is the person it cannot read."], H1)
    bar(s, M, BAR2)
    deck(s, "Cosplay masks, full-face helmets, an injury, a phone on 2% — or somebody "
            "who simply declines. Pretending those are rare is how a face system turns "
            "into your queue problem at ten in the morning.", DECK2)

    trio(s, [
        ("A manual lane always runs",
         ["Staffed and signposted beside the face lane",
          "at all times — never a fallback, never an",
          "apology, never a special case."]),
        ("A supervisor override",
         ["One tap admits anybody, with a reason code",
          "attached. The exception becomes a record",
          "instead of an argument at the door."]),
        ("Declining costs nothing",
         ["Opt-in is real precisely because the other",
          "lane is running anyway. Nobody waits longer",
          "for having said no."]),
    ])
    footnote(s, "Stated plainly: helmets and full-face prosthetics defeat every face "
                "system on the market, ours included. We built the lane instead of "
                "pretending otherwise.", FOOT_Y)
    return s


# ---------------------------------------------------------------- 07 the venue
def s07(prs):
    s = blank(prs)
    chrome(s, "BUILT FOR THE VENUE YOU ACTUALLY GET", "07", FOOT)
    headline(s, ["Arena WiFi collapses at doors-open.", "This runs without it."], H1)
    bar(s, M, BAR2)
    deck(s, "Recognition happens on the tablet at the gate. There is no round trip to a "
            "cloud, and no dependency on venue connectivity at the one moment it is "
            "guaranteed to be saturated.", DECK2)

    trio(s, [
        ("Offline by design",
         ["The tablet holds an encrypted roster bound",
          "to that device, keeps admitting people when",
          "the network drops, and syncs when it is back."]),
        ("~0.35 seconds",
         ["Measured on ordinary tablet hardware. Not a",
          "lab number, and not contingent on a signal",
          "reaching the door."]),
        ("Nothing installed on site",
         ["No server rack, no cabling, no integration",
          "with the venue. Keys live on the device and",
          "are wiped when the event ends."]),
    ])
    footnote(s, "Up in an hour on a trestle table. Down on the final night, back into "
                "the same flight case.", FOOT_Y)
    return s


# -------------------------------------------------------------- 08 the promise
def s08(prs):
    s = blank(prs)
    chrome(s, "THE ONE RULE THAT GOVERNS EVERYTHING", "08", FOOT)

    shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, M, 1.95, CONTENT_W, 3.55, fill=TINT, adj=0.04)
    txt(s, 1.10, 2.35, 6.00, 0.34, "THE PROMISE", 11.5, DEEP, MONO, spc=1.8)
    txt(s, 1.10, 2.85, 17.00, 0.90, "We never keep the photograph.", 46, DEEP, LIGHT,
        ls=1.06)
    txt(s, 1.10, 4.20, 16.00, 1.00,
        ["The image becomes an encrypted key on the tablet and is destroyed in the "
         "same second.",
         "It is never written to disk, never uploaded, and never leaves the venue."],
        17, DEEP, SANS, ls=1.36)

    trio(s, [
        ("Consent is a record",
         ["Who agreed, to what purpose, and when —",
          "with a withdrawal that erases the credential",
          "and issues a certificate saying so."]),
        ("It expires with the event",
         ["No dormant database of faces sitting on a",
          "server after the weekend, waiting for the",
          "breach that makes it a news story."]),
        ("A breach yields nothing",
         ["There are no photographs to steal. Only keys,",
          "and a key cannot be turned back into a face",
          "by anybody, ourselves included."]),
    ])
    footnote(s, "Built against India's DPDP Act: a stated purpose, recorded consent, a "
                "retention limit, and erasure on request.", FOOT_Y)
    return s


# --------------------------------------------------------- 09 what comes back
def s09(prs):
    s = blank(prs)
    chrome(s, "WHAT THE DOOR HANDS BACK", "09", FOOT)
    headline(s, "Counting, not surveillance", H1)
    bar(s, M, BAR1)
    deck(s, "Because the face is destroyed at the gate, what is left is arithmetic — "
            "the numbers an operations plan and a sponsor report both need, and that a "
            "privacy-literate audience has no reason to object to.", DECK1)

    quad(s, [
        ("True unique footfall",
         ["How many individual people came,",
          "held apart from total entries,",
          "which re-entry inflates today."]),
        ("Hour by hour",
         ["Where the peak actually sat, so",
          "day two is staffed for the real",
          "curve and not last year's guess."]),
        ("Gate by gate",
         ["Which entrance carried the load",
          "and which stood idle, while you",
          "can still move people across."]),
        ("Live capacity",
         ["A running count of who is inside,",
          "for the venue, the fire officer",
          "and the local authority."]),
    ])
    footnote(s, "Counts and timings only. No movement trails, no dwell tracking, no "
                "profiles — the things that would make this audience turn on you.",
             FOOT_Y)
    return s


# ------------------------------------------------------- 10 the rest of Marwah
def s10(prs):
    s = blank(prs)
    chrome(s, "THE SAME LAYER, ELSEWHERE IN THE GROUP", "10", FOOT)
    headline(s, ["One identity layer.", "Four doors you already operate."], H1)
    bar(s, M, BAR2)
    deck(s, "Nothing here is a second product or a second contract. It is the same tablet, "
            "the same enrolment and the same rules, pointed at a different door.", DECK2)

    quad(s, [
        ("Tournament floor",
         ["Players, crew, press and talent,",
          "each with their own zone and",
          "their own hours on the pass."]),
        ("Bootcamp & team house",
         ["Who is in the house, and who let",
          "them in — answered without a",
          "register on a clipboard."]),
        ("SCORE facilities",
         ["Mumbai and Chennai. Memberships",
          "and slot bookings that stop being",
          "lent between friends."]),
        ("Football & kabaddi",
         ["Squad verification on matchday,",
          "and staff access to the areas",
          "meant to be restricted."]),
    ])
    footnote(s, "Mumbai Ultras, SCORE and the tournament IPs each have a door problem. "
                "It is the same door problem.", FOOT_Y)
    return s


# -------------------------------------------------------------------- 11 ask
def s11(prs):
    s = blank(prs)
    chrome(s, "THE ASK", "11", FOOT)
    headline(s, "One event. One lane. Beside your existing entry.", H1)
    bar(s, M, BAR1)
    deck(s, "Give us a single lane at one Marwah event, running in parallel with your "
            "normal entry. Your counters stay open the whole time, and nothing about the "
            "run-sheet changes.", DECK1)

    trio(s, [
        ("What we bring",
         ["Tablets on stands, in a flight case, and the",
          "people to run them. Set up in an hour, packed",
          "down the same night."]),
        ("What you change",
         ["Nothing. Entrants opt in when they book, and",
          "everybody else walks up to your counter",
          "exactly as they do today."]),
        ("What we measure",
         ["People per lane per hour from doors-open,",
          "side by side with your own counter, across",
          "the full weekend."]),
    ])
    footnote(s, "If we do not beat your counter on throughput, there is nothing to "
                "discuss afterwards.", FOOT_Y)
    return s


# --------------------------------------------------------------- 12 one breath
def s12(prs):
    s = blank(prs)
    chrome(s, "IN ONE BREATH", "12", FOOT)
    headline(s, ["Zero risk to the run-sheet.", "A number you can check on the night."], H1)
    bar(s, M, BAR2)
    deck(s, "One lane, at one event, and a throughput figure you can read for yourself "
            "before the weekend is over.", DECK2)

    quad(s, [
        ("Operations",
         ["One lane. Your counters and",
          "your staffing stay exactly",
          "as they are today."]),
        ("Revenue",
         ["Passes that cannot be lent,",
          "a shorter queue, and a crowd",
          "inside the hall spending."]),
        ("Accountability",
         ["Every entry attached to a person,",
          "so a dispute has a record",
          "instead of an argument."]),
        ("Privacy",
         ["No photograph kept, no database",
          "left behind, and an erasure",
          "certificate on request."]),
    ])
    footnote(s, "All we need is one lane at one event, and somebody of yours at the "
                "door on the Saturday morning.", FOOT_Y)
    return s


# s03 (player integrity) is parked, not deleted - Marwah's esports arm is a
# roster rather than a prize-pool tournament operator, so the argument does not
# land. Re-add s03 to this list to restore it; numerals follow position.
BUILDERS = [s01, s02, s04, s05, s06, s07, s08, s09, s10, s11, s12]


def build(out):
    prs = new_deck()
    for b in BUILDERS:
        b(prs)
    renumber(prs)          # corner numerals follow position, not the builder name
    prs.save(out)
    return len(prs.slides._sldIdLst)


if __name__ == "__main__":
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "BioCore_for_Marwah_Sports.pptx")
    print("marwah deck :", build(out), "slides ->", out)
