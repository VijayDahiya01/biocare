from pydantic import BaseModel, Field


class ErasureRequest(BaseModel):
    otp: str  # re-authentication required before erasure


class GrievanceCreate(BaseModel):
    subject: str | None = None
    message: str = Field(min_length=3)


class GrievanceResolve(BaseModel):
    resolution: str = Field(min_length=1)
