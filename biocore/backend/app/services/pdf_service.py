"""PDF builders (reportlab) for compliance documents.

Each returns PDF bytes; callers store them via documents.save() and hand back the
capability URL. Kept dependency-light (reportlab is pure-Python, no system libs).
"""
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


def _doc(title: str, lines: list[tuple[str, str]], footer: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 3 * cm

    c.setFont("Helvetica-Bold", 18)
    c.drawString(2.5 * cm, y, "BioCore")
    c.setFont("Helvetica", 11)
    c.drawRightString(w - 2.5 * cm, y, datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))
    y -= 1.2 * cm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2.5 * cm, y, title)
    y -= 0.4 * cm
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.line(2.5 * cm, y, w - 2.5 * cm, y)
    y -= 1.0 * cm

    c.setFont("Helvetica", 11)
    for label, value in lines:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(2.5 * cm, y, f"{label}:")
        c.setFont("Helvetica", 11)
        c.drawString(7.0 * cm, y, str(value))
        y -= 0.8 * cm

    c.setFont("Helvetica-Oblique", 9)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(2.5 * cm, 2.0 * cm, footer)
    c.showPage()
    c.save()
    return buf.getvalue()


def erasure_certificate(*, erasure_ref: str, stores: list[str], when: datetime) -> bytes:
    return _doc(
        "Certificate of Data Erasure",
        [("Reference", erasure_ref),
         ("Completed", when.strftime("%Y-%m-%d %H:%M UTC")),
         ("Stores cleared", ", ".join(stores)),
         ("Status", "Verified across all stores")],
        "Issued under the Digital Personal Data Protection Act, 2026. This certifies the "
        "permanent erasure of the subject's biometric data. No personal data is contained herein.",
    )


def donation_receipt(*, donation_id: str, donor_name: str, amount: float,
                     purpose: str, when: datetime) -> bytes:
    return _doc(
        "Donation Receipt (80G)",
        [("Receipt no.", donation_id),
         ("Date", when.strftime("%Y-%m-%d")),
         ("Donor", donor_name),
         ("Amount", f"INR {amount:,.2f}"),
         ("Purpose", purpose or "General")],
        "Eligible for deduction under Section 80G of the Income Tax Act, 1961. "
        "Please retain this receipt for your records.",
    )


def muster_report(*, ref: str, people: list[dict], when: datetime) -> bytes:
    lines = [("Reference", ref),
             ("Generated", when.strftime("%Y-%m-%d %H:%M UTC")),
             ("Inside count", str(len(people)))]
    # list up to ~20 names on the cover
    for i, p in enumerate(people[:20], 1):
        lines.append((f"{i}", p.get("name", "?")))
    return _doc("Emergency Muster Report", lines,
                "Snapshot of all persons recorded as inside at the time of the emergency trigger.")
