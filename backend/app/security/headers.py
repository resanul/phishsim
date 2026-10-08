from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings


API_CSP = (
    "default-src 'self'; frame-ancestors 'none'; object-src 'none'; "
    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self'"
)

# The server-rendered dashboard uses Tailwind's CDN build and htmx for speed
# of delivery, plus a couple of small inline <script> blocks (theme toggle)
# and inline onclick/onsubmit confirmations. That requires a looser CSP than
# the JSON API. HARDENING NOTE for production: self-host Tailwind (compiled,
# not the CDN JIT script) and htmx, move inline scripts to an external file,
# and switch this to 'self'-only + a per-response nonce -- see SECURITY.md.
DASHBOARD_CSP = (
    "default-src 'self'; frame-ancestors 'none'; object-src 'none'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: https:; "
    "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com; "
    "frame-src 'self' data:"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"

        path = request.url.path
        is_api_or_tracking = path.startswith("/api") or path.startswith("/simulation") or path.startswith("/health")
        response.headers["Content-Security-Policy"] = API_CSP if is_api_or_tracking else DASHBOARD_CSP

        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response
