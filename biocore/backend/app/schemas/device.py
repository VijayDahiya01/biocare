from pydantic import BaseModel


class CreateDeviceRequest(BaseModel):
    name: str
    zone_id: str | None = None
    capture_method: str = "webcam"  # webcam | rtsp


class FaceSearchRequest(BaseModel):
    image: str                 # base64 / data URL frame from the kiosk
    action: str = "auto"       # auto = toggle in/out; or "in" / "out"
