from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    mfa_required: bool = False
    must_change_password: bool = False


class AdminCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    role_name: str = Field(description="One of: super_admin, security_administrator, campaign_manager, analyst, read_only")


class AdminOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role_name: str
    is_active: bool
    mfa_enabled: bool

    class Config:
        from_attributes = True


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MFAVerifyRequest(BaseModel):
    code: str
