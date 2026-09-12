"""Donations + 80G receipts (API Reference §14.4)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, get_db_for, get_principal, require_role
from app.core.envelope import ApiError, success
from app.dpdp.audit import write_audit
from app.models import Donation, User
from app.schemas.modules import DonationCreate
from app.services import documents, pdf_service

router = APIRouter(prefix="/donations", tags=["donations"])
_ADMIN = ("entity_admin", "manager", "super_admin")


def _scoped_db(principal: Principal = Depends(get_principal)) -> Session:
    yield from get_db_for(principal)


@router.post("")
def record_donation(request: Request, body: DonationCreate,
                    principal: Principal = Depends(require_role(*_ADMIN)),
                    db: Session = Depends(auth_db)):
    donor = db.get(User, body.donor_user_id)
    if not donor:
        raise ApiError(404, "DONOR_NOT_FOUND", "Donor not found in this tenant.")
    d = Donation(tenant_id=principal.tenant_id, donor_user_id=body.donor_user_id,
                 amount=body.amount, purpose=body.purpose, payment_ref=body.payment_ref)
    db.add(d)
    db.flush()
    # generate the 80G receipt PDF and store it (capability-token URL)
    pdf = pdf_service.donation_receipt(
        donation_id=str(d.id),
        donor_name=f"{donor.first_name} {donor.last_name or ''}".strip(),
        amount=float(d.amount), purpose=d.purpose or "General",
        when=datetime.now(timezone.utc),
    )
    d.receipt_url = documents.save("receipts", pdf)
    write_audit(db, action="DONATION_RECORDED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=str(d.id),
                request_id=request.state.request_id)
    db.commit()
    return success(request, {"donation_id": str(d.id), "receipt_url": d.receipt_url}, status_code=201)


@router.get("/{donor_id}")
def donor_history(request: Request, donor_id: str,
                  principal: Principal = Depends(get_principal),
                  db: Session = Depends(_scoped_db)):
    rows = db.execute(
        select(Donation).where(Donation.donor_user_id == donor_id)
        .order_by(Donation.created_at.desc())
    ).scalars().all()
    items = [{"donation_id": str(d.id), "amount": float(d.amount), "purpose": d.purpose,
              "receipt_url": d.receipt_url, "at": d.created_at.isoformat()} for d in rows]
    return success(request, {"items": items})
