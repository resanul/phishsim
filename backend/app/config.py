"""
Application configuration.

All secrets and environment-dependent values MUST come from environment
variables / .env — never hard-code credentials, keys, or connection strings
here. See .env.example for the full list of supported settings.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Core application ---
    app_name: str = "Phishing Simulation & Security Awareness Platform"
    environment: str = Field(default="development")  # development | staging | production
    debug: bool = False
    secret_key: str = Field(..., description="Used for signing JWTs and session cookies. MUST be set via env.")
    base_url: str = "http://localhost:8000"

    # --- Database ---
    database_url: str = Field(..., description="e.g. postgresql+psycopg://user:pass@host:5432/dbname")

    # --- Redis / background jobs ---
    redis_url: Optional[str] = None
    use_celery: bool = False  # if False, APScheduler is used in-process

    # --- Auth ---
    access_token_expire_minutes: int = 30
    jwt_algorithm: str = "HS256"
    session_cookie_name: str = "phishsim_session"
    session_cookie_secure: bool = True
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    require_mfa_for_admins: bool = True

    # --- Email / sending engine ---
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    default_sender_name: str = "IT Security"
    default_sender_email: str = "security-awareness@example.org"
    max_emails_per_minute: int = 30

    # --- Safety / organizational scope ---
    # Comma-separated in the environment (e.g. "example.org,corp.example.org");
    # use the `approved_recipient_domains` property for the parsed list.
    approved_recipient_domains_raw: str = Field(default="", alias="approved_recipient_domains")
    test_mode_default: bool = True

    # --- Privacy / retention ---
    default_retention_days: int = 180

    # --- Tracking ---
    tracking_token_bytes: int = 32

    @property
    def approved_recipient_domains(self) -> List[str]:
        return [d.strip().lower() for d in self.approved_recipient_domains_raw.split(",") if d.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


settings = Settings()  # type: ignore[call-arg]
