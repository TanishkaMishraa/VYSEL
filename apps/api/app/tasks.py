"""Background tasks. Each task updates its BackgroundJob row so status survives restarts."""

import logging
import time

from app.db import SessionLocal
from app.models import BackgroundJob, JobStatus
from app.worker import celery_app

log = logging.getLogger(__name__)


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
