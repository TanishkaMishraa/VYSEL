"""Test configuration.

Uses TEST_DATABASE_URL when set (CI: a real PostgreSQL test database), otherwise a
temporary SQLite file. Celery runs eagerly, so tests need no broker or worker.
Environment is set before any `app` import because the engine is created at import time.
"""

import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="vysel-tests-"))
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{(_tmp / 'test.db').as_posix()}"
os.environ["APP_ENV"] = "test"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["RATE_LIMIT_ENABLED"] = "false"  # enabled explicitly in test_ratelimit
os.environ["PUBLIC_API_PREFIX"] = "/v1"  # TestClient calls the API directly (no Next.js proxy)
os.environ["JWT_SECRET"] = "test-secret-" + "x" * 40
os.environ["EMAIL_BACKEND"] = "console"
os.environ["GOOGLE_CLIENT_ID"] = "test-client-id.apps.googleusercontent.com"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

API_DIR = Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    return cfg


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Build the schema with the real migrations — tests double as a migration check."""
    command.downgrade(alembic_config(), "base")
    command.upgrade(alembic_config(), "head")
    yield
    command.downgrade(alembic_config(), "base")


@pytest.fixture
def client(monkeypatch):
    import app.tasks

    monkeypatch.setattr(app.tasks.time, "sleep", lambda _s: None)  # keep tests fast
    from app.main import app as fastapi_app

    with TestClient(fastapi_app) as c:
        yield c


@pytest.fixture
def outbox(monkeypatch):
    """Captures emails sent by the (eager) send_email task."""
    sent = []
    import app.email

    monkeypatch.setattr(app.email, "send", lambda to, subject, text: sent.append({"to": to, "subject": subject, "text": text}))
    return sent


def unique_email() -> str:
    import uuid

    return f"user-{uuid.uuid4().hex[:10]}@example.com"


@pytest.fixture
def signup(client):
    """Register a fresh user; returns (email, password, session_json)."""

    def _signup(password: str = "correct-horse-battery", name: str = "Tanya"):
        email = unique_email()
        res = client.post("/v1/auth/register", json={"email": email, "password": password, "display_name": name})
        assert res.status_code == 201, res.text
        return email, password, res.json()

    return _signup
