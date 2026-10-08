from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import admins, analytics, audit, auth, campaigns, content, emergency, recipients, reports, settings_routes, tracking
from app.config import settings
from app.database import SessionLocal
from app.security.headers import SecurityHeadersMiddleware
from app.services.bootstrap import seed_rbac
from app.services.sending_service import dispatch_pending
from app.web.deps import RedirectToLogin
from app.web.routes import admins_web, analytics_web, auth_web, campaigns_web, dashboard_web, landing_pages_web, recipients_web, reports_web, settings_web, templates_web, training_web
from app.web.routes import audit_web as audit_web_routes

logging.basicConfig(level=logging.INFO if not settings.debug else logging.DEBUG)
logger = logging.getLogger("phishsim")

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        seed_rbac(db)
    finally:
        db.close()

    scheduler.add_job(dispatch_pending, "interval", seconds=15, id="dispatch_pending", replace_existing=True)
    scheduler.start()
    logger.info("PhishSim backend started. Sending engine dispatch job running every 15s.")
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(SecurityHeadersMiddleware)


def _is_api_request(path: str) -> bool:
    return path.startswith("/api") or path.startswith("/simulation") or path.startswith("/health")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    if _is_api_request(request.url.path):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    if exc.status_code == 401:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=303)
    return HTMLResponse(
        f"<html><body style='font-family:sans-serif;padding:2rem;'><h1>{exc.status_code}</h1><p>{exc.detail}</p>"
        f"<p><a href='/'>Return to dashboard</a></p></body></html>",
        status_code=exc.status_code,
    )


@app.exception_handler(RedirectToLogin)
async def redirect_to_login_handler(request, exc: RedirectToLogin):
    return RedirectResponse(f"/login?next={exc.next_path}", status_code=303)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


app.include_router(auth.router)
app.include_router(admins.router)
app.include_router(recipients.router)
app.include_router(content.router)
app.include_router(campaigns.router)
app.include_router(analytics.router)
app.include_router(reports.router)
app.include_router(audit.router)
app.include_router(settings_routes.router)
app.include_router(emergency.router)
app.include_router(tracking.router)

# Server-rendered dashboard (cookie session + CSRF, separate trust boundary from the JSON API above)
app.include_router(auth_web.router)
app.include_router(dashboard_web.router)
app.include_router(campaigns_web.router)
app.include_router(templates_web.router)
app.include_router(landing_pages_web.router)
app.include_router(recipients_web.router)
app.include_router(analytics_web.router)
app.include_router(reports_web.router)
app.include_router(audit_web_routes.router)
app.include_router(settings_web.router)
app.include_router(admins_web.router)
app.include_router(training_web.router)
