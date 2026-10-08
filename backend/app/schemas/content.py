from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class SenderProfileCreate(BaseModel):
    name: str
    from_name: str
    from_email: EmailStr
    reply_to: str = ""
    smtp_host: str
    smtp_port: int = 587
    smtp_use_tls: bool = True
    smtp_username: str = ""
    smtp_password: str = ""  # write-only; encrypted at rest, never returned


class SenderProfileOut(BaseModel):
    id: str
    name: str
    from_name: str
    from_email: EmailStr
    reply_to: str
    smtp_host: str
    smtp_port: int
    smtp_use_tls: bool
    is_active: bool

    class Config:
        from_attributes = True


class TemplateCreate(BaseModel):
    name: str
    scenario: str = "custom"
    subject: str
    from_name: str = ""
    reply_to: str = ""
    html_body: str
    text_body: str = ""


class TemplateOut(BaseModel):
    id: str
    name: str
    scenario: str
    subject: str
    html_body: str
    text_body: str
    is_builtin: bool
    is_active: bool

    class Config:
        from_attributes = True


class TemplateValidationResult(BaseModel):
    is_valid: bool
    broken_links: list[str] = Field(default_factory=list)
    unknown_variables: list[str] = Field(default_factory=list)
    html_errors: list[str] = Field(default_factory=list)


class LandingPageCreate(BaseModel):
    name: str
    html_body: str
    has_synthetic_form: bool = False
    show_education_reveal: bool = True


class LandingPageOut(BaseModel):
    id: str
    name: str
    html_body: str
    has_synthetic_form: bool
    show_education_reveal: bool
    is_active: bool

    class Config:
        from_attributes = True


class SendTestEmailRequest(BaseModel):
    template_id: str
    sender_profile_id: str
    test_addresses: list[EmailStr]
