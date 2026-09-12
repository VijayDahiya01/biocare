"""Kiosk face-search endpoint (API Reference §3.4). Device-authenticated."""
from fastapi import APIRouter, Depends, Request

from app.api.deps import DeviceContext, device_db
from app.core.envelope import success
from app.dpdp.audit import write_audit
from app.schemas.device import FaceSearchRequest
from app.services.kiosk_service import process_scan

router = APIRouter(prefix="/faces", tags=["kiosk"])


@router.post("/search")
def face_search(request: Request, body: FaceSearchRequest,
                device: DeviceContext = Depends(device_db)):
    """Identify the person in the frame and record an attendance event."""
    rid = request.state.request_id
    result = process_scan(
        device.db, device=device, image_b64=body.image,
        action=body.action, request_id=rid,
    )
    # Every face search is audited (DPDP requirement), match or not.
    write_audit(
        device.db, action="FACE_SEARCH", actor_id=device.device_id,
        tenant_id=device.tenant_id, target_id=result.get("user_id"),
        request_id=rid,
        metadata={"match": result.get("match"), "score": result.get("score")},
    )
    device.db.commit()
    return success(request, result)
