from __future__ import annotations

import asyncio
import datetime as dt
import getpass
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models.campaigns import Campaign
from app.models.content import EmailTemplate, LandingPage
from app.models.identity import Administrator
from app.security.passwords import hash_password, validate_password_policy
from app.services.audit_service import log_action
from app.services.auth_service import get_admin_by_email, get_or_create_role
from app.services.bootstrap import seed_rbac
from app.services import settings_service


def cmd_create_admin(email: str, full_name: str, role_name: str = "super_admin", password: str | None = None) -> None:
    db = SessionLocal()
    try:
        seed_rbac(db)
        if get_admin_by_email(db, email) is not None:
            print(f"An administrator with email {email} already exists.", file=sys.stderr)
            sys.exit(1)

        if password is None:
            password = getpass.getpass("Password: ")
            confirm = getpass.getpass("Confirm password: ")
            if password != confirm:
                print("Passwords do not match.", file=sys.stderr)
                sys.exit(1)

        problems = validate_password_policy(password)
        if problems:
            print("Password does not meet policy:", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            sys.exit(1)

        role = get_or_create_role(db, role_name)
        admin = Administrator(
            email=email.lower(),
            full_name=full_name,
            hashed_password=hash_password(password),
            role_id=role.id,
            is_super_admin=(role_name == "super_admin"),
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        log_action(db, actor_id=admin.id, actor_email=admin.email, action="administrator_created", object_type="administrator", object_id=admin.id, metadata={"via": "cli", "role": role_name})
        print(f"Created administrator {admin.email} with role '{role_name}' (id={admin.id}).")
    finally:
        db.close()


def cmd_seed_demo() -> None:
    from app.services.demo_data import seed_demo_data

    db = SessionLocal()
    try:
        seed_rbac(db)
        summary = seed_demo_data(db)
        print("Seeded demo data:")
        for k, v in summary.items():
            print(f"  {k}: {v}")
    finally:
        db.close()


def cmd_test_email(sender_profile_id: str, to_address: str) -> None:
    from email.message import EmailMessage

    import aiosmtplib

    from app.security.crypto import decrypt_secret
    from app.models.content import SenderProfile

    db = SessionLocal()
    try:
        sender = db.get(SenderProfile, sender_profile_id)
        if sender is None:
            print("Sender profile not found.", file=sys.stderr)
            sys.exit(1)

        message = EmailMessage()
        message["From"] = f"{sender.from_name} <{sender.from_email}>"
        message["To"] = to_address
        message["Subject"] = "PhishSim SMTP connection test"
        message.set_content("This is a test message confirming SMTP connectivity for the PhishSim platform.")

        password = decrypt_secret(sender.smtp_password_encrypted) if sender.smtp_password_encrypted else None
        asyncio.run(
            aiosmtplib.send(
                message,
                hostname=sender.smtp_host,
                port=sender.smtp_port,
                username=sender.smtp_username or None,
                password=password or None,
                start_tls=sender.smtp_use_tls,
                timeout=15,
            )
        )
        print(f"Test email sent to {to_address} via {sender.smtp_host}:{sender.smtp_port}.")
    finally:
        db.close()


def cmd_campaign_status(campaign_id: str | None = None) -> None:
    db = SessionLocal()
    try:
        query = select(Campaign)
        if campaign_id:
            query = query.where(Campaign.id == campaign_id)
        campaigns = db.execute(query).scalars().all()
        if not campaigns:
            print("No campaigns found.")
            return
        for c in campaigns:
            sent = sum(1 for t in c.targets if t.sent_at is not None)
            clicked = sum(1 for t in c.targets if t.clicked_at is not None)
            print(f"{c.id}  {c.name!r:40}  status={c.status:10}  targets={len(c.targets):5}  sent={sent:5}  clicked={clicked:5}  kill_switch={c.kill_switch_engaged}")
    finally:
        db.close()


def cmd_emergency_stop(reason: str) -> None:
    from app.models.enums import CampaignStatus

    db = SessionLocal()
    try:
        settings_service.engage_global_stop(db, reason)
        running = db.execute(select(Campaign).where(Campaign.status == CampaignStatus.RUNNING.value)).scalars().all()
        for c in running:
            c.status = CampaignStatus.PAUSED.value
            db.add(c)
        db.commit()
        log_action(db, action="global_emergency_stop_engaged", metadata={"reason": reason, "via": "cli"})
        print(f"Emergency stop engaged. Paused {len(running)} running campaign(s).")
    finally:
        db.close()


def cmd_cleanup() -> None:
    """Apply retention policy: delete campaign events older than each campaign's retention_days."""
    from app.models.campaigns import CampaignEvent

    db = SessionLocal()
    try:
        now = dt.datetime.now(dt.timezone.utc)
        campaigns = db.execute(select(Campaign)).scalars().all()
        deleted_total = 0
        for c in campaigns:
            cutoff = now - dt.timedelta(days=c.retention_days)
            old_events = [e for e in c.events if e.occurred_at < cutoff]
            for e in old_events:
                db.delete(e)
                deleted_total += 1
        db.commit()
        print(f"Cleanup complete. Deleted {deleted_total} event(s) past retention window.")
    finally:
        db.close()
