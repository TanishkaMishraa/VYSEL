"""Celery application.

Start a worker (from apps/api):
    Windows:      celery -A app.worker worker --pool=solo --loglevel=INFO
    Linux/macOS:  celery -A app.worker worker --loglevel=INFO

Windows needs --pool=solo: Celery's default prefork pool is unsupported there.
"""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery("vysel", broker=settings.celery_broker_url, backend=settings.celery_result_backend, include=["app.tasks"])

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Reliability: ack only after the task finishes, one task at a time per process,
    # so a crashed worker's task is redelivered rather than lost.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=30,
    task_time_limit=45,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
)
