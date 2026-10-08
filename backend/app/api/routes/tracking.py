from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip
from app.database import get_db
from app.models.campaigns import Campaign
from app.models.enums import CampaignEventType
from app.services import tracking_service
from app.services.content_service import render_variables

router = APIRouter(tags=["tracking"])


def _get_target_or_404(db: Session, campaign_id: str, token: str):
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    target = tracking_service.get_target_by_token(db, campaign_id, token)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    return campaign, target


@router.get("/simulation/{campaign_id}/{token}", response_class=HTMLResponse)
def simulation_landing(campaign_id: str, token: str, request: Request, db: Session = Depends(get_db)):
    campaign, target = _get_target_or_404(db, campaign_id, token)

    tracking_service.record_event(
        db, target, CampaignEventType.LINK_CLICKED, ip=get_client_ip(request), user_agent=request.headers.get("user-agent", "")
    )
    tracking_service.record_event(
        db, target, CampaignEventType.LANDING_VISITED, ip=get_client_ip(request), user_agent=request.headers.get("user-agent", "")
    )

    page = campaign.landing_page
    variables = {
        "first_name": target.recipient.first_name,
        "last_name": target.recipient.last_name,
        "department": target.recipient.department,
        "job_title": target.recipient.job_title,
        "company": campaign.authorized_organization,
        "campaign_name": campaign.name,
        "simulation_link": "",
    }
    html = render_variables(page.html_body, variables)
    return HTMLResponse(content=html)


@router.post("/simulation/{campaign_id}/{token}/demo-form")
def submit_demo_form(campaign_id: str, token: str, request: Request, db: Session = Depends(get_db)):
    """Endpoint for the OPTIONAL synthetic credential-entry demo.

    By design this handler never reads request.form()/request.json() for
    the submitted field values -- it only records that an interaction
    happened. Any values a user types into the demo fields are discarded by
    the client-side page and never reach the server in the first place; this
    endpoint exists purely to record the training event.
    """
    campaign, target = _get_target_or_404(db, campaign_id, token)
    if not campaign.landing_page.has_synthetic_form:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This landing page has no synthetic form.")

    tracking_service.handle_synthetic_form_submission(
        db, target, ip=get_client_ip(request), user_agent=request.headers.get("user-agent", "")
    )
    return {"status": "recorded", "note": "No submitted values were stored. This was a simulation."}


@router.post("/simulation/{campaign_id}/{token}/report-phishing")
def report_phishing(campaign_id: str, token: str, request: Request, db: Session = Depends(get_db)):
    campaign, target = _get_target_or_404(db, campaign_id, token)
    tracking_service.record_event(
        db, target, CampaignEventType.REPORTED_PHISHING, ip=get_client_ip(request), user_agent=request.headers.get("user-agent", "")
    )
    return {"status": "reported", "message": "Thank you for reporting this simulated phishing attempt."}


@router.post("/simulation/{campaign_id}/{token}/training/start")
def training_start(campaign_id: str, token: str, db: Session = Depends(get_db)):
    campaign, target = _get_target_or_404(db, campaign_id, token)
    session = tracking_service.start_training_session(db, target)
    return {"training_session_id": session.id}


@router.post("/simulation/{campaign_id}/{token}/training/{session_id}/complete")
def training_complete(campaign_id: str, token: str, session_id: str, request: Request, db: Session = Depends(get_db)):
    campaign, target = _get_target_or_404(db, campaign_id, token)
    from app.models.campaigns import TrainingSession

    session = db.get(TrainingSession, session_id)
    if session is None or session.target_id != target.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Training session not found.")
    tracking_service.complete_training_session(db, session)
    tracking_service.record_event(
        db, target, CampaignEventType.TRAINING_VIEWED, ip=get_client_ip(request), user_agent=request.headers.get("user-agent", "")
    )
    tracking_service.record_event(
        db, target, CampaignEventType.SIMULATION_COMPLETED, ip=get_client_ip(request), user_agent=request.headers.get("user-agent", "")
    )
    return {"status": "completed"}
