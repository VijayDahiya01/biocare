from pydantic import BaseModel, Field


# --- HR / wages ---
class WageConfigRequest(BaseModel):
    user_id: str
    rate_per_hour: float
    overtime_multiplier: float = 1.5
    effective_from: str  # ISO date


class BreakRequest(BaseModel):
    image: str
    break_type: str = Field(alias="break", pattern="^(start|end)$")

    model_config = {"populate_by_name": True}


# --- leave ---
class LeaveRequestBody(BaseModel):
    type: str = Field(pattern="^(casual|sick|earned|unpaid)$")
    from_date: str = Field(alias="from")
    to_date: str = Field(alias="to")
    reason: str | None = None

    model_config = {"populate_by_name": True}


class LeaveDecision(BaseModel):
    note: str | None = None
    reason: str | None = None


# --- roles ---
class RoleCreate(BaseModel):
    name: str
    permissions: list[str] = Field(default_factory=list)
    scope: dict = Field(default_factory=dict)


class RoleUpdate(BaseModel):
    permissions: list[str] | None = None
    scope: dict | None = None


# --- GPS / geofence ---
class GpsCheckin(BaseModel):
    image: str
    latitude: float
    longitude: float


class GeofenceCreate(BaseModel):
    name: str
    center_lat: float
    center_lng: float
    radius_km: float


# --- membership ---
class MembershipCreate(BaseModel):
    user_id: str
    plan_type: str = Field(pattern="^(monthly|quarterly|annual)$")
    start_date: str
    amount_paid: float | None = None
    payment_ref: str | None = None


# --- guardian ---
class GuardianInvite(BaseModel):
    student_user_id: str
    guardian_name: str
    guardian_email: str
    relationship: str = "parent"


class PickupVerify(BaseModel):
    image: str
    student_id: str


class GuardianEnroll(BaseModel):
    token: str
    image: str


# --- timetable ---
class TimetableCreate(BaseModel):
    class_id: str
    subject: str | None = None
    teacher_user_id: str | None = None
    day_of_week: int = Field(ge=0, le=6)
    start_time: str
    end_time: str


# --- donations ---
class DonationCreate(BaseModel):
    donor_user_id: str
    amount: float
    purpose: str = "general"
    payment_ref: str | None = None


# --- reports ---
class ReportSchedule(BaseModel):
    report: str
    frequency: str = Field(pattern="^(daily|weekly|monthly)$")
    format: str = "pdf"
    recipients: list[str] = Field(default_factory=list)


# --- attendance manual correction ---
class ManualEvent(BaseModel):
    user_id: str
    event: str = Field(pattern="^(check_in|check_out)$")
    timestamp: str  # ISO datetime
    reason: str


# --- users ---
class UserUpdate(BaseModel):
    role: str | None = None
    department: str | None = None
    status: str | None = None
    member_id: str | None = None


class ZoneUpdate(BaseModel):
    name: str | None = None
    access_rule: dict | None = None
    door_webhook_url: str | None = None


# --- ERP ---
class ErpSync(BaseModel):
    kind: str = Field(pattern="^(sap|zoho|darwinbox|keka)$")
    from_date: str | None = Field(default=None, alias="from")
    to_date: str | None = Field(default=None, alias="to")

    model_config = {"populate_by_name": True}
