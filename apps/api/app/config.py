"""Typed settings loaded from environment variables and apps/api/.env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
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
    admin_emails: str = ""
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

    # ── Face detection and landmarks (MediaPipe, Phase 4.2) ──
    # Defaults are MediaPipe's documented defaults or geometric rationale (docs: FACE_ANALYSIS.md),
    # not values tuned on photos. Re-tune only on the validation split of a consented dataset.
    face_model_path: Path = API_DIR / "models" / "face_landmarker.task"
    face_min_detection_confidence: float = Field(default=0.5, ge=0, le=1)
    face_min_presence_confidence: float = Field(default=0.5, ge=0, le=1)
    face_max_faces_counted: int = Field(default=4, ge=2, le=10)
    face_low_confidence_warning: float = Field(default=0.7, ge=0, le=1)
    face_min_face_width_px: int = Field(default=128, ge=16)
    face_max_inference_side: int = Field(default=1920, ge=256)
    face_rotation_search: bool = True
    face_max_yaw_degrees: float = Field(default=25, gt=0, le=90)
    face_max_pitch_degrees: float = Field(default=20, gt=0, le=90)
    face_max_roll_degrees: float = Field(default=20, gt=0, le=180)
    face_min_in_frame_ratio: float = Field(default=0.95, ge=0, le=1)
    face_min_side_width_ratio: float = Field(default=0.5, gt=0, le=1)

    # ── Skin colour and undertone (Phase 4.3) ──
    # Method constants, not values tuned on photos; see SKIN_ANALYSIS.md before changing any.
    skin_white_balance: Literal["shades_of_gray", "none"] = "shades_of_gray"
    skin_wb_minkowski_p: float = Field(default=6.0, ge=1, le=20)
    skin_wb_max_gain: float = Field(default=1.5, gt=1, le=4)
    skin_mask_erosion_ratio: float = Field(default=0.03, ge=0, le=0.2)
    skin_min_pixels_per_region: int = Field(default=50, ge=1)
    skin_min_pixels: int = Field(default=300, ge=10)
    skin_kmeans_clusters: int = Field(default=3, ge=1, le=8)
    skin_kmeans_seed: int = 0
    skin_region_max_delta_e: float = Field(default=10.0, gt=0)
    skin_undertone_reference_hue: float = Field(default=55.0, ge=0, lt=360)
    skin_undertone_neutral_delta_h: float = Field(default=2.5, gt=0)
    # Optional JSON {"points": [[L*, hue], ...]} fitted on validation data by scripts/evaluate_skin.py.
    skin_undertone_reference_path: Path | None = None

    # ── Face shape and facial attributes (Phase 4.4) ──
    # Untuned starting values; see FACIAL_ATTRIBUTES.md before changing any.
    # Optional JSON {"prototypes": {shape: [4 floats]}, "spread": {...}} fitted on validation data
    # by scripts/evaluate_attributes.py --fit-prototypes.
    face_shape_prototypes_path: Path | None = None
    eye_min_iris_radius_px: float = Field(default=4.0, gt=0)
    eye_min_pixels: int = Field(default=20, ge=1)
    hair_min_pixels: int = Field(default=500, ge=10)
    # Above within-face skin variation (CIEDE2000 1.6-5.9 between regions on the test portrait).
    hair_skin_delta_e: float = Field(default=8.0, gt=0)
    hair_background_delta_e: float = Field(default=8.0, gt=0)
    contrast_low_max_delta_l: float = Field(default=20.0, gt=0)
    contrast_medium_max_delta_l: float = Field(default=40.0, gt=0)

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

    @field_validator("face_model_path")
    @classmethod
    def _resolve_model_path(cls, value: Path) -> Path:
        # Relative paths are relative to apps/api, whatever directory the server starts in.
        return value if value.is_absolute() else API_DIR / value

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
    def admin_email_allowlist(self) -> frozenset[str]:
        return frozenset(email.strip().lower() for email in self.admin_emails.split(",") if email.strip())

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def google_redirect_uri(self) -> str:
        return f"{self.web_url}{self.public_api_prefix}/auth/google/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()
