from __future__ import annotations

from io import BytesIO

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.services.image_validation import ImageValidationError, validate_image


def bearer(session: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {session['access_token']}"}


def image_bytes(fmt: str = "JPEG", size: tuple[int, int] = (512, 512), kind: str = "texture") -> bytes:
    if kind == "texture":
        rng = np.random.default_rng(310)
        pixels = rng.integers(25, 230, (size[1], size[0], 3), dtype=np.uint8)
    elif kind == "dark":
        pixels = np.full((size[1], size[0], 3), 8, dtype=np.uint8)
    elif kind == "overexposed":
        pixels = np.full((size[1], size[0], 3), 255, dtype=np.uint8)
    elif kind == "blurry":
        pixels = np.full((size[1], size[0], 3), 125, dtype=np.uint8)
    else:
        raise ValueError(kind)
    stream = BytesIO()
    Image.fromarray(pixels).save(stream, format=fmt)
    return stream.getvalue()


def post_image(client: TestClient, auth: dict, content: bytes, filename: str = "face.jpg", mime: str = "image/jpeg"):
    return client.post(
        "/v1/images",
        headers=auth,
        files={"file": (filename, content, mime)},
        data={"consent": "true", "policy_version": "2026-11-01"},
    )


@pytest.mark.parametrize(
    ("filename", "mime", "fmt"),
    [
        ("portrait.jpg", "image/jpeg", "JPEG"),
        ("portrait.jpeg", "image/jpeg", "JPEG"),
        ("portrait.png", "image/png", "PNG"),
    ],
    ids=["jpg", "jpeg", "png"],
)
def test_uploads_valid_jpeg_and_png(client, signup, monkeypatch, tmp_path, filename, mime, fmt):
    _, _, session = signup()
    from app.api import images

    monkeypatch.setattr(images, "get_settings", lambda: Settings(_env_file=None, selfie_storage_dir=tmp_path))
    response = post_image(client, bearer(session), image_bytes(fmt), filename, mime)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["image"]["status"] == "uploaded"
    assert body["image"]["id"].startswith("img_")
    assert body["image"]["width"] == 512
    assert body["image"]["content_type"] == mime
    assert all(check["passed"] for check in body["validation"].values())
    assert len(list(tmp_path.iterdir())) == 1
    assert str(tmp_path) not in response.text


def test_authentication_and_consent_required(client, signup):
    _, _, session = signup()
    data = {"file": ("face.jpg", image_bytes(), "image/jpeg")}
    assert client.post("/v1/images", files=data, data={"consent": "true", "policy_version": "v1"}).status_code == 401
    response = client.post(
        "/v1/images",
        headers=bearer(session),
        files=data,
        data={"consent": "false", "policy_version": "v1"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "CONSENT_REQUIRED"


@pytest.mark.parametrize(
    ("filename", "mime", "payload", "code", "status"),
    [
        ("face.gif", "image/gif", b"bad", "UNSUPPORTED_FORMAT", 415),
        ("face.jpg", "image/png", image_bytes(), "MIME_MISMATCH", 415),
        ("face.jpg", "image/jpeg", image_bytes("PNG"), "FORMAT_MISMATCH", 415),
        ("face.png", "image/png", b"not an image", "CORRUPT_IMAGE", 400),
        ("face.jpg", "image/jpeg", b"", "EMPTY_UPLOAD", 400),
    ],
    ids=["unsupported-extension", "mime-mismatch", "format-mismatch", "corrupt-image", "empty-file"],
)
def test_rejects_invalid_file_inputs(client, signup, filename, mime, payload, code, status):
    _, _, session = signup()
    response = post_image(client, bearer(session), payload, filename, mime)
    assert response.status_code == status
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == code
    assert "traceback" not in response.text.lower()


def test_rejects_large_file(client, signup):
    _, _, session = signup()
    response = post_image(client, bearer(session), b"x" * (5 * 1024 * 1024 + 1))
    assert response.status_code == 413
    assert response.json()["code"] == "FILE_TOO_LARGE"


@pytest.mark.parametrize(("kind", "check"), [("dark", "brightness"), ("overexposed", "brightness"), ("blurry", "blur")])
def test_rejects_quality_failures(client, signup, kind, check):
    _, _, session = signup()
    response = post_image(client, bearer(session), image_bytes("PNG", kind=kind), "face.png", "image/png")
    assert response.status_code == 422
    assert response.json()["code"] == "IMAGE_QUALITY_FAILED"
    assert not response.json()["validation"][check]["passed"]
    assert response.json()["validation_errors"]
    if kind == "dark":
        assert len(response.json()["validation_errors"]) > 1


def test_minimum_and_maximum_resolution_and_threshold_boundary():
    low = validate_image(image_bytes("PNG", (128, 128)), "face.png", "image/png")
    assert not low.checks["resolution"].passed
    cfg = Settings(_env_file=None, selfie_max_width=300, selfie_max_height=300)
    with pytest.raises(ImageValidationError) as too_big:
        validate_image(image_bytes("PNG"), "face.png", "image/png", cfg)
    assert too_big.value.status_code == 413
    pixel_cfg = Settings(_env_file=None, selfie_max_pixels=100_000)
    with pytest.raises(ImageValidationError) as too_many_pixels:
        validate_image(image_bytes("PNG"), "face.png", "image/png", pixel_cfg)
    assert too_many_pixels.value.code == "IMAGE_DIMENSIONS_TOO_LARGE"

    data = image_bytes("PNG")
    first = validate_image(data, "face.png", "image/png")
    edge_cfg = Settings(
        _env_file=None,
        selfie_min_blur_variance=first.blur_variance,
        selfie_min_brightness=first.mean_brightness,
        selfie_max_brightness=first.mean_brightness,
    )
    edge = validate_image(data, "face.png", "image/png", edge_cfg)
    assert edge.checks["blur"].passed and edge.checks["brightness"].passed
    exact_size_cfg = Settings(_env_file=None, selfie_max_file_size_bytes=len(data))
    assert validate_image(data, "face.png", "image/png", exact_size_cfg).valid


def test_path_traversal_filename_is_never_used_as_storage_path(client, signup, monkeypatch, tmp_path):
    _, _, session = signup()
    from app.api import images

    monkeypatch.setattr(images, "get_settings", lambda: Settings(_env_file=None, selfie_storage_dir=tmp_path))
    response = post_image(client, bearer(session), image_bytes("PNG"), "../../../../evil.png", "image/png")
    assert response.status_code == 201
    assert len(list(tmp_path.iterdir())) == 1
    assert (tmp_path / "evil.png").exists() is False
    assert response.headers["location"] == f"/v1/images/{response.json()['image']['id']}"


def test_missing_multipart_fields_and_bad_metadata(client, signup):
    _, _, session = signup()
    response = client.post(
        "/v1/images",
        headers=bearer(session),
        files={"file": ("face.jpg", image_bytes(), "image/jpeg")},
    )
    assert response.status_code == 422
    no_file = client.post(
        "/v1/images",
        headers=bearer(session),
        data={"consent": "true", "policy_version": "v1"},
    )
    assert no_file.status_code == 422


def test_image_metadata_is_scoped_to_authenticated_owner(client, signup, monkeypatch, tmp_path):
    _, _, first = signup()
    _, _, second = signup()
    from app.api import images

    monkeypatch.setattr(images, "get_settings", lambda: Settings(_env_file=None, selfie_storage_dir=tmp_path))
    created = post_image(client, bearer(first), image_bytes())
    image_id = created.json()["image"]["id"]
    assert client.get(f"/v1/images/{image_id}", headers=bearer(first)).status_code == 200
    hidden = client.get(f"/v1/images/{image_id}", headers=bearer(second))
    assert hidden.status_code == 404


def test_delete_image_removes_file_and_metadata(client, signup, monkeypatch, tmp_path):
    _, _, session = signup()
    from app.api import images

    monkeypatch.setattr(images, "get_settings", lambda: Settings(_env_file=None, selfie_storage_dir=tmp_path))
    created = post_image(client, bearer(session), image_bytes())
    image_id = created.json()["image"]["id"]
    assert len(list(tmp_path.iterdir())) == 1
    response = client.delete(f"/v1/images/{image_id}", headers=bearer(session))
    assert response.status_code == 204
    assert list(tmp_path.iterdir()) == []
    assert client.get(f"/v1/images/{image_id}", headers=bearer(session)).status_code == 404


def test_evaluation_reports_metrics_and_subgroups(tmp_path):
    import csv

    from scripts.evaluate_images import evaluate

    (tmp_path / "good.png").write_bytes(image_bytes("PNG"))
    (tmp_path / "bad.png").write_bytes(image_bytes("PNG", kind="dark"))
    manifest = tmp_path / "labels.csv"
    with manifest.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["path", "label", "split", "group"])
        writer.writeheader()
        writer.writerow({"path": "good.png", "label": "suitable", "split": "validation", "group": "camera_a"})
        writer.writerow({"path": "bad.png", "label": "unsuitable", "split": "validation", "group": "low_light"})
    report = evaluate(manifest, tmp_path, "validation")
    assert report["samples"] == 2
    assert report["precision"] == 1.0
    assert report["recall"] == 1.0
    assert set(report["groups"]) == {"camera_a", "low_light"}
    stricter = evaluate(manifest, tmp_path, "validation", min_blur_variance=1_000_000)
    assert stricter["recall"] < report["recall"]
