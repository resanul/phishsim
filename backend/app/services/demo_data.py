from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import EmailTemplate, LandingPage, SenderProfile
from app.models.identity import Administrator
from app.models.recipients import Recipient
from app.security.crypto import encrypt_secret
from app.security.passwords import hash_password
from app.services.auth_service import get_or_create_role

BUILTIN_SCENARIOS = [
    {
        "name": "Password Reset Awareness",
        "scenario": "password_reset",
        "subject": "[DEMO] Action Required: Reset your password",
        "html_body": (
            "<p>Hi {{first_name}},</p>"
            "<p>Our records show your password for {{company}} is about to expire. "
            "Please <a href='{{simulation_link}}'>click here to reset your password</a> before it expires.</p>"
            "<p>IT Support Team</p>"
        ),
    },
    {
        "name": "Account Security Notification",
        "scenario": "account_security",
        "subject": "[DEMO] Unusual sign-in activity detected on your account",
        "html_body": (
            "<p>Hello {{first_name}},</p>"
            "<p>We noticed a sign-in to your {{company}} account from an unrecognized device. "
            "<a href='{{simulation_link}}'>Review this activity</a> if this wasn't you.</p>"
        ),
    },
    {
        "name": "IT Support Notification",
        "scenario": "it_support",
        "subject": "[DEMO] IT Support: Mailbox storage almost full",
        "html_body": (
            "<p>Hi {{first_name}},</p>"
            "<p>Your mailbox is at 95% capacity. <a href='{{simulation_link}}'>Increase your storage</a> "
            "to avoid missing new messages.</p>"
        ),
    },
    {
        "name": "Software Update Notification",
        "scenario": "software_update",
        "subject": "[DEMO] Critical update required for your workstation",
        "html_body": (
            "<p>Hello {{first_name}},</p>"
            "<p>A critical security update is pending for your device. "
            "<a href='{{simulation_link}}'>Install the update now</a>.</p>"
        ),
    },
    {
        "name": "HR Notification",
        "scenario": "hr_notification",
        "subject": "[DEMO] Updated {{company}} benefits enrollment deadline",
        "html_body": (
            "<p>Hi {{first_name}},</p>"
            "<p>HR has an important update about your benefits enrollment. "
            "<a href='{{simulation_link}}'>Review the changes</a> before the deadline.</p>"
        ),
    },
    {
        "name": "Document Sharing Notification",
        "scenario": "document_sharing",
        "subject": "[DEMO] A document has been shared with you",
        "html_body": (
            "<p>Hi {{first_name}},</p>"
            "<p>A colleague in {{department}} shared a document with you. "
            "<a href='{{simulation_link}}'>View document</a>.</p>"
        ),
    },
    {
        "name": "Invoice Awareness",
        "scenario": "invoice",
        "subject": "[DEMO] Invoice #48213 is ready for review",
        "html_body": (
            "<p>Hello {{first_name}},</p>"
            "<p>An invoice requires your approval. <a href='{{simulation_link}}'>Review invoice</a>.</p>"
        ),
    },
    {
        "name": "Delivery Notification",
        "scenario": "delivery_notification",
        "subject": "[DEMO] Your package delivery requires attention",
        "html_body": (
            "<p>Hi {{first_name}},</p>"
            "<p>We were unable to deliver your package. <a href='{{simulation_link}}'>Reschedule delivery</a>.</p>"
        ),
    },
    {
        "name": "Executive Impersonation Awareness",
        "scenario": "executive_impersonation",
        "subject": "[DEMO] Quick request",
        "html_body": (
            "<p>{{first_name}},</p>"
            "<p>Are you available right now? I need you to handle something urgent. "
            "<a href='{{simulation_link}}'>Reply here</a>.</p><p>Sent from my mobile.</p>"
        ),
    },
    {
        "name": "Cloud Storage Notification",
        "scenario": "cloud_storage",
        "subject": "[DEMO] Your cloud storage is almost full",
        "html_body": (
            "<p>Hi {{first_name}},</p>"
            "<p>Your organization's cloud storage is nearly full. "
            "<a href='{{simulation_link}}'>Manage storage</a>.</p>"
        ),
    },
    {
        "name": "Social Engineering Awareness",
        "scenario": "social_engineering",
        "subject": "[DEMO] Please confirm your details for the {{department}} directory",
        "html_body": (
            "<p>Hi {{first_name}},</p>"
            "<p>We're updating the {{department}} staff directory. "
            "<a href='{{simulation_link}}'>Confirm your details</a>.</p>"
        ),
    },
]

DEMO_LANDING_PAGE_HTML = """
<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>Simulation Complete</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 640px; margin: 40px auto; padding: 0 20px; color: #1e293b; }
  .banner { background: #fef3c7; border: 1px solid #f59e0b; padding: 16px; border-radius: 8px; margin-bottom: 24px; }
  .flags { background: #f1f5f9; padding: 16px; border-radius: 8px; }
  h1 { color: #b45309; }
</style></head>
<body>
  <div class="banner"><strong>This was a simulated phishing test.</strong> No real data was collected. This exercise is part of {{company}}'s security awareness program.</div>
  <h1>You clicked a simulated phishing link</h1>
  <p>Hi {{first_name}}, if this had been a real phishing email, clicking this link could have exposed you or {{company}} to risk.</p>
  <div class="flags">
    <h3>What should you have checked?</h3>
    <ul>
      <li>Was the sender's address exactly correct?</li>
      <li>Did the message create urgency or pressure you to act quickly?</li>
      <li>Did the link's destination match what was displayed?</li>
      <li>Were there spelling or formatting inconsistencies?</li>
    </ul>
  </div>
  <p>If you see a real suspicious email, use the "Report Phishing" button in your mail client, or contact IT Security.</p>
</body></html>
"""


def seed_demo_data(db: Session) -> dict:
    created = {"admins": 0, "sender_profiles": 0, "templates": 0, "landing_pages": 0, "recipients": 0}

    role = get_or_create_role(db, "security_administrator")
    if db.execute(select(Administrator).where(Administrator.email == "demo-admin@example.org")).scalar_one_or_none() is None:
        admin = Administrator(
            email="demo-admin@example.org",
            full_name="Demo Security Administrator",
            hashed_password=hash_password("Demo!Passw0rd123"),
            role_id=role.id,
            is_super_admin=False,
        )
        db.add(admin)
        created["admins"] += 1

    if db.execute(select(SenderProfile).where(SenderProfile.name == "Demo IT Security")).scalar_one_or_none() is None:
        db.add(
            SenderProfile(
                name="Demo IT Security",
                from_name="IT Security (Simulation)",
                from_email="security-awareness@example.org",
                reply_to="",
                smtp_host="localhost",
                smtp_port=1025,
                smtp_use_tls=False,
                smtp_username="",
                smtp_password_encrypted="",
            )
        )
        created["sender_profiles"] += 1

    if db.execute(select(LandingPage).where(LandingPage.name == "Demo Awareness Landing Page")).scalar_one_or_none() is None:
        db.add(
            LandingPage(
                name="Demo Awareness Landing Page",
                html_body=DEMO_LANDING_PAGE_HTML,
                has_synthetic_form=False,
                show_education_reveal=True,
            )
        )
        created["landing_pages"] += 1

    for scenario in BUILTIN_SCENARIOS:
        if db.execute(select(EmailTemplate).where(EmailTemplate.name == scenario["name"])).scalar_one_or_none() is None:
            db.add(
                EmailTemplate(
                    name=scenario["name"],
                    scenario=scenario["scenario"],
                    subject=scenario["subject"],
                    from_name="IT Security (Simulation)",
                    html_body=scenario["html_body"],
                    text_body="",
                    is_builtin=True,
                )
            )
            created["templates"] += 1

    demo_recipients = [
        ("Ava", "Chen", "ava.chen@example.org", "Engineering", "Software Engineer"),
        ("Liam", "Patel", "liam.patel@example.org", "Finance", "Accountant"),
        ("Noah", "Garcia", "noah.garcia@example.org", "Sales", "Account Executive"),
        ("Mia", "Nguyen", "mia.nguyen@example.org", "HR", "HR Generalist"),
        ("Ethan", "Kowalski", "ethan.kowalski@example.org", "Engineering", "QA Engineer"),
    ]
    for first, last, email, dept, title in demo_recipients:
        if db.execute(select(Recipient).where(Recipient.email == email)).scalar_one_or_none() is None:
            db.add(
                Recipient(
                    first_name=first,
                    last_name=last,
                    email=email,
                    department=dept,
                    job_title=title,
                    is_test_address=True,
                    custom_attributes={"demo": True},
                )
            )
            created["recipients"] += 1

    db.commit()
    return created
