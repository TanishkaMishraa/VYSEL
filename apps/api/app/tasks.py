"""Background tasks. Each task updates its BackgroundJob row so status survives restarts."""

import logging
import time

from app import email
from app.db import SessionLocal
from app.models import BackgroundJob, JobStatus
from app.services.scan_pipeline import process_face_scan
from app.worker import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="vysel.analyze_face_scan", bind=True)
def analyze_face_scan(self, scan_id: str) -> dict:
    """Run face detection, landmarks, skin and facial attributes in the worker."""
    return process_face_scan(scan_id)


@celery_app.task(name="vysel.hello_world", bind=True)
def hello_world(self, job_id: str, name: str = "world", delay_seconds: float = 1.0) -> dict:
    """Hello-world task: proves the API → Redis → worker → PostgreSQL round trip."""
    with SessionLocal() as db:
        job = db.get(BackgroundJob, job_id)
        if job is None:
            log.warning("hello_world: job %s not found", job_id)
            return {"error": "job not found"}
        job.status = JobStatus.running
        db.commit()

        try:
            time.sleep(delay_seconds)  # stand-in for real work
            result = {"message": f"Hello, {name}!", "worker": self.request.hostname or "eager"}
            job.status = JobStatus.succeeded
            job.result = result
            db.commit()
            log.info("hello_world: job %s succeeded", job_id)
            return result
        except Exception as exc:
            db.rollback()
            job.status = JobStatus.failed
            job.error = f"{type(exc).__name__}: {exc}"
            db.commit()
            raise


@celery_app.task(name="vysel.send_email", autoretry_for=(OSError,), retry_backoff=True, max_retries=5)
def send_email(to: str, subject: str, text: str) -> None:
    """Deliver one email; retried with backoff on network errors (SMTP down, timeouts)."""
    email.send(to, subject, text)
