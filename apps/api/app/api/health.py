"""GET /v1/health — liveness plus dependency checks (schema: Health in openapi.yaml)."""

from typing import Literal

import redis
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from app import __version__
from app.config import get_settings
from app.db import engine

router = APIRouter(tags=["System"])

Check = Literal["ok", "down"]


class Health(BaseModel):
    status: Literal["ok", "degraded", "down"]
    version: str
    checks: dict[str, Check]


def _database() -> Check:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "down"


def _redis(url: str) -> Check:
    try:
        return "ok" if redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1).ping() else "down"
    except Exception:
        return "down"


@router.get("/health", response_model=Health, responses={503: {"model": Health}})
def get_health():
    settings = get_settings()
    checks: dict[str, Check] = {
        "database": _database(),
        "cache": _redis(settings.redis_url),
        "queue": "ok" if settings.celery_task_always_eager else _redis(settings.celery_broker_url),
    }
    healthy = all(v == "ok" for v in checks.values())
    body = Health(status="ok" if healthy else "down", version=__version__, checks=checks)
    return JSONResponse(body.model_dump(), status_code=200 if healthy else 503)
