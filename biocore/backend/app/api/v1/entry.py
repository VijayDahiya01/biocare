"""Entry API (BIOCORE_COMPLETE_CHANGE_SPEC §10.3, §7).

Terminal-authenticated (device token). `POST /entry/match` is the combined transactional
decision (capture → 1:1 match → authorize → record); the rest support the flow and manual
fallback. A face match NEVER auto-grants entry — the authorization plane decides (§29.11).
Only minimal entry events are recorded; no biometric payload is stored or returned (§7.5).
"""
import uuid

from fastapi import APIRouter, Depends, Request

from app.api.deps import DeviceContext, device_db
from app.core import metrics
from app.core.config import settings
from app.core.envelope import ApiError, success
from app.core.policy import EntryReason
from app.dpdp.audit import write_audit
from app.models import Device, TenantSubject, Zone
from app.schemas.entry import (
    AuthorizeRequest,
    CommitRequest,
    IdentifyRequest,
    ManualOverride,
    ManualReview,
    MatchRequest,
    RequestContext,
    ResolveClaim,
)
from sqlalchemy import select
from app.services import authorization, device_trust, entry_service, hardware_bridge, request_context
from app.services.request_context import TrustedContextError

router = APIRouter(prefix="/entry", tags=["entry"])


def _enforce_trust(ctx: DeviceContext, context: RequestContext | None) -> str:
    """Enforce §12.3 hardening posture + §12.4 signed request context. Returns the policy
    version to record on the entry event. Raises 403 DEVICE_NOT_TRUSTED on any failure."""
    # §12.3 — require an attested, compliant hardening posture on production terminals
    if settings.require_hardened_terminal:
        device = ctx.db.get(Device, ctx.device_id)
        if not device_trust.posture_ok(device):
            metrics.incr("device_trust.failure")
            raise ApiError(403, "DEVICE_NOT_TRUSTED",
                           "Terminal has not attested a compliant hardening posture.")
    # §12.4 — signed request context
    if context is None:
        if settings.require_signed_context:
            metrics.incr("device_trust.failure")
            raise ApiError(403, "DEVICE_NOT_TRUSTED", "A signed request context is required.")
        return settings.current_policy_version
    try:
        request_context.verify(ctx.db, device_ctx=ctx, ctx=context.model_dump(), secret=ctx.token or "")
    except TrustedContextError as e:
        metrics.incr("device_trust.failure")  # §23 device trust failures / alert
        raise ApiError(403, "DEVICE_NOT_TRUSTED", str(e))
    return context.policy_version


@router.post("/resolve-claim")
def resolve_claim(request: Request, body: ResolveClaim, ctx: DeviceContext = Depends(device_db)):
    subj = entry_service.resolve_claim(ctx.db, claim=body.claim)
    if not subj:
        return success(request, {"resolved": False})
    cred = entry_service.active_credential(ctx.db, subj.id)
    return success(request, {"resolved": True, "subject_id": str(subj.id),
                             "name": subj.display_name or subj.external_reference,
                             "has_credential": cred is not None,
                             "verification_status": subj.verification_status})


@router.post("/capture-session")
def capture_session(request: Request, ctx: DeviceContext = Depends(device_db)):
    # a short-lived capture handle for the terminal (frames are never persisted, §7.5)
    return success(request, {"capture_id": str(uuid.uuid4()), "device_id": ctx.device_id})


@router.get("/gates")
def gates(request: Request, ctx: DeviceContext = Depends(device_db)):
    """The site's gates (zones) for the guard to pick where they're standing."""
    rows = ctx.db.execute(select(Zone).order_by(Zone.name)).scalars().all()
    return success(request, {"items": [{"id": str(z.id), "name": z.name} for z in rows],
                             "device_zone_id": ctx.zone_id})


@router.post("/identify")
def identify(request: Request, body: IdentifyRequest, ctx: DeviceContext = Depends(device_db)):
    """Walk-up check-in/out: capture a face → recognise who it is (1:N) → allow/deny + record."""
    direction = "out" if body.direction == "out" else "in"
    result = entry_service.identify_face(
        ctx.db, tenant_id=ctx.tenant_id, device_id=ctx.device_id,
        zone_id=(body.gate_id or ctx.zone_id), image=body.image, direction=direction)
    write_audit(ctx.db, action="ENTRY_IDENTIFY", tenant_id=ctx.tenant_id,
                target_id=result.get("subject_id"), request_id=request.state.request_id,
                metadata={"decision": result["decision"], "reason": result["reason"],
                          "direction": direction, "device": ctx.device_id})
    ctx.db.commit()
    return success(request, result)


@router.post("/match")
def match(request: Request, body: MatchRequest, ctx: DeviceContext = Depends(device_db)):
    policy_version = _enforce_trust(ctx, body.context)  # §12.3/§12.4 — trusted device + context
    result = entry_service.run_entry(ctx.db, tenant_id=ctx.tenant_id, device_id=ctx.device_id,
                                     zone_id=ctx.zone_id, subject_id=body.subject_id, image=body.image,
                                     policy_version=policy_version)
    write_audit(ctx.db, action="ENTRY_DECISION", tenant_id=ctx.tenant_id, target_id=body.subject_id,
                request_id=request.state.request_id,
                metadata={"decision": result["decision"], "reason": result["reason"], "device": ctx.device_id})
    ctx.db.commit()
    if settings.hardware_bridge_enabled:  # §19.3 — signed allow/deny command, no template
        result["hardware_command"] = hardware_bridge.build_command(
            device_ctx=ctx, decision=result["decision"], reason=result["reason"])
    return success(request, result)


@router.post("/authorize")
def authorize_entry(request: Request, body: AuthorizeRequest, ctx: DeviceContext = Depends(device_db)):
    # policy-only dry run (no biometric) — assumes identity already proven elsewhere
    subj = ctx.db.get(TenantSubject, body.subject_id)
    cred = entry_service.active_credential(ctx.db, body.subject_id) if subj else None
    consent = entry_service.consent_active(ctx.db, body.subject_id) if subj else False
    reason = authorization.evaluate(face_match_passed=True, liveness_passed=True, subject=subj,
                                    credential=cred, consent_active=consent)
    return success(request, {"allowed": reason == EntryReason.ALLOWED, "reason": reason.value})


@router.post("/commit")
def commit(request: Request, body: CommitRequest, ctx: DeviceContext = Depends(device_db)):
    entry_service.record_attempt(ctx.db, tenant_id=ctx.tenant_id, device_id=ctx.device_id,
                                 zone_id=ctx.zone_id, subject_id=body.subject_id,
                                 reason=body.reason, authorization_result=body.decision)
    write_audit(ctx.db, action="ENTRY_COMMIT", tenant_id=ctx.tenant_id, target_id=body.subject_id,
                request_id=request.state.request_id, metadata={"decision": body.decision, "reason": body.reason})
    ctx.db.commit()
    return success(request, {"committed": True}, status_code=201)


@router.post("/manual-review")
def manual_review(request: Request, body: ManualReview, ctx: DeviceContext = Depends(device_db)):
    entry_service.record_attempt(ctx.db, tenant_id=ctx.tenant_id, device_id=ctx.device_id,
                                 zone_id=ctx.zone_id, subject_id=body.subject_id,
                                 reason="MANUAL_REVIEW", authorization_result="manual_review")
    write_audit(ctx.db, action="ENTRY_MANUAL_REVIEW", tenant_id=ctx.tenant_id, target_id=body.subject_id,
                request_id=request.state.request_id, metadata={"note": body.note})
    ctx.db.commit()
    return success(request, {"queued": True}, status_code=201)


@router.post("/manual-override")
def manual_override(request: Request, body: ManualOverride, ctx: DeviceContext = Depends(device_db)):
    # every override records operator + supervisor + reason in the audit trail (§7.6)
    entry_service.record_attempt(ctx.db, tenant_id=ctx.tenant_id, device_id=ctx.device_id,
                                 zone_id=ctx.zone_id, subject_id=body.subject_id,
                                 reason="MANUAL_OVERRIDE", authorization_result="override")
    write_audit(ctx.db, action="ENTRY_MANUAL_OVERRIDE", tenant_id=ctx.tenant_id, target_id=body.subject_id,
                request_id=request.state.request_id,
                metadata={"operator": body.operator, "supervisor": body.supervisor,
                          "reason": body.reason, "note": body.note})
    ctx.db.commit()
    return success(request, {"overridden": True}, status_code=201)
