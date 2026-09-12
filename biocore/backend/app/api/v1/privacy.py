"""Consent & privacy API (BIOCORE_COMPLETE_CHANGE_SPEC §10.4).

Notices, consent withdrawal, and erasure requests. Erasure *execution* (the cascade over
vector/cache/backups, §13.4) is performed by the erasure service; this API enqueues the job
and reports status/certificate. No biometric payload is exposed.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Principal, auth_db, require_role
from app.core.envelope import ApiError, success
from app.dpdp.audit import write_audit
from app.models import ConsentNotice, ConsentReceipt, ErasureJob
from app.schemas.identity import ErasureRequest
from app.core.roles import PRIVACY, READ_STATUS
from app.services import erasure_service

router = APIRouter(prefix="/privacy", tags=["privacy"])
_ADMIN = PRIVACY


@router.get("/notices")
def notices(request: Request, principal: Principal = Depends(require_role(*READ_STATUS)),
            db: Session = Depends(auth_db)):
    rows = db.execute(select(ConsentNotice)).scalars().all()
    return success(request, {"items": [
        {"id": str(n.id), "purpose_id": n.purpose_id, "version": n.version, "language": n.language,
         "active_from": n.active_from.isoformat() if n.active_from else None} for n in rows]})


@router.post("/consents/{receipt_id}/withdraw")
def withdraw(request: Request, receipt_id: str,
             principal: Principal = Depends(require_role(*_ADMIN)),
             db: Session = Depends(auth_db)):
    r = db.get(ConsentReceipt, receipt_id)
    if not r:
        raise ApiError(404, "RECEIPT_NOT_FOUND", "Consent receipt not found.")
    r.withdrawn_at = datetime.now(timezone.utc)
    write_audit(db, action="CONSENT_WITHDRAWN", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=str(r.tenant_subject_id),
                request_id=request.state.request_id, metadata={"purpose": r.purpose_id})
    db.commit()
    return success(request, {"receipt_id": str(r.id), "withdrawn": True})


@router.post("/erasure-request")
def erasure_request(request: Request, body: ErasureRequest,
                    principal: Principal = Depends(require_role(*_ADMIN)),
                    db: Session = Depends(auth_db)):
    job = ErasureJob(tenant_id=principal.tenant_id, tenant_subject_id=body.tenant_subject_id,
                     scope=body.scope, status="pending")
    db.add(job)
    db.flush()
    # execute the cascade now (zeroize credentials + record proof); async worker in production
    erasure_service.run_job(db, job=job)
    write_audit(db, action="ERASURE_EXECUTED", actor_id=principal.user_id,
                tenant_id=principal.tenant_id, target_id=str(body.tenant_subject_id),
                request_id=request.state.request_id,
                metadata={"scope": body.scope, "job": str(job.id), "certificate": job.certificate_id})
    db.commit()
    return success(request, {"erasure_job_id": str(job.id), "status": job.status,
                             "certificate_id": job.certificate_id}, status_code=201)


@router.get("/erasure/{job_id}/status")
def erasure_status(request: Request, job_id: str,
                   principal: Principal = Depends(require_role(*READ_STATUS)),
                   db: Session = Depends(auth_db)):
    job = db.get(ErasureJob, job_id)
    if not job:
        raise ApiError(404, "JOB_NOT_FOUND", "Erasure job not found.")
    return success(request, {"erasure_job_id": str(job.id), "status": job.status, "scope": job.scope,
                             "certificate_id": job.certificate_id,
                             "completed_at": job.completed_at.isoformat() if job.completed_at else None})


@router.get("/erasure/{job_id}/certificate")
def erasure_certificate(request: Request, job_id: str,
                        principal: Principal = Depends(require_role(*READ_STATUS)),
                        db: Session = Depends(auth_db)):
    job = db.get(ErasureJob, job_id)
    if not job:
        raise ApiError(404, "JOB_NOT_FOUND", "Erasure job not found.")
    if job.status != "completed":
        raise ApiError(409, "NOT_COMPLETED", "Erasure not completed yet.")
    # a verifiable proof of erasure — metadata only, no biometric data (§13.4)
    return success(request, {
        "certificate_id": job.certificate_id, "tenant_subject_id": str(job.tenant_subject_id),
        "scope": job.scope, "status": job.status,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "statement": "All encrypted face credentials for this subject were zeroized and the "
                     "subject marked erased. No biometric data remains; only audit metadata is kept.",
    })


@router.get("/erasure")
def list_erasure(request: Request, principal: Principal = Depends(require_role(*READ_STATUS)),
                 db: Session = Depends(auth_db)):
    rows = db.execute(select(ErasureJob).order_by(ErasureJob.created_at.desc()).limit(100)).scalars().all()
    items = [{
        "id": str(j.id), "tenant_subject_id": str(j.tenant_subject_id), "scope": j.scope, "status": j.status,
        "certificate_id": j.certificate_id,
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "completed_at": j.completed_at.isoformat() if j.completed_at else None,
    } for j in rows]
    return success(request, {"items": items})
