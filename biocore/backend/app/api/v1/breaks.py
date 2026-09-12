"""Break events (API Reference §4.3). Device-authenticated, like the kiosk."""
from fastapi import APIRouter, Depends, Request

from app.api.deps import DeviceContext, device_db
from app.core.envelope import success
from app.dpdp.audit import write_audit
from app.schemas.modules import BreakRequest
from app.services.kiosk_service import process_break

router = APIRouter(tags=["attendance"])


@router.post("/attendance/break")
def attendance_break(request: Request, body: BreakRequest,
                     device: DeviceContext = Depends(device_db)):
    rid = request.state.request_id
    result = process_break(device.db, device=device, image_b64=body.image,
                           break_type=body.break_type, request_id=rid)
    write_audit(device.db, action="BREAK_RECORDED", actor_id=device.device_id,
                tenant_id=device.tenant_id, target_id=result.get("user_id"),
                request_id=rid, metadata={"event": result.get("event")})
    device.db.commit()
    return success(request, result)
