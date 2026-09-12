"""Verified-identity erasure execution (BIOCORE_COMPLETE_CHANGE_SPEC §13.4).

Executes an erasure job: zeroizes the subject's encrypted face credentials (via the vault,
which records the key events), marks the subject erased, and issues an erasure certificate.
Only metadata + audit proof remain — no biometric data survives (§13.4, §29.14).
"""
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ErasureJob, FaceCredential, TenantSubject
from app.services import credential_vault


def run_job(db: Session, *, job: ErasureJob) -> ErasureJob:
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    creds = db.execute(
        select(FaceCredential).where(
            FaceCredential.tenant_subject_id == job.tenant_subject_id,
            FaceCredential.status != "erased",
        )
    ).scalars().all()
    for c in creds:
        credential_vault.erase_credential(db, credential=c)  # zeroizes ciphertext + DEK + key event
    if job.scope in ("subject", "tenant"):
        subj = db.get(TenantSubject, job.tenant_subject_id)
        if subj:
            subj.status = "erased"
            subj.verification_status = "erased"
            subj.authorization_status = "revoked"
    job.certificate_id = f"ERZ-{datetime.now(timezone.utc).year}-{secrets.randbelow(1000000):06d}"
    job.status = "completed"
    job.completed_at = datetime.now(timezone.utc)
    return job
