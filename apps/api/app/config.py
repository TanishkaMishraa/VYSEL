"""Typed settings loaded from environment variables and apps/api/.env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
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

    # Private local storage and rule-based selfie validation.
    selfie_storage_dir: Path = API_DIR / ".private" / "selfies"
    selfie_max_file_size_bytes: int = Field(default=5 * 1024 * 1024, gt=0)
    selfie_min_width: int = Field(default=256, ge=1)
    selfie_min_height: int = Field(default=256, ge=1)
    selfie_max_width: int = Field(default=8192, ge=256)
    selfie_max_height: int = Field(default=8192, ge=256)
    selfie_max_pixels: int = Field(default=40_000_000, ge=65_536)
    selfie_min_blur_variance: float = Field(default=35.0, ge=0)
    selfie_min_brightness: float = Field(default=35.0, ge=0, le=255)
    selfie_max_brightness: float = Field(default=225.0, ge=0, le=255)
    selfie_max_dark_pixel_ratio: float = Field(default=0.75, ge=0, le=1)
    selfie_max_bright_pixel_ratio: float = Field(default=0.75, ge=0, le=1)
    selfie_upload_chunk_bytes: int = Field(default=64 * 1024, ge=1024)

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
        if self.selfie_min_brightness > self.selfie_max_brightness:
            raise ValueError("SELFIE_MIN_BRIGHTNESS must be <= SELFIE_MAX_BRIGHTNESS")
        if self.selfie_min_width > self.selfie_max_width or self.selfie_min_height > self.selfie_max_height:
            raise ValueError("Selfie minimum dimensions must not exceed maximum dimensions")
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
