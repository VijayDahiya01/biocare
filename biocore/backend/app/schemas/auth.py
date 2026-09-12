from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None  # required for admin roles


class ProvisionTenantRequest(BaseModel):
    name: str
    org_code: str = Field(min_length=2)
    vertical: str
    plan: str = "starter"
    admin_email: EmailStr
    admin_password: str = Field(min_length=8)
    admin_name: str = "Administrator"


class CreateAdminRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = "Administrator"
    role: str = "entity_admin"
