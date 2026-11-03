"""Eye colour, hair colour, contrast and recommendation features (behaviour on fixed fixtures).

Colour variations are painted onto the real portrait so the expected answer is known: the irises
(MediaPipe's iris circles) or the hair (dark, low-chroma pixels around the top of the head in this
fixture) are filled with a flat CIELAB colour.
"""

from __future__ import annotations

import json
from copy import deepcopy

import cv2
import numpy as np
import pytest
from PIL import Image

from app import schemas
from app.config import Settings
from app.services.appearance import analyze_appearance, recommendation_features
from app.services.color import lab_to_linear, linear_to_srgb, srgb8_to_lab
from app.services.face_region_data import FEATURE_LANDMARKS, REGION_LANDMARKS
from app.services.facial_attributes import (
    EYE_COLORS,
    HAIR_COLORS,
    AttributeUnavailable,
    analyze_eye_color,
    analyze_hair_color,
    classify_eye,
    classify_hair,
    feature_contrast,
)
from app.services.skin_analysis import prepare_scene
from tests.conftest import FIXTURES

PORTRAIT = np.asarray(Image.open(FIXTURES / "portrait.jpg").convert("RGB"))
H, W = PORTRAIT.shape[:2]
CFG = Settings(_env_file=None)


def srgb(lab) -> np.ndarray:
    return np.round(linear_to_srgb(lab_to_linear(np.asarray(lab, dtype=float))) * 255).astype(np.uint8)


def value_or_code(result: dict) -> str:
    return result.get("value") or result["error"]["code"]


@pytest.fixture(scope="module")
def face(face_analyzer):
    return face_analyzer.analyze(PORTRAIT)


@pytest.fixture(scope="module")
def baseline(face):
    return analyze_appearance(PORTRAIT, face, CFG)


@pytest.fixture(scope="module")
def pixels(face):
    return np.array([(p["px"], p["py"]) for p in face.landmarks])


@pytest.fixture(scope="module")
def hair_mask(face, pixels):
    oval = np.asarray(face.regions["face_oval"]["polyline"])
    centre = oval.mean(axis=0)
    up = pixels[REGION_LANDMARKS["forehead_top"][0]] - pixels[REGION_LANDMARKS["chin_bottom"][0]]
    length = np.linalg.norm(up)
    outer = np.zeros((H, W), np.uint8)
    cv2.fillPoly(outer, [(centre + (oval - centre) * 1.6 + up / length * 0.12 * length).astype(np.int32)], 1)
    inner = np.zeros((H, W), np.uint8)
    cv2.fillPoly(inner, [oval.astype(np.int32)], 1)
    lab = srgb8_to_lab(PORTRAIT.reshape(-1, 3)).reshape(H, W, 3)
    rows = np.mgrid[0:H, 0:W][0]
    mask = outer.astype(bool) & ~inner.astype(bool) & (rows < pixels[REGION_LANDMARKS["left_forehead_edge"][0]][1] + 10)
    mask &= (lab[..., 0] < 66) & (np.hypot(lab[..., 1], lab[..., 2]) < 12)
    return cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)


def paint_irises(pixels: np.ndarray, lab) -> np.ndarray:
    image = PORTRAIT.copy()
    for side in ("left", "right"):
        centre = pixels[FEATURE_LANDMARKS[f"{side}_iris_center"][0]]
        radius = np.mean(np.linalg.norm(pixels[list(FEATURE_LANDMARKS[f"{side}_iris"])] - centre, axis=1))
        mask = np.zeros((H, W), np.uint8)
        cv2.circle(mask, (round(centre[0]), round(centre[1])), round(radius), 1, -1)
        image[mask.astype(bool)] = srgb(lab)
    return image


# ── Output and integration ─────────────────────────────────────────────────


def test_appearance_output(baseline):
    attributes = baseline["attributes"]
    assert set(attributes) >= {"face_shape", "eye_color", "hair_color"}
    eye, hair = attributes["eye_color"], attributes["hair_color"]
    assert eye["status"] == "ok" and eye["value"] in EYE_COLORS and eye["label"] == "estimate"
    assert hair["status"] == "ok" and hair["value"] in HAIR_COLORS and hair["label"] == "estimate"
    assert 0 < eye["confidence"] <= 0.85 and 0 < hair["confidence"] <= 0.85  # never near-certain
    assert attributes["contrast"]["value"] in {"low", "medium", "high"}
    json.dumps(baseline)


def test_recommendation_features_feed_the_recommendation_engine(baseline):
    features = baseline["recommendation_features"]
    schemas.RecommendationFeatures(**features)  # strict schema: no extra or missing fields
    assert features["face_shape"]["value"] == baseline["attributes"]["face_shape"]["value"]
    assert features["undertone"]["value"] == baseline["skin"]["undertone"]["value"]
    assert features["skin_depth"]["value"] == baseline["skin"]["skin_tone"]["depth"]
    assert features["contrast"]["value"] == baseline["attributes"]["contrast"]["value"]


def test_recommendation_features_need_face_shape_and_skin(baseline):
    unavailable = {"status": "unavailable", "error": {"code": "X", "message": "x"}}
    assert recommendation_features(unavailable, baseline["attributes"]["face_shape"], None) is None
    assert recommendation_features(baseline["skin"], unavailable, None) is None
    without_contrast = recommendation_features(baseline["skin"], baseline["attributes"]["face_shape"], None)
    assert schemas.RecommendationFeatures(**without_contrast).contrast.value == "medium"  # the engine's default


# ── Eye colour ─────────────────────────────────────────────────────────────


def test_iris_centres_are_the_centres_of_their_rings(pixels):
    """Checks the topology the generator derives (centre = landmark before the documented ring)."""
    for side in ("left", "right"):
        centre = pixels[FEATURE_LANDMARKS[f"{side}_iris_center"][0]]
        ring = pixels[list(FEATURE_LANDMARKS[f"{side}_iris"])]
        assert np.linalg.norm(ring.mean(axis=0) - centre) < 1.5


def test_portrait_eyes(baseline):
    eye = baseline["attributes"]["eye_color"]
    assert eye["value"] == "dark_brown"
    assert eye["eyes"]["left"]["used"] and eye["eyes"]["right"]["used"]


@pytest.mark.parametrize(("lab", "expected"), [((45, -2, -22), "blue"), ((45, -18, 14), "green"), ((58, 8, 28), "hazel")])
def test_eye_colour_follows_iris_colour(face, pixels, lab, expected):
    image = paint_irises(pixels, lab)
    result = analyze_eye_color(face, prepare_scene(image, face, CFG), CFG)
    assert result["value"] == expected


def test_closed_or_covered_eyes_are_unavailable(face_analyzer, pixels):
    image = PORTRAIT.copy()
    for side in ("left", "right"):
        cv2.fillPoly(image, [pixels[list(FEATURE_LANDMARKS[f"{side}_eye"])].astype(np.int32)], (190, 140, 110))
    face = face_analyzer.analyze(image)
    with pytest.raises(AttributeUnavailable) as exc:
        analyze_eye_color(face, prepare_scene(image, face, CFG), CFG)
    assert exc.value.code == "EYES_NOT_VISIBLE"


def test_tiny_irises_are_unavailable(face_analyzer):
    small = cv2.resize(PORTRAIT, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    face = face_analyzer.analyze(small)
    with pytest.raises(AttributeUnavailable):
        analyze_eye_color(face, prepare_scene(small, face, CFG), CFG)


def test_classify_eye_table():
    assert classify_eye(np.array([20, 6, 5])) == "dark_brown"
    assert classify_eye(np.array([42, 10, 20])) == "brown"
    assert classify_eye(np.array([55, 8, 25])) == "hazel"
    assert classify_eye(np.array([50, -15, 10])) == "green"
    assert classify_eye(np.array([50, -3, -20])) == "blue"
    assert classify_eye(np.array([55, 0, -2])) == "gray"


# ── Hair colour ────────────────────────────────────────────────────────────


def test_portrait_hair_is_achromatic(baseline):
    hair = baseline["attributes"]["hair_color"]
    assert hair["value"] in {"black", "gray"}
    assert np.hypot(hair["lab"]["a"], hair["lab"]["b"]) < 6


@pytest.mark.parametrize(
    ("lab", "expected"),
    [
        ((70, 4, 30), "blonde"),
        ((72, 6, 38), "blonde"),
        ((50, 30, 42), "red"),
        ((12, 1, 1), "black"),
        ((40, 8, 18), "brown"),
        ((62, 0, 1), "gray"),
        ((40, 5, -30), "other"),
    ],
    ids=["blonde", "golden-blonde", "ginger", "black", "brown", "gray", "blue-dye"],
)
def test_hair_colour_follows_hair(face_analyzer, face, hair_mask, lab, expected):
    image = PORTRAIT.copy()
    image[hair_mask] = srgb(lab)
    result = analyze_appearance(image, face, CFG)["attributes"]["hair_color"]
    assert value_or_code(result) == expected


def test_red_hair_against_red_curtains_is_not_guessed(face, hair_mask):
    """The portrait's background is red curtains: hair of the same colour can't be told apart."""
    image = PORTRAIT.copy()
    image[hair_mask] = srgb((38, 30, 32))
    result = analyze_appearance(image, face, CFG)["attributes"]["hair_color"]
    assert value_or_code(result) == "HAIR_NOT_SEPARABLE"


def test_hair_the_colour_of_skin_is_not_visible(face, hair_mask, baseline):
    skin = baseline["skin"]["skin_tone"]["lab"]
    skin_lab = np.array([skin["l"], skin["a"], skin["b"]])
    image = PORTRAIT.copy()
    image[hair_mask] = srgb(skin_lab)  # a shaved head or a skin-coloured covering
    with pytest.raises(AttributeUnavailable) as exc:
        analyze_hair_color(face, prepare_scene(image, face, CFG), skin_lab, CFG)
    assert exc.value.code == "HAIR_NOT_VISIBLE"


def test_hair_matching_the_background_is_not_separable(face, hair_mask, baseline, pixels):
    skin = baseline["skin"]["skin_tone"]["lab"]
    skin_lab = np.array([skin["l"], skin["a"], skin["b"]])
    image = PORTRAIT.copy()
    hair_rgb = srgb((30, 1, 2))
    image[hair_mask] = hair_rgb
    image[: int(pixels[REGION_LANDMARKS["left_forehead_edge"][0]][1])] = np.where(
        hair_mask[: int(pixels[REGION_LANDMARKS["left_forehead_edge"][0]][1]), :, None],
        image[: int(pixels[REGION_LANDMARKS["left_forehead_edge"][0]][1])],
        hair_rgb,
    )  # everything above the temples outside the hair becomes the same colour
    with pytest.raises(AttributeUnavailable) as exc:
        analyze_hair_color(face, prepare_scene(image, face, CFG), skin_lab, CFG)
    assert exc.value.code in {"HAIR_NOT_SEPARABLE", "HAIR_NOT_VISIBLE"}


def test_hair_on_a_tilted_head(face_analyzer):
    matrix = cv2.getRotationMatrix2D((W / 2, H / 2), 20, 1.0)
    tilted = cv2.warpAffine(PORTRAIT, matrix, (W, H), borderMode=cv2.BORDER_REPLICATE)
    result = analyze_appearance(tilted, face_analyzer.analyze(tilted), CFG)["attributes"]["hair_color"]
    assert value_or_code(result) in {"black", "gray"}


def test_classify_hair_table():
    assert classify_hair(np.array([10, 1, 1])) == "black"
    assert classify_hair(np.array([50, 0, 2])) == "gray"
    assert classify_hair(np.array([85, 0, 2])) == "white"
    assert classify_hair(np.array([25, 6, 12])) == "dark_brown"
    assert classify_hair(np.array([40, 8, 18])) == "brown"
    assert classify_hair(np.array([52, 8, 16])) == "light_brown"
    assert classify_hair(np.array([68, 4, 30])) == "blonde"
    assert classify_hair(np.array([40, 30, 30])) == "red"
    assert classify_hair(np.array([50, 30, 42])) == "red"  # ginger
    assert classify_hair(np.array([60, 18, 32])) == "blonde"  # strawberry blonde: not saturated enough for red
    assert classify_hair(np.array([45, 20, -25])) == "other"


# ── Contrast ───────────────────────────────────────────────────────────────


def test_feature_contrast(baseline):
    skin = deepcopy(baseline["skin"])
    skin["skin_tone"]["lab"]["l"] = 70.0
    hair = {"status": "ok", "lab": {"l": 15.0, "a": 0, "b": 0}, "confidence": 0.6}
    eyes = {"status": "ok", "lab": {"l": 62.0, "a": 0, "b": 0}, "confidence": 0.6}
    assert feature_contrast(skin, hair, eyes, CFG)["value"] == "high"
    assert feature_contrast(skin, eyes | {"lab": {"l": 60.0, "a": 0, "b": 0}}, eyes, CFG)["value"] == "low"
    no_hair = {"status": "unavailable"}
    result = feature_contrast(skin, no_hair, eyes, CFG)
    assert result["source"] == "eyes" and result["value"] == "low"
    assert feature_contrast({"status": "unavailable"}, hair, eyes, CFG) is None
    assert feature_contrast(skin, no_hair, no_hair, CFG) is None
