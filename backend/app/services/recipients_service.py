from __future__ import annotations

import csv
import io

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recipients import Recipient
from app.schemas.recipients import CSVImportResult

REQUIRED_CSV_COLUMNS = {"first_name", "last_name", "email"}
OPTIONAL_CSV_COLUMNS = {"department", "job_title", "location", "manager"}
EXCLUDED_ACCOUNT_KEYWORDS = ("noreply", "no-reply", "postmaster", "mailer-daemon", "service-account", "svc-")


def is_probably_service_account(email: str) -> bool:
    local = email.split("@")[0].lower()
    return any(k in local for k in EXCLUDED_ACCOUNT_KEYWORDS)


def import_csv(db: Session, csv_text: str, *, default_group_id: str | None = None) -> CSVImportResult:
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        return CSVImportResult(total_rows=0, imported=0, duplicates_skipped=0, invalid_skipped=0, errors=["CSV has no header row."])

    header = {h.strip().lower() for h in reader.fieldnames}
    missing = REQUIRED_CSV_COLUMNS - header
    if missing:
        return CSVImportResult(
            total_rows=0, imported=0, duplicates_skipped=0, invalid_skipped=0,
            errors=[f"Missing required columns: {', '.join(sorted(missing))}"],
        )

    total = 0
    imported = 0
    duplicates = 0
    invalid = 0
    errors: list[str] = []

    seen_in_batch: set[str] = set()

    for i, row in enumerate(reader, start=2):  # row 1 is header
        total += 1
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        email = row.get("email", "")
        try:
            validated = validate_email(email, check_deliverability=False)
            email = validated.normalized.lower()
        except EmailNotValidError as e:
            invalid += 1
            errors.append(f"Row {i}: invalid email '{email}' ({e})")
            continue

        if not row.get("first_name") or not row.get("last_name"):
            invalid += 1
            errors.append(f"Row {i}: missing first_name/last_name")
            continue

        if email in seen_in_batch:
            duplicates += 1
            continue

        existing = db.execute(select(Recipient).where(Recipient.email == email)).scalar_one_or_none()
        if existing is not None:
            duplicates += 1
            continue

        seen_in_batch.add(email)
        recipient = Recipient(
            first_name=row["first_name"],
            last_name=row["last_name"],
            email=email,
            department=row.get("department", ""),
            job_title=row.get("job_title", ""),
            location=row.get("location", ""),
            manager=row.get("manager", ""),
            is_excluded=is_probably_service_account(email),
            exclusion_reason="auto-detected service/no-reply account" if is_probably_service_account(email) else "",
        )
        db.add(recipient)
        imported += 1

    db.commit()
    return CSVImportResult(total_rows=total, imported=imported, duplicates_skipped=duplicates, invalid_skipped=invalid, errors=errors[:100])
