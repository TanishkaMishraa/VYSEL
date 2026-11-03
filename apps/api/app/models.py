"""ORM models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin, utcnow


def prefixed_id(prefix: str):
    """Opaque, prefixed IDs (usr_…, job_…) as specified in docs/api/openapi.yaml."""
    return lambda: f"{prefix}_{uuid.uuid4().hex}"


# ── Background jobs ─────────────────────────────────────────────────────────


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class BackgroundJob(TimestampMixin, Base):
    """A unit of background work. The API creates the row; the worker owns status updates.

    The database (not Celery's result backend) is the source of truth for job status,
    the same pattern the selfie-analysis pipeline will use.
    """

    __tablename__ = "background_jobs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=prefixed_id("job"))
    task_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", native_enum=False, length=20), default=JobStatus.queued, nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


# ── Users & auth ────────────────────────────────────────────────────────────


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=prefixed_id("usr"))
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)  # stored lower-cased
    display_name: Mapped[str] = mapped_column(String(50), nullable=False)
    # Null for accounts created through Google that never set a password.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    preferences: Mapped["UserPreferences"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="joined")
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(back_populates="user", cascade="all, delete-orphan", lazy="selectin")


class RefreshToken(Base):
    """Opaque refresh token (only its SHA-256 is stored). Rotated on every use.

    All tokens descending from one login share a `family_id`; presenting a token that
    was already rotated means it leaked, so the whole family is revoked.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=prefixed_id("rt"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    family_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=prefixed_id("prt"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"
    __table_args__ = (UniqueConstraint("provider", "provider_user_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=prefixed_id("oa"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="oauth_accounts")


# ── Profile ─────────────────────────────────────────────────────────────────


class UserPreferences(TimestampMixin, Base):
    """Onboarding answers and defaults applied to new analyses. One row per user."""

    __tablename__ = "user_preferences"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    style_goals: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    occasions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    budget: Mapped[str | None] = mapped_column(String(10), nullable=True)
    style: Mapped[str | None] = mapped_column(String(20), nullable=True)
    categories: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="preferences")


class ImageUpload(TimestampMixin, Base):
    """Accepted selfie metadata. Image bytes stay in private storage under opaque keys."""

    __tablename__ = "image_uploads"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=prefixed_id("img"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(128), nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    blur_variance: Mapped[float] = mapped_column(Float, nullable=False)
    mean_brightness: Mapped[float] = mapped_column(Float, nullable=False)
    validation_results: Mapped[dict] = mapped_column(JSON, nullable=False)
    consent_policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    retention: Mapped[str] = mapped_column(String(16), default="ephemeral", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RecommendationReport(Base):
    """Account-owned snapshot of estimates and ranked suggestions."""

    __tablename__ = "recommendation_reports"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=prefixed_id("rpt"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    report_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    share_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RecommendationFeedback(Base):
    """One replaceable feedback vote per user and recommendation in a report."""

    __tablename__ = "recommendation_feedback"
    __table_args__ = (UniqueConstraint("report_id", "user_id", "recommendation_id"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=prefixed_id("fb"))
    report_id: Mapped[str] = mapped_column(ForeignKey("recommendation_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(100), nullable=False)
    helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
