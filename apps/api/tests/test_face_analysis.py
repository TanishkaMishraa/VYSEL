"""Face detection and landmark extraction with the real MediaPipe model on fixed fixtures.

Harder conditions are derived from real fixture faces (rotation, tilt, scale, compression,
occlusion, crop, aspect ratio) so the expected landmarks are known exactly. Tolerances are a
few times the measured error, expressed as mean landmark error / face width (NME).
"""

from __future__ import annotations

import io
import re

import cv2
import numpy as np
import pytest
from PIL import Image

from app.config import Settings
from app.services.face_analysis import (
    LANDMARK_COUNT,
    FaceAnalysisError,
    FaceAnalyzer,
    FaceModelUnavailable,
    _unrotate,
)
from app.services.face_regions import AREA_REGIONS
from tests.conftest import FIXTURES


def load(name: str) -> np.ndarray:
    return np.asarray(Image.open(FIXTURES / name).convert("RGB"))


def jpeg(pixels: np.ndarray, quality: int = 92, orientation: int | None = None) -> bytes:
    image = Image.fromarray(pixels)
    stream = io.BytesIO()
    exif = image.getexif()
    if orientation:
        exif[0x0112] = orientation
    image.save(stream, "JPEG", quality=quality, exif=exif.tobytes())
    return stream.getvalue()


def pixels_of(result) -> np.ndarray:
    return np.array([(p["px"], p["py"]) for p in result.landmarks])


PORTRAIT = load("portrait.jpg")
H, W = PORTRAIT.shape[:2]


@pytest.fixture(scope="module")
def baseline(face_analyzer):
    result = face_analyzer.analyze(PORTRAIT)
    oval = np.array(result.regions["face_oval"]["polyline"])
    return result, pixels_of(result), float(oval[:, 0].max() - oval[:, 0].min())


def nme(points: np.ndarray, expected: np.ndarray, face_width: float) -> float:
    return float(np.linalg.norm(points - expected, axis=1).mean() / face_width)


# ── One face, landmarks, regions ───────────────────────────────────────────


def test_single_face_landmarks_and_bounds(baseline):
    result, points, _ = baseline
    assert result.face_count == 1
    assert len(result.landmarks) == LANDMARK_COUNT
    assert [p["index"] for p in result.landmarks] == list(range(LANDMARK_COUNT))
    for p in result.landmarks:
        assert 0 <= p["x"] <= 1 and 0 <= p["y"] <= 1  # face fully in frame
        assert 0 <= p["px"] <= W and 0 <= p["py"] <= H
        assert np.isfinite(p["z"]) and abs(p["z"]) < 1
        assert p["px"] == pytest.approx(p["x"] * W, abs=0.1) and p["py"] == pytest.approx(p["y"] * H, abs=0.1)
    assert result.detection["confidence"] >= 0.5
    box = result.detection["bounding_box"]
    assert box["x"] <= points[:, 0].mean() <= box["x"] + box["width"]
    assert result.warnings == []
    assert (result.image_width, result.image_height) == (W, H)


def test_matches_mediapipe_published_expected_landmarks(baseline):
    """Regression against MediaPipe's own expected output, with MediaPipe's tolerance (0.03)."""
    text = (FIXTURES / "portrait_expected_face_landmarks.pbtxt").read_text()
    expected = np.array([(float(x), float(y)) for x, y in re.findall(r"x: ([-\d.e]+)\s+y: ([-\d.e]+)", text)])
    got = np.array([(p["x"], p["y"]) for p in baseline[0].landmarks])
    assert expected.shape == got.shape == (LANDMARK_COUNT, 2)
    assert np.abs(got - expected).max() < 0.03


def test_regions_land_on_the_right_parts_of_the_face(baseline):
    result, points, _ = baseline
    r = result.regions
    oval = np.array(r["face_oval"]["polyline"], dtype=np.float32)
    for name in AREA_REGIONS:
        assert r[name]["visible"] is True and r[name]["in_frame_ratio"] == 1.0
        for x, y in r[name]["polygon"]:
            assert cv2.pointPolygonTest(oval, (x, y), measureDist=True) > -2, name  # inside the face
    nose = result.key_points["nose_tip"]
    # Subject's left cheek appears on the image's right in an unmirrored photo.
    assert r["left_cheek"]["centroid"][0] > nose["px"] > r["right_cheek"]["centroid"][0]
    eyes_y = points[[33, 263]][:, 1].mean()
    assert r["forehead"]["centroid"][1] < eyes_y < r["left_cheek"]["centroid"][1] < r["chin"]["centroid"][1]
    assert result.key_points["forehead_top"]["py"] < result.key_points["chin_bottom"]["py"]
    jaw = r["jawline"]["polyline"]
    assert jaw[0][0] < jaw[-1][0]  # subject's right ear (image left) -> left ear


def test_output_is_deterministic(face_analyzer, baseline):
    again = face_analyzer.analyze(PORTRAIT)
    assert again.landmarks == baseline[0].landmarks
    assert again.regions == baseline[0].regions


# ── Rejections ─────────────────────────────────────────────────────────────


def test_no_face(face_analyzer):
    with pytest.raises(FaceAnalysisError) as exc:
        face_analyzer.analyze_bytes((FIXTURES / "cat.jpg").read_bytes())
    assert exc.value.code == "NO_FACE_DETECTED" and exc.value.face_count == 0


def test_no_face_in_plain_texture(face_analyzer):
    texture = np.random.default_rng(42).integers(30, 220, (512, 512, 3), dtype=np.uint8)
    with pytest.raises(FaceAnalysisError) as exc:
        face_analyzer.analyze(texture)
    assert exc.value.code == "NO_FACE_DETECTED"


@pytest.mark.parametrize("layout", ["side_by_side", "stacked", "wide_frame"])
def test_multiple_faces(face_analyzer, layout):
    if layout == "side_by_side":
        image = np.concatenate([PORTRAIT, PORTRAIT[:, ::-1]], axis=1)
    elif layout == "stacked":
        image = np.concatenate([PORTRAIT, PORTRAIT], axis=0)
    else:
        image = np.full((H, H * 4, 3), 120, np.uint8)
        image[:, 50 : 50 + W] = PORTRAIT
        image[:, H * 3 : H * 3 + W] = PORTRAIT
    with pytest.raises(FaceAnalysisError) as exc:
        face_analyzer.analyze(np.ascontiguousarray(image))
    assert exc.value.code == "MULTIPLE_FACES_DETECTED" and exc.value.face_count == 2


def test_rejects_non_rgb_arrays(face_analyzer):
    with pytest.raises(ValueError):
        face_analyzer.analyze(np.zeros((64, 64), np.uint8))
    with pytest.raises(ValueError):
        face_analyzer.analyze(np.zeros((64, 64, 3), np.float32))


# ── Rotation, tilt and orientation ─────────────────────────────────────────


@pytest.mark.parametrize("k", [1, 2, 3])
def test_quarter_turns_are_found_and_mapped_back(face_analyzer, baseline, k):
    _, upright, width = baseline
    result = face_analyzer.analyze(np.ascontiguousarray(np.rot90(PORTRAIT, k)))
    h, w = np.rot90(PORTRAIT, k).shape[:2]
    # Where the upright landmarks land in the rotated image (inverse of _unrotate).
    expected = upright / [W, H]
    for _ in range(k):
        expected = np.stack([expected[:, 1], 1 - expected[:, 0]], axis=1)
    assert nme(pixels_of(result), expected * [w, h], width) < 0.02
    codes = {w["code"] for w in result.warnings}
    assert "HIGH_HEAD_ROTATION" in codes
    assert abs(result.head_pose["roll"]) > 60


def test_unrotate_inverts_rot90():
    rng = np.random.default_rng(0)
    points = rng.random((20, 2))
    for k in (1, 2, 3):
        rotated = points.copy()
        for _ in range(k):
            rotated = np.stack([rotated[:, 1], 1 - rotated[:, 0]], axis=1)
        np.testing.assert_allclose(_unrotate(rotated, k), points, atol=1e-12)


def test_sideways_fixture_without_exif(face_analyzer):
    result = face_analyzer.analyze_bytes((FIXTURES / "portrait_rotated.jpg").read_bytes())
    assert result.face_count == 1
    assert abs(abs(result.head_pose["roll"]) - 90) < 10


def test_exif_orientation_is_applied(face_analyzer, baseline):
    # Store the portrait rotated on disk with EXIF orientation 6 ("rotate 90 CW to display").
    stored = np.ascontiguousarray(np.rot90(PORTRAIT, 1))
    result = face_analyzer.analyze_bytes(jpeg(stored, orientation=6))
    assert result.orientation_corrected is True
    assert (result.image_width, result.image_height) == (W, H)
    assert nme(pixels_of(result), baseline[1], baseline[2]) < 0.02
    assert result.rotation_applied == 0


@pytest.mark.parametrize("degrees", [15, 30])
def test_tilted_faces(face_analyzer, baseline, degrees):
    _, upright, width = baseline
    matrix = cv2.getRotationMatrix2D((W / 2, H / 2), degrees, 1.0)
    tilted = cv2.warpAffine(PORTRAIT, matrix, (W, H), borderMode=cv2.BORDER_REPLICATE)
    result = face_analyzer.analyze(tilted)
    expected = np.c_[upright, np.ones(len(upright))] @ matrix.T
    assert nme(pixels_of(result), expected, width) < 0.05
    assert abs(abs(result.head_pose["roll"]) - degrees) < 8


# ── Image quality, occlusion, framing ──────────────────────────────────────


@pytest.mark.parametrize("scale", [0.5, 0.25])
def test_low_resolution_faces_warn(face_analyzer, baseline, scale):
    small = cv2.resize(PORTRAIT, (round(W * scale), round(H * scale)), interpolation=cv2.INTER_AREA)
    result = face_analyzer.analyze(small)
    assert nme(pixels_of(result) / scale, baseline[1], baseline[2]) < 0.04
    assert "FACE_LOW_RESOLUTION" in {w["code"] for w in result.warnings}


def test_heavy_compression_and_blur(face_analyzer, baseline):
    degraded = jpeg(cv2.GaussianBlur(PORTRAIT, (9, 9), 3), quality=8)
    result = face_analyzer.analyze_bytes(degraded)
    assert nme(pixels_of(result), baseline[1], baseline[2]) < 0.04


def test_partially_occluded_lower_face(face_analyzer, baseline):
    result0, upright, width = baseline
    occluded = PORTRAIT.copy()
    nose_y = int(result0.key_points["nose_tip"]["py"])
    chin_y = int(result0.key_points["chin_bottom"]["py"])
    occluded[nose_y + 10 : chin_y + 20, 300:520] = 128  # e.g. a hand or scarf over mouth and chin
    result = face_analyzer.analyze(occluded)
    upper = upright[:, 1] < nose_y
    assert result.face_count == 1
    assert nme(pixels_of(result)[upper], upright[upper], width) < 0.04


def test_face_cut_by_the_frame_marks_regions_not_visible(face_analyzer, baseline):
    x0 = int(baseline[0].key_points["nose_tip"]["px"]) - 60
    result = face_analyzer.analyze(np.ascontiguousarray(PORTRAIT[:, x0:]))
    codes = {w["code"] for w in result.warnings}
    assert {"FACE_PARTIALLY_OUT_OF_FRAME", "REGION_NOT_VISIBLE"} <= codes
    assert result.regions["right_cheek"]["visible"] is False  # subject's right is on the cut side
    assert result.regions["left_cheek"]["visible"] is True
    assert min(p["x"] for p in result.landmarks) < 0  # coordinates are preserved, not clamped


@pytest.mark.parametrize("ratio", [2, 4, 6])
def test_unusual_aspect_ratios(face_analyzer, baseline, ratio):
    frame = np.full((H, H * ratio, 3), 120, np.uint8)
    x0 = (H * ratio - W) // 3
    frame[:, x0 : x0 + W] = PORTRAIT
    result = face_analyzer.analyze(frame)
    assert result.face_count == 1
    assert nme(pixels_of(result) - [x0, 0], baseline[1], baseline[2]) < 0.03


def test_tall_frame(face_analyzer, baseline):
    frame = np.full((H * 3, W, 3), 120, np.uint8)
    frame[H : 2 * H] = PORTRAIT
    result = face_analyzer.analyze(frame)
    assert nme(pixels_of(result) - [0, H], baseline[1], baseline[2]) < 0.03


def test_large_images_are_downscaled_for_inference_but_reported_full_size(face_analyzer, baseline):
    big = cv2.resize(PORTRAIT, (W * 3, H * 3), interpolation=cv2.INTER_CUBIC)
    result = face_analyzer.analyze(big)
    assert (result.image_width, result.image_height) == (W * 3, H * 3)
    assert nme(pixels_of(result) / 3, baseline[1], baseline[2]) < 0.02


# ── Model lifecycle ────────────────────────────────────────────────────────


def test_missing_or_tampered_model_is_unavailable(tmp_path):
    with pytest.raises(FaceModelUnavailable, match="setup_face_analysis"):
        FaceAnalyzer(Settings(_env_file=None, face_model_path=tmp_path / "missing.task"))
    bad = tmp_path / "bad.task"
    bad.write_bytes(b"not the pinned model")
    with pytest.raises(FaceModelUnavailable, match="SHA-256"):
        FaceAnalyzer(Settings(_env_file=None, face_model_path=bad))


def test_closed_analyzer_refuses_work(face_analyzer):
    analyzer = FaceAnalyzer(face_analyzer.settings)
    with analyzer:
        assert analyzer.analyze(PORTRAIT).face_count == 1
    with pytest.raises(FaceModelUnavailable):
        analyzer.analyze(PORTRAIT)
    analyzer.close()  # idempotent
