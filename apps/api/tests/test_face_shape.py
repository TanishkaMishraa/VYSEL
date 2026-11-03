"""Face-shape measurements and classification (behaviour on fixed fixtures, not accuracy)."""

from __future__ import annotations

import importlib.util
import json
import sys
from copy import deepcopy

import cv2
import numpy as np
import pytest
from PIL import Image

from app.config import Settings
from app.services.face_shape import (
    CANONICAL,
    DEFAULT_PROTOTYPES,
    DEFAULT_SPREAD,
    FEATURES,
    SHAPES,
    FaceShapeUnavailable,
    analyze_face_shape,
    canonical_reference,
    classify,
    features,
    measure,
)
from tests.conftest import API_DIR, FIXTURES

PORTRAIT = np.asarray(Image.open(FIXTURES / "portrait.jpg").convert("RGB"))
H, W = PORTRAIT.shape[:2]
CFG = Settings(_env_file=None)


def _canonical_vertices() -> np.ndarray:
    spec = importlib.util.spec_from_file_location("generate_face_regions", API_DIR / "scripts" / "generate_face_regions.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.load_canonical()


@pytest.fixture(scope="module")
def baseline(face_analyzer):
    face = face_analyzer.analyze(PORTRAIT)
    return face, analyze_face_shape(face, CFG)


def test_canonical_reference_constants_match_the_model():
    assert canonical_reference(_canonical_vertices()) == pytest.approx(CANONICAL, abs=1e-3)


def test_the_canonical_face_has_zero_features_and_reads_as_oval():
    values = features(measure(_canonical_vertices()))
    assert all(abs(v) < 1e-3 for v in values.values())
    assert next(iter(classify(values, CFG))) == "oval"  # the average face is the "balanced" shape


@pytest.mark.parametrize("shape", SHAPES)
def test_each_prototype_classifies_as_itself(shape):
    values = {f: DEFAULT_PROTOTYPES[shape][i] * DEFAULT_SPREAD[f] for i, f in enumerate(FEATURES)}
    probabilities = classify(values, CFG)
    assert next(iter(probabilities)) == shape
    assert sum(probabilities.values()) == pytest.approx(1)
    assert list(probabilities.values()) == sorted(probabilities.values(), reverse=True)


def test_output_shape(baseline):
    _, result = baseline
    assert result["status"] == "ok" and result["value"] in SHAPES and result["label"] == "estimate"
    assert 0 < result["confidence"] <= 1 and len(result["alternatives"]) == 2
    assert {a["value"] for a in result["alternatives"]} <= set(SHAPES) - {result["value"]}
    assert set(result["measurements"]) == {"length_ratio", "forehead_ratio", "jaw_ratio", "chin_angle"}
    assert set(result["features"]) == set(FEATURES)
    assert 0.8 < result["measurements"]["length_ratio"] < 1.8 and 0.6 < result["measurements"]["jaw_ratio"] < 1.1
    json.dumps(result)


def test_deterministic(baseline):
    face, result = baseline
    assert analyze_face_shape(face, CFG) == result


@pytest.mark.parametrize("scale", [1.15, 0.85])
def test_longer_or_shorter_faces_move_the_length_feature(face_analyzer, baseline, scale):
    _, upright = baseline
    image = cv2.resize(PORTRAIT, (W, round(H * scale)))
    result = analyze_face_shape(face_analyzer.analyze(image), CFG)
    direction = 1 if scale > 1 else -1
    assert direction * (result["features"]["length"] - upright["features"]["length"]) > 0.08
    assert direction * (result["probabilities"]["oblong"] - upright["probabilities"]["oblong"]) > 0
    # Widths are unaffected by a vertical stretch.
    assert abs(result["features"]["jaw"] - upright["features"]["jaw"]) < 0.03


def test_3d_measurements_survive_head_tilt(face_analyzer, baseline):
    _, upright = baseline
    matrix = cv2.getRotationMatrix2D((W / 2, H / 2), 20, 1.0)
    tilted = cv2.warpAffine(PORTRAIT, matrix, (W, H), borderMode=cv2.BORDER_REPLICATE)
    face = face_analyzer.analyze(tilted)
    result = analyze_face_shape(face, CFG)
    for name in ("length", "forehead", "jaw"):
        assert abs(result["features"][name] - upright["features"][name]) < 0.04, name
    if any(w["code"] == "HIGH_HEAD_ROTATION" for w in face.warnings):
        assert {w["code"] for w in result["warnings"]} == {"FACE_SHAPE_POSE"}
        assert result["confidence"] < max(result["probabilities"].values())


def test_face_cut_off_by_the_frame_is_unavailable(face_analyzer, baseline):
    x0 = int(baseline[0].key_points["nose_tip"]["px"]) - 60
    with pytest.raises(FaceShapeUnavailable) as exc:
        analyze_face_shape(face_analyzer.analyze(np.ascontiguousarray(PORTRAIT[:, x0:])), CFG)
    assert exc.value.code == "FACE_NOT_FULLY_VISIBLE"


def test_fitted_prototypes_file_is_used(tmp_path, baseline):
    face, _ = baseline
    model = tmp_path / "prototypes.json"
    model.write_text(json.dumps({"prototypes": {"round": [0, 0, 0, 0], "heart": [9, 9, 9, 9]}, "spread": DEFAULT_SPREAD}))
    result = analyze_face_shape(deepcopy(face), Settings(_env_file=None, face_shape_prototypes_path=model))
    assert set(result["probabilities"]) == {"round", "heart"} and result["value"] == "round"
