from __future__ import annotations

import asyncio

import bleach
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.database import get_db
from app.models.content import EmailTemplate, LandingPage, SenderProfile
from app.models.enums import Permission
from app.models.identity import Administrator
from app.schemas.content import (
    LandingPageCreate,
    LandingPageOut,
    SendTestEmailRequest,
    SenderProfileCreate,
    SenderProfileOut,
    TemplateCreate,
    TemplateOut,
    TemplateValidationResult,
)
from app.security.crypto import encrypt_secret
from app.services.audit_service import log_action
from app.services.content_service import validate_template

router = APIRouter(prefix="/api", tags=["content"])

ALLOWED_HTML_TAGS = bleach.sanitizer.ALLOWED_TAGS | {
    "p", "div", "span", "table", "tr", "td", "th", "thead", "tbody", "img", "h1", "h2", "h3",
    "h4", "br", "hr", "style", "a", "ul", "li", "ol", "b", "strong", "i", "em", "u",
}
ALLOWED_HTML_ATTRS = {
    "*": ["class", "style", "id"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "width", "height"],
}


def sanitize_html(html: str) -> str:
    return bleach.clean(html, tags=ALLOWED_HTML_TAGS, attributes=ALLOWED_HTML_ATTRS, strip=False)


# ---------------- Sender Profiles ----------------


@router.get("/sender-profiles", response_model=list[SenderProfileOut])
def list_sender_profiles(db: Session = Depends(get_db), _=Depends(require_permission(Permission.SETTINGS_MANAGE))):
    return db.execute(select(SenderProfile)).scalars().all()


@router.post("/sender-profiles", response_model=SenderProfileOut, status_code=status.HTTP_201_CREATED)
def create_sender_profile(
    payload: SenderProfileCreate,
    db: Session = Depends(get_db),
    actor: Administrator = Depends(require_permission(Permission.SETTINGS_MANAGE)),
):
    profile = SenderProfile(
        name=payload.name,
        from_name=payload.from_name,
        from_email=payload.from_email,
        reply_to=payload.reply_to,
        smtp_host=payload.smtp_host,
        smtp_port=payload.smtp_port,
        smtp_use_tls=payload.smtp_use_tls,
        smtp_username=payload.smtp_username,
        smtp_password_encrypted=encrypt_secret(payload.smtp_password) if payload.smtp_password else "",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    log_action(db, actor_id=actor.id, actor_email=actor.email, action="sender_profile_created", object_type="sender_profile", object_id=profile.id)
    return profile


# ---------------- Templates ----------------


@router.get("/templates", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db), _=Depends(require_permission(Permission.TEMPLATE_MANAGE))):
    return db.execute(select(EmailTemplate)).scalars().all()


@router.post("/templates/validate", response_model=TemplateValidationResult)
def validate_template_endpoint(
    payload: TemplateCreate,
    _=Depends(require_permission(Permission.TEMPLATE_MANAGE)),
):
    return validate_template(payload.subject, payload.html_body, payload.text_body)


@router.post("/templates", response_model=TemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(
    payload: TemplateCreate,
    db: Session = Depends(get_db),
    actor: Administrator = Depends(require_permission(Permission.TEMPLATE_MANAGE)),
):
    validation = validate_template(payload.subject, payload.html_body, payload.text_body)
    if not validation.is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=validation.model_dump())

    template = EmailTemplate(
        name=payload.name,
        scenario=payload.scenario,
        subject=payload.subject,
        from_name=payload.from_name,
        reply_to=payload.reply_to,
        html_body=sanitize_html(payload.html_body),
        text_body=payload.text_body,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    log_action(db, actor_id=actor.id, actor_email=actor.email, action="template_created", object_type="email_template", object_id=template.id)
    return template


@router.post("/templates/send-test")
async def send_test_email(
    payload: SendTestEmailRequest,
    db: Session = Depends(get_db),
    actor: Administrator = Depends(require_permission(Permission.TEMPLATE_MANAGE)),
):
    from app.services.sending_service import _send_via_smtp
    from app.services.content_service import render_variables

    template = db.get(EmailTemplate, payload.template_id)
    sender = db.get(SenderProfile, payload.sender_profile_id)
    if template is None or sender is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template or sender profile not found.")

    class _FakeCampaign:
        pass

    fake_campaign = _FakeCampaign()
    fake_campaign.sender_profile = sender

    variables = {
        "first_name": "Test",
        "last_name": "User",
        "department": "IT",
        "job_title": "Employee",
        "company": "Your Organization",
        "campaign_name": "Test Send",
        "simulation_link": "https://example.org/simulation/test/test-token",
    }
    subject = render_variables(template.subject, variables)
    html_body = render_variables(template.html_body, variables)
    text_body = render_variables(template.text_body, variables) if template.text_body else ""

    errors = []
    for address in payload.test_addresses:
        try:
            await _send_via_smtp(fake_campaign, address, subject, html_body, text_body)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{address}: {exc}")

    log_action(db, actor_id=actor.id, actor_email=actor.email, action="test_email_sent", object_type="email_template", object_id=template.id, metadata={"addresses": payload.test_addresses, "errors": errors})
    if errors:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={"sent": len(payload.test_addresses) - len(errors), "errors": errors})
    return {"sent": len(payload.test_addresses)}


# ---------------- Landing Pages ----------------


@router.get("/landing-pages", response_model=list[LandingPageOut])
def list_landing_pages(db: Session = Depends(get_db), _=Depends(require_permission(Permission.TEMPLATE_MANAGE))):
    return db.execute(select(LandingPage)).scalars().all()


@router.post("/landing-pages", response_model=LandingPageOut, status_code=status.HTTP_201_CREATED)
def create_landing_page(
    payload: LandingPageCreate,
    db: Session = Depends(get_db),
    actor: Administrator = Depends(require_permission(Permission.TEMPLATE_MANAGE)),
):
    page = LandingPage(
        name=payload.name,
        html_body=sanitize_html(payload.html_body),
        has_synthetic_form=payload.has_synthetic_form,
        show_education_reveal=payload.show_education_reveal,
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    log_action(db, actor_id=actor.id, actor_email=actor.email, action="landing_page_created", object_type="landing_page", object_id=page.id)
    return page
