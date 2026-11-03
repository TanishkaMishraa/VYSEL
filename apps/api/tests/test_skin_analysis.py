"""Skin colour and undertone estimation on fixed fixtures and controlled, derived variations.

Variations are applied to a real face so their effect is known exactly: a lighting cast is a
per-channel gain in linear light, darker skin is a linear-light scale of the face pixels, and an
undertone shift is a CIELAB a*/b* offset. These test the method's behaviour, not its accuracy
across people (see SKIN_ANALYSIS.md).
"""

from __future__ import annotations

import json
from copy import deepcopy

import cv2
import numpy as np
import pytest
from PIL import Image

from app.config import Settings
from app.services.color import delta_e_2000, lab_to_linear, linear_to_srgb, srgb8_to_lab, srgb_to_linear
from app.services.skin_analysis import (
    _MONK_LAB,
    ITA_CATEGORIES,
    MONK_SCALE,
    SkinAnalysisUnavailable,
    analyze_skin,
    classify_undertone,
    ita_category,
    nearest_monk,
)
from tests.conftest import FIXTURES

PORTRAIT = np.asarray(Image.open(FIXTURES / "portrait.jpg").convert("RGB"))
CFG = Settings(_env_file=None)


def lab_of(result) -> np.ndarray:
    lab = result["skin_tone"]["lab"]
    return np.array([lab["l"], lab["a"], lab["b"]])


def cast(image: np.ndarray, gains) -> np.ndarray:
    return np.round(linear_to_srgb(srgb_to_linear(image / 255) * np.array(gains)) * 255).astype(np.uint8)


@pytest.fixture(scope="module")
def face(face_analyzer):
    return face_analyzer.analyze(PORTRAIT)


@pytest.fixture(scope="module")
def baseline(face):
    return analyze_skin(PORTRAIT, face, CFG)


@pytest.fixture(scope="module")
def face_mask(face):
    mask = np.zeros(PORTRAIT.shape[:2], np.uint8)
    cv2.fillPoly(mask, [np.asarray(face.regions["face_oval"]["polyline"]).astype(np.int32)], 1)
    return mask.astype(bool)


def recolour_face(mask: np.ndarray, *, scale: float = 1.0, shift=(0.0, 0.0)) -> np.ndarray:
    """Change only the face's skin: darker (linear-light scale) and/or a*/b* shifted."""
    image = PORTRAIT.copy()
    lab = srgb8_to_lab(image[mask]) + [0, *shift]
    image[mask] = np.round(linear_to_srgb(lab_to_linear(lab) * scale) * 255).astype(np.uint8)
    return image


# ── Output structure ───────────────────────────────────────────────────────


def test_output_matches_the_contract_shape(baseline):
    assert baseline["status"] == "ok"
    tone = baseline["skin_tone"]
    assert set(tone) >= {"hex", "lab", "depth", "confidence", "label"}  # SkinTone in docs/api/openapi.yaml
    assert tone["label"] == "estimate" and 0 <= tone["confidence"] <= 1
    assert tone["depth"] in {"fair", "light", "medium", "tan", "deep"}
    assert tone["hex"].startswith("#") and len(tone["hex"]) == 7
    assert 1 <= tone["monk"]["value"] <= 10 and tone["monk"]["hex"] == MONK_SCALE[tone["monk"]["value"] - 1]
    undertone = baseline["undertone"]
    assert undertone["value"] in {"warm", "cool", "neutral"} and undertone["label"] == "estimate"
    assert 0 <= undertone["confidence"] <= 1
    assert abs(sum(c["share"] for c in baseline["clusters"]) - 1) < 1e-3
    assert {"forehead", "left_cheek", "right_cheek", "chin"} == set(baseline["regions"])
    assert all(region["used"] for region in baseline["regions"].values())
    assert baseline["pixels_used"] >= CFG.skin_min_pixels
    json.dumps(baseline)  # JSON-serializable for storage


def test_skin_colour_is_plausible_and_consistent_with_its_category(baseline):
    lab = lab_of(baseline)
    assert 20 < lab[0] < 95 and 0 < lab[1] < 30 and 5 < lab[2] < 40  # skin sits in the red-yellow quadrant
    category, depth = ita_category(baseline["skin_tone"]["ita_degrees"])
    assert (category, depth) == (baseline["skin_tone"]["ita_category"], baseline["skin_tone"]["depth"])


def test_deterministic(face, baseline):
    assert analyze_skin(PORTRAIT, face, CFG) == baseline


def test_cluster_count_barely_moves_the_estimate(face, baseline):
    for k in (2, 4):
        other = analyze_skin(PORTRAIT, face, Settings(_env_file=None, skin_kmeans_clusters=k))
        assert float(delta_e_2000(lab_of(other), lab_of(baseline))) < 3


# ── Colour correction ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "gains", "max_corrected_error"),
    [("tungsten", (1.25, 1.0, 0.75), 2.0), ("shade", (0.85, 1.0, 1.2), 3.0), ("fluorescent", (0.9, 1.1, 0.9), 2.5)],
)
def test_white_balance_reduces_colour_cast_error(face_analyzer, baseline, name, gains, max_corrected_error):
    image = cast(PORTRAIT, gains)
    face = face_analyzer.analyze(image)
    corrected = analyze_skin(image, face, CFG)
    uncorrected = analyze_skin(image, face, Settings(_env_file=None, skin_white_balance="none"))
    error_off = float(delta_e_2000(lab_of(uncorrected), lab_of(baseline)))
    error_on = float(delta_e_2000(lab_of(corrected), lab_of(baseline)))
    assert error_on < error_off / 2, name
    assert error_on < max_corrected_error, name
    assert corrected["undertone"]["confidence"] < baseline["undertone"]["confidence"]  # correction = uncertainty


def test_strong_cast_is_flagged_and_undertone_confidence_capped(face_analyzer):
    image = cast(PORTRAIT, (1.5, 1.0, 0.6))
    result = analyze_skin(image, face_analyzer.analyze(image), CFG)
    assert result["color_correction"]["clamped"] is True
    assert {w["code"] for w in result["warnings"]} >= {"STRONG_COLOR_CAST", "LOW_CONFIDENCE_UNDERTONE"}
    assert result["undertone"]["confidence"] <= 0.3


def test_white_balance_ignores_the_face_itself(face, baseline, face_mask):
    """Only background pixels feed the illuminant estimate, so recolouring the skin leaves the gains alone."""
    darker_skin = analyze_skin(recolour_face(face_mask, scale=0.3), face, CFG)
    assert darker_skin["color_correction"]["gains"] == pytest.approx(baseline["color_correction"]["gains"], abs=0.02)


# ── Skin pixels and occlusion ──────────────────────────────────────────────


@pytest.mark.parametrize("colour", [(70, 90, 140), (235, 200, 180)], ids=["scarf", "pale-hand"])
def test_covered_cheek_is_detected_and_excluded(face_analyzer, baseline, face, colour):
    image = PORTRAIT.copy()
    box = face.regions["right_cheek"]["bounding_box"]
    image[int(box["y"]) - 5 : int(box["y"] + box["height"]) + 5, int(box["x"]) - 5 : int(box["x"] + box["width"]) + 5] = colour
    result = analyze_skin(image, face_analyzer.analyze(image), CFG)
    assert result["regions"]["right_cheek"] == {"used": False, "reason": "color_inconsistent", "pixels": pytest.approx(2000, rel=0.5)}
    assert "REGION_COLOR_INCONSISTENT" in {w["code"] for w in result["warnings"]}
    assert float(delta_e_2000(lab_of(result), lab_of(baseline))) < 2


def test_regions_marked_not_visible_are_not_sampled(face, baseline):
    partial = deepcopy(face)
    partial.regions["left_cheek"]["visible"] = False
    result = analyze_skin(PORTRAIT, partial, CFG)
    assert result["regions"]["left_cheek"] == {"used": False, "reason": "not_visible", "pixels": 0}
    assert float(delta_e_2000(lab_of(result), lab_of(baseline))) < 3


def test_no_visible_skin_is_unavailable(face):
    hidden = deepcopy(face)
    for name in ("forehead", "left_cheek", "right_cheek", "chin"):
        hidden.regions[name]["visible"] = False
    with pytest.raises(SkinAnalysisUnavailable) as exc:
        analyze_skin(PORTRAIT, hidden, CFG)
    assert exc.value.code == "NO_VISIBLE_SKIN"
    assert exc.value.as_json()["status"] == "unavailable"


def test_clipped_highlights_are_excluded(face, baseline):
    image = PORTRAIT.copy()
    box = face.regions["forehead"]["bounding_box"]
    image[int(box["y"]) : int(box["y"] + box["height"] / 2), int(box["x"]) : int(box["x"] + box["width"])] = 255  # blown-out shine
    result = analyze_skin(image, face, CFG)
    assert result["regions"]["forehead"]["pixels"] < baseline["regions"]["forehead"]["pixels"]
    assert float(delta_e_2000(lab_of(result), lab_of(baseline))) < 2


def test_rejects_an_image_that_is_not_the_scanned_one(face):
    with pytest.raises(ValueError):
        analyze_skin(PORTRAIT[:500], face, CFG)


# ── Skin tone across depth ─────────────────────────────────────────────────


def test_darker_skin_moves_tone_monotonically_and_leaves_undertone_alone(face, baseline, face_mask):
    results = [baseline] + [analyze_skin(recolour_face(face_mask, scale=s), face, CFG) for s in (0.7, 0.45, 0.25, 0.12)]
    lightness = [r["skin_tone"]["lab"]["l"] for r in results]
    ita = [r["skin_tone"]["ita_degrees"] for r in results]
    monk = [r["skin_tone"]["monk"]["value"] for r in results]
    assert lightness == sorted(lightness, reverse=True) and ita == sorted(ita, reverse=True)
    assert monk == sorted(monk) and monk[-1] >= 7
    assert results[-1]["skin_tone"]["depth"] == "deep"
    # Darkening keeps chromaticity, so the undertone class must not drift with depth.
    assert {r["undertone"]["value"] for r in results} == {baseline["undertone"]["value"]}


def test_monk_and_ita_reference_tables():
    for value in range(1, 11):
        assert nearest_monk(_MONK_LAB[value - 1]) == (value, pytest.approx(0, abs=1e-9))
    thresholds = [t for t, _, _ in ITA_CATEGORIES]
    assert thresholds == sorted(thresholds, reverse=True)
    assert ita_category(60) == ("very_light", "fair") and ita_category(-45) == ("dark", "deep")
    assert ita_category(30) == ("intermediate", "medium") and ita_category(0) == ("brown", "deep")


# ── Undertone ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("shift", "expected"), [((0, 6), "warm"), ((6, 0), "cool"), ((5, -4), "cool")], ids=["yellower", "redder", "pinker"]
)
def test_undertone_follows_hue_shifts(face, face_mask, baseline, shift, expected):
    result = analyze_skin(recolour_face(face_mask, shift=shift), face, CFG)
    assert result["undertone"]["value"] == expected
    direction = 1 if expected == "warm" else -1
    assert direction * (result["undertone"]["delta_h"] - baseline["undertone"]["delta_h"]) > 2


def test_classify_undertone_bands():
    cfg = Settings(_env_file=None, skin_undertone_reference_hue=55, skin_undertone_neutral_delta_h=2.5)

    def at_hue(hue, c=25.0, lightness=65.0):
        return np.array([lightness, c * np.cos(np.radians(hue)), c * np.sin(np.radians(hue))])

    assert classify_undertone(at_hue(55), cfg)[0] == "neutral"
    assert classify_undertone(at_hue(65), cfg)[0] == "warm"
    assert classify_undertone(at_hue(45), cfg)[0] == "cool"
    # The same 10 degree hue offset is "neutral" at low chroma: undertone is hard to judge there.
    assert classify_undertone(at_hue(65, c=8), cfg)[0] == "neutral"
    # Confidence is lowest at a class boundary and grows with distance from it.
    boundary = 55 + np.degrees(2 * np.arcsin(2.5 / (2 * 25)))
    assert classify_undertone(at_hue(boundary + 0.01), cfg)[1] == pytest.approx(0.5, abs=0.01)
    assert classify_undertone(at_hue(55), cfg)[1] > classify_undertone(at_hue(58), cfg)[1]


def test_fitted_reference_curve_is_used(tmp_path):
    curve = tmp_path / "reference.json"
    curve.write_text(json.dumps({"points": [[30, 45.0], [80, 65.0]]}))
    cfg = Settings(_env_file=None, skin_undertone_reference_path=curve)
    lab_dark = np.array([30, 25 * np.cos(np.radians(45)), 25 * np.sin(np.radians(45))])
    lab_light = np.array([80, 25 * np.cos(np.radians(65)), 25 * np.sin(np.radians(65))])
    for lab in (lab_dark, lab_light):
        value, _, dh, reference = classify_undertone(lab, cfg)
        assert value == "neutral" and abs(dh) < 1e-9
    assert classify_undertone(lab_light, cfg)[3] == pytest.approx(65.0)
