from __future__ import annotations

import asyncio
import datetime as dt
import logging
import random
from email.message import EmailMessage

import aiosmtplib
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.campaigns import Campaign, CampaignTarget
from app.models.enums import CampaignEventType, CampaignStatus
from app.security.crypto import decrypt_secret
from app.security.rate_limit import is_rate_limited
from app.services.audit_service import log_action
from app.services.content_service import render_variables
from app.services.settings_service import is_globally_stopped
from app.services.tracking_service import record_event

logger = logging.getLogger("phishsim.sending")


class SendingBlockedError(Exception):
    pass


def build_simulation_link(campaign_id: str, tracking_token: str) -> str:
    return f"{settings.base_url.rstrip('/')}/simulation/{campaign_id}/{tracking_token}"


def _check_domain_allowlist(campaign: Campaign, email: str) -> bool:
    if campaign.test_mode:
        return email.lower() in {a.lower() for a in (campaign.test_addresses or [])}
    approved = {d.lower() for d in (campaign.approved_domains or [])} or set(settings.approved_recipient_domains)
    if not approved:
        # No allowlist configured anywhere == fail closed, refuse to send.
        return False
    domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
    return domain in approved


def render_email_for_target(db: Session, campaign: Campaign, target: CampaignTarget) -> tuple[str, str, str]:
    recipient = target.recipient
    variables = {
        "first_name": recipient.first_name,
        "last_name": recipient.last_name,
        "department": recipient.department,
        "job_title": recipient.job_title,
        "company": campaign.authorized_organization,
        "campaign_name": campaign.name,
        "simulation_link": build_simulation_link(campaign.id, target.tracking_token),
    }
    template = campaign.template
    subject = render_variables(template.subject, variables)
    html_body = render_variables(template.html_body, variables)
    text_body = render_variables(template.text_body, variables) if template.text_body else ""
    return subject, html_body, text_body


async def _send_via_smtp(campaign: Campaign, to_email: str, subject: str, html_body: str, text_body: str) -> None:
    sender = campaign.sender_profile
    message = EmailMessage()
    message["From"] = f"{sender.from_name} <{sender.from_email}>"
    message["To"] = to_email
    message["Subject"] = "[SIMULATED PHISHING AWARENESS TEST] " + subject if settings.is_production is False else subject
    if sender.reply_to:
        message["Reply-To"] = sender.reply_to
    if text_body:
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")
    else:
        message.set_content(html_body, subtype="html")

    password = decrypt_secret(sender.smtp_password_encrypted) if sender.smtp_password_encrypted else None
    await aiosmtplib.send(
        message,
        hostname=sender.smtp_host,
        port=sender.smtp_port,
        username=sender.smtp_username or None,
        password=password or None,
        start_tls=sender.smtp_use_tls,
        timeout=15,
    )


def send_one(db: Session, campaign: Campaign, target: CampaignTarget) -> bool:
    """Send a single simulated email for a campaign target. Returns True on success."""
    if is_globally_stopped(db) or campaign.kill_switch_engaged:
        raise SendingBlockedError("Sending is blocked by an emergency stop / kill switch.")
    if campaign.status != CampaignStatus.RUNNING.value:
        raise SendingBlockedError(f"Campaign status is '{campaign.status}', not running.")

    recipient_email = target.recipient.email
    if not _check_domain_allowlist(campaign, recipient_email):
        target.send_error = "Recipient domain not in approved allowlist; send refused."
        db.add(target)
        db.commit()
        log_action(db, action="send_refused_allowlist", object_type="campaign_target", object_id=target.id, result="failure")
        return False

    rl_key = f"campaign:{campaign.id}"
    if is_rate_limited(rl_key, max_requests=max(campaign.sending_rate_per_minute, 1), window_seconds=60):
        return False  # try again on the next scheduler tick

    subject, html_body, text_body = render_email_for_target(db, campaign, target)

    try:
        asyncio.run(_send_via_smtp(campaign, recipient_email, subject, html_body, text_body))
    except Exception as exc:  # noqa: BLE001
        target.send_error = str(exc)[:500]
        db.add(target)
        db.commit()
        logger.warning("send failed for target %s: %s", target.id, exc)
        return False

    now = dt.datetime.now(dt.timezone.utc)
    target.sent_at = now
    target.send_error = ""
    db.add(target)
    record_event(db, target, CampaignEventType.SENT, metadata={"subject": subject})
    return True


def dispatch_pending(campaign_id: str | None = None, limit: int = 200) -> int:
    """Scheduler entry point: send all due, not-yet-sent targets for running
    campaigns. Returns count of emails successfully sent this tick."""
    db = SessionLocal()
    sent_count = 0
    try:
        if is_globally_stopped(db):
            return 0

        query = select(Campaign).where(Campaign.status == CampaignStatus.RUNNING.value, Campaign.kill_switch_engaged.is_(False))
        if campaign_id:
            query = query.where(Campaign.id == campaign_id)
        campaigns = db.execute(query).scalars().all()

        now = dt.datetime.now(dt.timezone.utc)
        for campaign in campaigns:
            due_targets = [
                t
                for t in campaign.targets
                if t.sent_at is None
                and (t.scheduled_send_at is None or t.scheduled_send_at <= now)
            ][:limit]
            for target in due_targets:
                if campaign.randomize_delivery_window_minutes and target.scheduled_send_at is None:
                    jitter = random.randint(0, campaign.randomize_delivery_window_minutes)
                    target.scheduled_send_at = now + dt.timedelta(minutes=jitter)
                    db.add(target)
                    db.commit()
                    continue
                try:
                    if send_one(db, campaign, target):
                        sent_count += 1
                except SendingBlockedError:
                    break

            all_done = all(t.sent_at is not None or t.send_error for t in campaign.targets)
            if all_done and campaign.targets:
                campaign.status = CampaignStatus.COMPLETED.value
                db.add(campaign)
                db.commit()
        return sent_count
    finally:
        db.close()
