"""Background job endpoints — the hello-world pipeline used to verify the worker setup."""

from datetime import datetime

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.models import BackgroundJob, JobStatus
from app.tasks import hello_world

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class HelloJobRequest(BaseModel):
    name: str = Field(default="world", min_length=1, max_length=50)


class JobOut(BaseModel):
    id: str
    task_name: str
    status: JobStatus
    result: dict | None
    error: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


@router.post("/hello", status_code=202, response_model=JobOut)
def create_hello_job(body: HelloJobRequest, response: Response, db: Session = Depends(get_db)):
    job = BackgroundJob(task_name="vysel.hello_world", payload=body.model_dump())
    db.add(job)
    db.commit()  # the row must exist before the worker can pick the task up

    try:
        async_result = hello_world.delay(job.id, body.name)
    except Exception as exc:  # broker unreachable
        job.status, job.error = JobStatus.failed, "Queue unavailable"
        db.commit()
        raise ApiError(503, "SERVICE_UNAVAILABLE", "The job queue is unavailable. Try again shortly.") from exc

    job.celery_task_id = async_result.id
    db.commit()
    db.refresh(job)
    response.headers["Location"] = f"/v1/jobs/{job.id}"
    response.headers["Retry-After"] = "1"
    return job


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, response: Response, db: Session = Depends(get_db)):
    job = db.get(BackgroundJob, job_id)
    if job is None:
        raise ApiError(404, "NOT_FOUND", "Job not found.")
    if job.status in (JobStatus.queued, JobStatus.running):
        response.headers["Retry-After"] = "1"
    return job
