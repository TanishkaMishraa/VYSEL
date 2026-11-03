"""Typed settings loaded from environment variables and apps/api/.env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parents[1]
INSECURE_DEV_SECRET = "dev-insecure-secret-change-me"  # noqa: S105 — refused in production below


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://vysel:vysel@localhost:5432/vysel"
    redis_url: str = "redis://127.0.0.1:6379/0"
    celery_broker_url: str = "redis://127.0.0.1:6379/1"
    celery_result_backend: str = "redis://127.0.0.1:6379/2"
    # Run tasks inline instead of via the broker (tests, or demos without a worker).
    celery_task_always_eager: bool = False

    # Comma-separated origins allowed to call the API directly. The web app normally
    # goes through the Next.js proxy (same origin), so this stays empty in development.
    cors_origins: str = ""

    # ── Auth ──
    jwt_secret: str = INSECURE_DEV_SECRET
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    password_reset_ttl_minutes: int = 30
    # Public URL of the web app: used for links in emails and OAuth redirects.
    web_url: str = "http://localhost:3000"
    # Browser-visible API prefix (via the Next.js proxy). Cookies are scoped to it.
    public_api_prefix: str = "/api/v1"
    cookie_secure: bool = False  # True in production (HTTPS)
    rate_limit_enabled: bool = True

    # ── Google OAuth (optional — the button hides itself when unset) ──
    google_client_id: str = ""
    google_client_secret: str = ""

    # ── Email (console logs links in development; smtp sends for real) ──
    email_backend: Literal["console", "smtp"] = "console"
    email_from: str = "VYSEL <no-reply@vysel.app>"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""

    @model_validator(mode="after")
    def _production_safety(self) -> "Settings":
        if self.app_env == "production":
            if self.jwt_secret == INSECURE_DEV_SECRET or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be set to a random value of 32+ characters in production")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def google_redirect_uri(self) -> str:
        return f"{self.web_url}{self.public_api_prefix}/auth/google/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
