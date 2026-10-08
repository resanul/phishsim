from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os

from openpyxl import Workbook
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from sqlalchemy.orm import Session

from app.models.campaigns import Campaign
from app.models.reports import Report
from app.services import analytics_service

REPORTS_DIR = os.environ.get("PHISHSIM_REPORTS_DIR", "/tmp/phishsim_reports")


def _summary_payload(db: Session, campaign: Campaign | None) -> dict:
    kpis = analytics_service.dashboard_kpis(db)
    employees = analytics_service.employee_metrics(db)
    departments = analytics_service.department_metrics(db)
    payload = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "campaign": {"id": campaign.id, "name": campaign.name, "status": campaign.status} if campaign else None,
        "executive_summary": {
            "total_campaigns": kpis["total_campaigns"],
            "emails_sent": kpis["emails_sent"],
            "click_rate_pct": kpis["click_rate_pct"],
            "report_rate_pct": kpis["report_rate_pct"],
        },
        "kpis": kpis,
        "participation": employees,
        "department_analysis": departments,
        "recommendations": [
            "Provide targeted micro-training to employees who clicked without reporting.",
            "Recognize departments with high report rates as examples of good practice.",
            "Re-run this scenario in 90 days to measure improvement.",
        ],
    }
    return payload


def generate_json_report(db: Session, campaign: Campaign | None) -> bytes:
    return json.dumps(_summary_payload(db, campaign), indent=2, default=str).encode("utf-8")


def generate_csv_report(db: Session, campaign: Campaign | None) -> bytes:
    payload = _summary_payload(db, campaign)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Metric", "Value"])
    for k, v in payload["kpis"].items():
        writer.writerow([k, v])
    writer.writerow([])
    writer.writerow(["Department", "Sent", "Click Rate %", "Report Rate %"])
    for row in payload["department_analysis"]:
        writer.writerow([row["department"], row["sent"], row["click_rate_pct"], row["report_rate_pct"]])
    return buf.getvalue().encode("utf-8")


def generate_xlsx_report(db: Session, campaign: Campaign | None) -> bytes:
    payload = _summary_payload(db, campaign)
    wb = Workbook()
    ws = wb.active
    ws.title = "KPIs"
    ws.append(["Metric", "Value"])
    for k, v in payload["kpis"].items():
        ws.append([k, v])

    ws2 = wb.create_sheet("Departments")
    ws2.append(["Department", "Sent", "Click Rate %", "Report Rate %"])
    for row in payload["department_analysis"]:
        ws2.append([row["department"], row["sent"], row["click_rate_pct"], row["report_rate_pct"]])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def generate_pdf_report(db: Session, campaign: Campaign | None) -> bytes:
    payload = _summary_payload(db, campaign)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("Security Awareness Campaign Report", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Generated: {payload['generated_at']}", styles["Normal"]),
    ]
    if payload["campaign"]:
        elements.append(Paragraph(f"Campaign: {payload['campaign']['name']} ({payload['campaign']['status']})", styles["Normal"]))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Executive Summary", styles["Heading2"]))

    kpi_rows = [["Metric", "Value"]] + [[k, str(v)] for k, v in payload["kpis"].items()]
    table = Table(kpi_rows, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 16))
    elements.append(Paragraph("Recommendations", styles["Heading2"]))
    for rec in payload["recommendations"]:
        elements.append(Paragraph(f"- {rec}", styles["Normal"]))

    doc.build(elements)
    return buf.getvalue()


GENERATORS = {
    "json": generate_json_report,
    "csv": generate_csv_report,
    "xlsx": generate_xlsx_report,
    "pdf": generate_pdf_report,
}


def generate_report(db: Session, fmt: str, generated_by: str, campaign: Campaign | None = None) -> Report:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    generator = GENERATORS[fmt]
    content = generator(db, campaign)

    report_id_stub = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    filename = f"report_{report_id_stub}.{fmt}"
    path = os.path.join(REPORTS_DIR, filename)
    with open(path, "wb") as f:
        f.write(content)

    report = Report(
        campaign_id=campaign.id if campaign else None,
        generated_by=generated_by,
        format=fmt,
        generated_at=dt.datetime.now(dt.timezone.utc),
        file_path=path,
        parameters_json={},
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
