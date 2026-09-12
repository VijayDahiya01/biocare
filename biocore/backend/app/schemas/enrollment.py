from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    org_code: str
    first_name: str
    last_name: str | None = None
    email: EmailStr
    department: str | None = None
    member_id: str | None = None


class OtpRequest(BaseModel):
    email: EmailStr


class OtpVerify(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=4, max_length=8)


class ConsentAcks(BaseModel):
    purpose_understood: bool = False
    sensitivity_understood: bool = False
    rights_understood: bool = False
    freely_given: bool = False


class ConsentRequest(BaseModel):
    purpose: str = "attendance"
    method: str = "self"  # self | admin_assisted
    acknowledgements: ConsentAcks


class EnrollFaceRequest(BaseModel):
    # base64 (data URL accepted). user_id optional — defaults to the caller.
    image: str
    user_id: str | None = None
