from pydantic import BaseModel, EmailStr


class PersonOtpRequest(BaseModel):
    email: EmailStr


class PersonOtpVerify(BaseModel):
    email: EmailStr
    otp: str


class JoinByCode(BaseModel):
    org_code: str


class InviteCreate(BaseModel):
    email: EmailStr
    role: str = "self_user"


class FaceAcks(BaseModel):
    purpose_understood: bool = False
    sensitivity_understood: bool = False
    rights_understood: bool = False
    freely_given: bool = False


class PersonFaceEnroll(BaseModel):
    image: str
    acknowledgements: FaceAcks
