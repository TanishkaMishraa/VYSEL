"""ORM models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
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
    profile: Mapped["UserProfile | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    # These ORM cascades mirror the ON DELETE CASCADE foreign keys so account erasure also works on SQLite.
    face_scans: Mapped[list["FaceScan"]] = relationship(cascade="all, delete-orphan")
    analysis_results: Mapped[list["AnalysisResult"]] = relationship(cascade="all, delete-orphan")
    reports: Mapped[list["RecommendationReport"]] = relationship(cascade="all, delete-orphan")
    saved_looks: Mapped[list["SavedTryOnLook"]] = relationship(cascade="all, delete-orphan")


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


class UserProfile(TimestampMixin, Base):
    """Facts about the person (vs. `UserPreferences`, which are their goals). One row per user, created on demand."""

    __tablename__ = "profiles"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    skin_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # normal | dry | oily | combination | sensitive
    skin_concerns: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    # The analysis the user's current estimates come from; kept when that analysis is deleted, just unlinked.
    latest_analysis_id: Mapped[str | None] = mapped_column(
        ForeignKey("analysis_results.id", ondelete="SET NULL"), nullable=True, index=True
    )

    user: Mapped[User] = relationship(back_populates="profile")
    latest_analysis: Mapped["AnalysisResult | None"] = relationship()


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
    # Scans contain derived biometric data and are erased with their source image.
    face_scans: Mapped[list["FaceScan"]] = relationship(cascade="all, delete-orphan")


# ── Analysis, reports & recommendations ─────────────────────────────────────


class AnalysisResult(Base):
    """The feature estimates a report was generated from.

    Unlike a `FaceScan` (raw landmarks, erased with the selfie), this is the durable, non-biometric
    summary: when the source scan expires, `scan_id` is set to null and the result is kept.
    """

    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=prefixed_id("ana"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    scan_id: Mapped[str | None] = mapped_column(ForeignKey("face_scans.id", ondelete="SET NULL"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(10), nullable=False)  # scan | manual
    features: Mapped[dict] = mapped_column(JSON, nullable=False)  # schemas.RecommendationFeatures
    skin_tone_hex: Mapped[str | None] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    scan: Mapped["FaceScan | None"] = relationship()


class RecommendationReport(Base):
    """Account-owned snapshot of estimates and ranked suggestions.

    `report_data` is the immutable snapshot that is rendered and shared; `recommendations` indexes its items
    so feedback can reference them with a foreign key.
    """

    __tablename__ = "recommendation_reports"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=prefixed_id("rpt"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_results.id", ondelete="SET NULL"), nullable=True, index=True)
    report_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    share_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    analysis: Mapped[AnalysisResult | None] = relationship()
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="report", cascade="all, delete-orphan", order_by="(Recommendation.category, Recommendation.rank)"
    )


class Recommendation(Base):
    """One ranked suggestion within a report."""

    __tablename__ = "recommendations"
    __table_args__ = (UniqueConstraint("report_id", "item_key"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=prefixed_id("rec"))
    report_id: Mapped[str] = mapped_column(ForeignKey("recommendation_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    item_key: Mapped[str] = mapped_column(String(100), nullable=False)  # catalog ID, e.g. "eyewear.slim_rectangle"
    category: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-based within its category
    score: Mapped[float] = mapped_column(Float, nullable=False)

    report: Mapped[RecommendationReport] = relationship(back_populates="recommendations")
    feedback: Mapped[list["RecommendationFeedback"]] = relationship(cascade="all, delete-orphan")


class RecommendationFeedback(Base):
    """One replaceable feedback vote per user and recommendation in a report."""

    __tablename__ = "recommendation_feedback"
    __table_args__ = (
        UniqueConstraint("report_id", "user_id", "recommendation_id"),
        # `recommendation_id` is the item's catalog key, so votes can only be cast on items the report contains.
        ForeignKeyConstraint(
            ["report_id", "recommendation_id"], ["recommendations.report_id", "recommendations.item_key"], ondelete="CASCADE"
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=prefixed_id("fb"))
    report_id: Mapped[str] = mapped_column(ForeignKey("recommendation_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(100), nullable=False)
    helpful: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class FaceScan(TimestampMixin, Base):
    """Face detection + landmark extraction for one uploaded image (Phase 4.2).

    Landmarks are biometric data: a scan lives no longer than its image (`expires_at` is copied
    from it, and rows are deleted with the image or the account).
    """

    __tablename__ = "face_scans"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=prefixed_id("scn"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    image_id: Mapped[str] = mapped_column(ForeignKey("image_uploads.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # succeeded | failed
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    face_count: Mapped[int] = mapped_column(Integer, nullable=False)
    detection_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SavedTryOnLook(TimestampMixin, Base):
    """A user's reusable makeup preview, grouped by the occasion they selected."""

    __tablename__ = "saved_try_on_looks"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=prefixed_id("look"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    occasion: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    look_data: Mapped[dict] = mapped_column(JSON, nullable=False)

