from pydantic import BaseModel, Field


class ZoneCreate(BaseModel):
    name: str
    type: str = Field(pattern="^(entry_exit|restricted|amenity)$")
    access_rule: dict = Field(default_factory=dict)  # {allowed_badges:[], time_windows:[]}
    door_webhook_url: str | None = None


class BadgeCreate(BaseModel):
    name: str
    zones: list[str] = Field(default_factory=list)
    time_rule: str = Field(default="always", pattern="^(always|window)$")
    time_windows: list[dict] = Field(default_factory=list)
    expiry: str | None = None  # ISO date
    print_badge: bool = False


class AssignBadge(BaseModel):
    user_id: str
    badge_id: str


class BlacklistAdd(BaseModel):
    image: str           # base64 face to add to the blacklist collection
    reason: str | None = None


class WebhookCreate(BaseModel):
    event: str
    url: str
    secret: str


class AlertSettings(BaseModel):
    late_threshold: str | None = None
    channels: dict | None = None
    whatsapp_enabled: bool | None = None


class AdminEnrollRequest(BaseModel):
    person_type: str = Field(pattern="^(patient|inmate|citizen|devotee|visitor|guardian)$")
    first_name: str
    last_name: str | None = None
    reference_id: str | None = None
    purpose: str
    image: str
    consent_method: str = "in_person_verbal"
    expiry_date: str | None = None
    extra: dict = Field(default_factory=dict)
    # the four admin confirmations (A7)
    person_present: bool = False
    purpose_explained: bool = False
    person_consented: bool = False
    admin_responsible: bool = False


class VisitorInviteRequest(BaseModel):
    visitor_name: str | None = None
    host_user_id: str | None = None
    valid_hours: int = 4


class VisitorEnrollRequest(BaseModel):
    token: str
    name: str
    phone: str | None = None
    image: str
