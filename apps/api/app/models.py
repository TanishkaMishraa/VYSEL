"""ORM models. Product tables (users, images, analyses) arrive in later phases."""

import enum
import uuid

from sqlalchemy import JSON, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


def new_job_id() -> str:
    return f"job_{uuid.uuid4().hex}"


class BackgroundJob(TimestampMixin, Base):
    """A unit of background work. The API creates the row; the worker owns status updates.

    The database (not Celery's result backend) is the source of truth for job status,
    the same pattern the selfie-analysis pipeline will use.
    """

    __tablename__ = "background_jobs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=new_job_id)
    task_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", native_enum=False, length=20), default=JobStatus.queued, nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
