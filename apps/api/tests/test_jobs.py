from app.db import SessionLocal
from app.models import BackgroundJob, JobStatus


def test_hello_job_runs_and_persists(client):
    res = client.post("/v1/jobs/hello", json={"name": "Tanya"})
    assert res.status_code == 202
    assert res.headers["location"] == f"/v1/jobs/{res.json()['id']}"
    job_id = res.json()["id"]

    status = client.get(f"/v1/jobs/{job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "succeeded"
    assert body["result"]["message"] == "Hello, Tanya!"
    assert "retry-after" not in status.headers  # terminal state

    # Read back straight from the database: the worker's write is durable.
    with SessionLocal() as db:
        row = db.get(BackgroundJob, job_id)
        assert row.status is JobStatus.succeeded
        assert row.celery_task_id
        assert row.payload == {"name": "Tanya"}


def test_unknown_job_is_problem_json_404(client):
    res = client.get("/v1/jobs/job_doesnotexist")
    assert res.status_code == 404
    assert res.headers["content-type"].startswith("application/problem+json")
    assert res.json()["code"] == "NOT_FOUND"


def test_validation_error_is_problem_json_422(client):
    res = client.post("/v1/jobs/hello", json={"name": ""})
    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["errors"][0]["field"] == "name"


def test_queue_down_returns_503_and_marks_job_failed(client, monkeypatch):
    import app.api.jobs as jobs

    def boom(*_a, **_k):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr(jobs.hello_world, "delay", boom)
    res = client.post("/v1/jobs/hello", json={"name": "x"})
    assert res.status_code == 503
    assert res.json()["code"] == "SERVICE_UNAVAILABLE"
    with SessionLocal() as db:
        latest = db.query(BackgroundJob).order_by(BackgroundJob.created_at.desc()).first()
        assert latest.status is JobStatus.failed
