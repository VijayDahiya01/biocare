"""Admin-assisted enrollment endpoint (API Reference §3.5)."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, require_role
from app.core.envelope import success
from app.dpdp.audit import write_audit
from app.schemas.access import AdminEnrollRequest
from app.services.admin_enroll_service import admin_enroll

router = APIRouter(prefix="/admin", tags=["admin-enroll"])
_ENROLLERS = ("entity_admin", "manager", "security_reception", "super_admin")


@router.post("/enroll")
def enroll_person(request: Request, body: AdminEnrollRequest,
                  principal: Principal = Depends(require_role(*_ENROLLERS)),
                  db: Session = Depends(auth_db)):
    result = admin_enroll(
        db, tenant_id=principal.tenant_id, admin_user_id=principal.user_id,
        person_type=body.person_type, first_name=body.first_name, last_name=body.last_name,
        reference_id=body.reference_id, purpose=body.purpose, image=body.image,
        consent_method=body.consent_method, expiry_date=body.expiry_date, extra=body.extra,
        confirmations={
            "person_present": body.person_present,
            "purpose_explained": body.purpose_explained,
            "person_consented": body.person_consented,
            "admin_responsible": body.admin_responsible,
        },
    )
    write_audit(db, action="ADMIN_ENROLL", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=result["user_id"],
                request_id=request.state.request_id,
                metadata={"person_type": body.person_type, "purpose": body.purpose,
                          "consent_method": body.consent_method, "consent_ref": result["consent_ref"]})
    db.commit()
    return success(request, result, status_code=201)
