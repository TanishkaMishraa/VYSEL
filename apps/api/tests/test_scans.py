"""POST/GET /v1/scans: integration with the Phase 4.1 upload flow, response schema and error codes."""

from __future__ import annotations

import io
from datetime import timedelta

import numpy as np
import pytest
from PIL import Image

from app.config import Settings
from app.db import SessionLocal, utcnow
from app.models import FaceScan, ImageUpload
from tests.conftest import FIXTURES


def bearer(session: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {session['access_token']}"}


@pytest.fixture
def storage(monkeypatch, tmp_path):
    """Private storage in a temp dir, shared by the upload and scan endpoints."""
    from app.api import images
    from app.services import scan_pipeline

    settings = Settings(_env_file=None, selfie_storage_dir=tmp_path)
    monkeypatch.setattr(images, "get_settings", lambda: settings)
    monkeypatch.setattr(scan_pipeline, "get_settings", lambda: settings)
    return tmp_path


def upload(client, auth, content: bytes) -> str:
    response = client.post(
        "/v1/images",
        headers=auth,
        files={"file": ("selfie.jpg", content, "image/jpeg")},
        data={"consent": "true", "policy_version": "2026-11-01"},
    )
    assert response.status_code == 201, response.text
    return response.json()["image"]["id"]


def two_faces() -> bytes:
    portrait = np.asarray(Image.open(FIXTURES / "portrait.jpg").convert("RGB"))
    stream = io.BytesIO()
    Image.fromarray(np.concatenate([portrait, portrait[:, ::-1]], axis=1)).save(stream, "JPEG", quality=90)
    return stream.getvalue()


def scan(client, auth, image_id: str):
    return client.post("/v1/scans", headers=auth, json={"image_id": image_id})


def test_scan_of_a_valid_selfie(client, signup, storage, face_analyzer):
    _, _, session = signup()
    auth = bearer(session)
    image_id = upload(client, auth, (FIXTURES / "portrait.jpg").read_bytes())

    response = scan(client, auth, image_id)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["id"].startswith("scn_") and response.headers["location"] == f"/v1/scans/{body['id']}"
    assert body["image_id"] == image_id and body["status"] == "succeeded" and body["face_count"] == 1
    assert 0.5 <= body["detection"]["confidence"] <= 1
    assert body["landmarks"]["count"] == len(body["landmarks"]["points"]) == 478
    assert set(body["landmarks"]["points"][0]) == {"index", "x", "y", "z", "px", "py"}
    assert {"forehead", "left_cheek", "right_cheek", "chin", "jawline", "face_oval"} <= set(body["regions"])
    assert body["regions"]["left_cheek"]["visible"] is True and body["regions"]["left_cheek"]["polygon"]
    assert {"forehead_top", "chin_bottom", "nose_tip"} <= set(body["key_points"])
    assert set(body["head_pose"]) == {"pitch", "yaw", "roll"}
    assert body["warnings"] == [] and "error" not in body
    assert all(check["passed"] for check in body["validation"].values())
    assert body["model"]["name"].startswith("mediapipe-face-landmarker")
    skin = body["skin"]  # Phase 4.3
    assert skin["status"] == "ok"
    assert set(skin["skin_tone"]) >= {"hex", "lab", "depth", "confidence", "label", "ita_degrees", "monk"}
    assert skin["undertone"]["value"] in {"warm", "cool", "neutral"} and skin["undertone"]["label"] == "estimate"
    assert skin["color_correction"]["method"] == "shades_of_gray" and skin["clusters"]
    attributes = body["attributes"]  # Phase 4.4
    assert attributes["face_shape"]["status"] == "ok" and attributes["face_shape"]["label"] == "estimate"
    assert len(attributes["face_shape"]["alternatives"]) == 2
    assert attributes["eye_color"]["status"] == "ok" and attributes["hair_color"]["status"] == "ok"
    # The scan's estimates go straight into the recommendation engine.
    recommended = client.post("/v1/recommendations", headers=auth, json=body["recommendation_features"])
    assert recommended.status_code == 200, recommended.text
    assert recommended.json()["features"]["face_shape"]["value"] == attributes["face_shape"]["value"]
    # Nothing internal leaks: no storage path, storage key, or user ID.
    assert str(storage) not in response.text and "storage_key" not in response.text
    assert session["user"]["id"] not in response.text

    fetched = client.get(f"/v1/scans/{body['id']}", headers=auth)
    assert fetched.status_code == 200 and fetched.json() == body


def test_scan_is_queued_and_frontend_can_poll_status(client, signup, storage, monkeypatch, face_analyzer):
    from types import SimpleNamespace

    from app.api import scans as scans_api
    from app.services.scan_pipeline import process_face_scan

    monkeypatch.setattr(scans_api.analyze_face_scan, "delay", lambda _scan_id: SimpleNamespace(id="task-id"))
    _, _, session = signup()
    auth = bearer(session)
    image_id = upload(client, auth, (FIXTURES / "portrait.jpg").read_bytes())

    created = scan(client, auth, image_id)
    assert created.status_code == 202 and created.json()["status"] == "queued"
    scan_id = created.json()["id"]
    pending = client.get(f"/v1/scans/{scan_id}", headers=auth)
    assert pending.status_code == 200 and pending.json()["status"] == "queued"
    assert pending.headers["retry-after"] == "1"

    outcome = process_face_scan(scan_id)
    assert outcome["status"] == "succeeded"
    complete = client.get(f"/v1/scans/{scan_id}", headers=auth)
    assert complete.json()["status"] == "succeeded"
    assert complete.json()["processing_time_ms"] >= 0


@pytest.mark.parametrize(
    ("content", "code", "faces"),
    [
        (lambda: (FIXTURES / "cat.jpg").read_bytes(), "NO_FACE_DETECTED", 0),
        (two_faces, "MULTIPLE_FACES_DETECTED", 2),
    ],
    ids=["no-face", "multiple-faces"],
)
def test_rejections_return_problem_with_failed_scan(client, signup, storage, face_analyzer, content, code, faces):
    _, _, session = signup()
    auth = bearer(session)
    response = scan(client, auth, upload(client, auth, content()))

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "failed"
    failed = body
    assert failed["status"] == "failed" and failed["face_count"] == faces
    assert failed["error"]["code"] == code and not {"landmarks", "skin", "attributes"} & set(failed)
    # The failed background scan is stored and retrievable.
    assert client.get(f"/v1/scans/{failed['id']}", headers=auth).json()["status"] == "failed"


def test_only_images_passing_phase_4_1_are_analyzed(client, signup, storage, monkeypatch):
    """Stored images are re-validated with the current rules before any face analysis."""
    _, _, session = signup()
    auth = bearer(session)
    image_id = upload(client, auth, (FIXTURES / "portrait.jpg").read_bytes())
    from app.services import scan_pipeline

    strict = Settings(_env_file=None, selfie_storage_dir=storage, selfie_min_width=2000, selfie_min_height=2000)
    monkeypatch.setattr(scan_pipeline, "get_settings", lambda: strict)
    monkeypatch.setattr(scan_pipeline, "get_face_analyzer", lambda: pytest.fail("analyzer must not run"))

    response = scan(client, auth, image_id)
    assert response.status_code == 202
    assert response.json()["status"] == "failed"
    assert response.json()["error"]["code"] == "IMAGE_QUALITY_FAILED"
    assert not response.json()["validation"]["resolution"]["passed"]


def test_access_control_and_input_validation(client, signup, storage):
    _, _, owner = signup()
    _, _, other = signup()
    image_id = upload(client, bearer(owner), (FIXTURES / "portrait.jpg").read_bytes())

    assert client.post("/v1/scans", json={"image_id": image_id}).status_code == 401
    assert scan(client, bearer(other), image_id).status_code == 404  # someone else's image
    assert scan(client, bearer(owner), "img_missing").json()["code"] == "NOT_FOUND"
    invalid = client.post("/v1/scans", headers=bearer(owner), json={"image_id": image_id, "path": "/etc/passwd"})
    assert invalid.status_code == 422 and invalid.json()["code"] == "VALIDATION_ERROR"
    assert client.get("/v1/scans/scn_missing", headers=bearer(owner)).status_code == 404


def test_expired_image(client, signup, storage):
    _, _, session = signup()
    image_id = upload(client, bearer(session), (FIXTURES / "portrait.jpg").read_bytes())
    with SessionLocal() as db:
        db.get(ImageUpload, image_id).expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    response = scan(client, bearer(session), image_id)
    assert response.status_code == 410 and response.json()["code"] == "UPLOAD_EXPIRED"


def test_model_unavailable_is_reported_safely_by_scan(client, signup, storage, monkeypatch):
    from app.services import scan_pipeline
    from app.services.face_analysis import FaceModelUnavailable

    def unavailable():
        raise FaceModelUnavailable("Face model not found at C:/secret/path/model.task")

    monkeypatch.setattr(scan_pipeline, "get_face_analyzer", unavailable)
    _, _, session = signup()
    response = scan(client, bearer(session), upload(client, bearer(session), (FIXTURES / "portrait.jpg").read_bytes()))
    assert response.status_code == 202
    assert response.json()["status"] == "failed"
    assert response.json()["error"]["code"] == "FACE_ANALYSIS_UNAVAILABLE"
    assert "secret" not in response.text


def test_queue_failure_returns_safe_503(client, signup, storage, monkeypatch):
    from app.api import scans as scans_api

    def unavailable(_scan_id):
        raise ConnectionError("redis://private-host/internal")

    monkeypatch.setattr(scans_api.analyze_face_scan, "delay", unavailable)
    _, _, session = signup()
    auth = bearer(session)
    image_id = upload(client, auth, (FIXTURES / "portrait.jpg").read_bytes())

    response = scan(client, auth, image_id)
    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"
    assert "private-host" not in response.text
    with SessionLocal() as db:
        assert db.query(FaceScan).filter_by(image_id=image_id).count() == 0


def test_deleting_the_image_deletes_its_scans(client, signup, storage, face_analyzer):
    _, _, session = signup()
    auth = bearer(session)
    image_id = upload(client, auth, (FIXTURES / "portrait.jpg").read_bytes())
    scan_id = scan(client, auth, image_id).json()["id"]

    assert client.delete(f"/v1/images/{image_id}", headers=auth).status_code == 204
    assert client.get(f"/v1/scans/{scan_id}", headers=auth).status_code == 404
    with SessionLocal() as db:
        assert db.get(FaceScan, scan_id) is None
