"""The skin evaluation script: metric mechanics, validation-only tuning, identity leakage (not an accuracy claim)."""

from __future__ import annotations

import importlib.util
import json
import sys

import cv2
import numpy as np
import pytest
from PIL import Image

from app.services.color import lab_to_linear, linear_to_srgb, srgb8_to_lab
from tests.conftest import API_DIR, FIXTURES


def _script():
    spec = importlib.util.spec_from_file_location("evaluate_skin", API_DIR / "scripts" / "evaluate_skin.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = _script()


@pytest.fixture
def dataset(tmp_path, face_analyzer):
    """Three versions of one face (as-is, yellower, pinker) plus a no-face image."""
    portrait = np.asarray(Image.open(FIXTURES / "portrait.jpg").convert("RGB"))
    face = face_analyzer.analyze(portrait)
    mask = np.zeros(portrait.shape[:2], np.uint8)
    cv2.fillPoly(mask, [np.asarray(face.regions["face_oval"]["polyline"]).astype(np.int32)], 1)
    mask = mask.astype(bool)
    lab = srgb8_to_lab(portrait[mask])
    for name, shift in {"as_is": (0, 0), "yellow": (0, 8), "pink": (6, -5)}.items():
        image = portrait.copy()
        image[mask] = np.round(linear_to_srgb(lab_to_linear(lab + [0, *shift])) * 255).astype(np.uint8)
        Image.fromarray(image).save(tmp_path / f"{name}.png")
    (tmp_path / "cat.jpg").write_bytes((FIXTURES / "cat.jpg").read_bytes())
    rows = [
        "path,person_id,split,undertone,monk,reference_lab,groups",
        "as_is.png,p1,validation,neutral,5,68.9;14.9;23.7,lighting=studio",
        "yellow.png,p2,validation,warm,5,,lighting=studio",
        "pink.png,p3,validation,cool,6,,",
        "cat.jpg,p4,validation,,,,",
        "as_is.png,p5,test,neutral,5,,",
    ]
    (tmp_path / "manifest.csv").write_text("\n".join(rows) + "\n")
    return tmp_path


def test_report_metrics(dataset, face_analyzer):
    rows = [r for r in MODULE.read_manifest(dataset / "manifest.csv", dataset) if r.split == "validation"]
    result = MODULE.report(rows, MODULE.analyze_rows(rows, face_analyzer.settings))
    overall = result["overall"]
    assert overall["images"] == 4 and overall["analyzed_rate"] == 0.75
    assert overall["outcomes"] == {"NO_FACE_DETECTED": 1, "ok": 3}
    undertone = overall["undertone"]
    assert undertone["n"] == 3
    assert undertone["accuracy"] == 1.0 and undertone["macro_f1"] == 1.0 and undertone["cohen_kappa"] == 1.0
    assert sum(sum(row.values()) for key, row in undertone["confusion_matrix"].items() if key in MODULE.UNDERTONES) == 3
    tone = overall["skin_tone"]
    assert tone["reference_n"] == 1 and tone["delta_e_2000"]["mean"] < 1  # reference reading = the estimate
    assert tone["monk_n"] == 3 and tone["monk"]["within_1"] == 1.0
    assert {"lighting=studio", "unlabelled", "monk=5", "monk=6"} <= set(result["groups"])
    assert result["groups"]["monk=5"]["conclusive"] is False


def test_sweeps_reclassify_without_reanalysis(dataset, face_analyzer):
    rows = [r for r in MODULE.read_manifest(dataset / "manifest.csv", dataset) if r.split == "validation"]
    outcomes = MODULE.analyze_rows(rows, face_analyzer.settings)
    wide = face_analyzer.settings.model_copy(update={"skin_undertone_neutral_delta_h": 50.0})
    everything_neutral = MODULE.reclassify(outcomes, wide)
    assert {o.undertone for o in everything_neutral if o.undertone} == {"neutral"}
    assert MODULE.reclassify(outcomes, face_analyzer.settings)[0].undertone == outcomes[0].undertone


def test_fit_reference_needs_enough_neutral_examples_and_fits_medians(dataset):
    rows = MODULE.read_manifest(dataset / "manifest.csv", dataset)
    few = [MODULE.Outcome("ok", np.array([60.0, 15.0, 22.0]))] * len(rows)
    with pytest.raises(ValueError, match="labelled-neutral"):
        MODULE.fit_reference(rows, few)

    row = rows[0]
    many_rows = [row] * 40
    outcomes = [
        MODULE.Outcome("ok", np.array([30.0 + i, 20 * np.cos(np.radians(50 + i / 4)), 20 * np.sin(np.radians(50 + i / 4))]))
        for i in range(40)
    ]
    curve = MODULE.fit_reference(many_rows, outcomes)
    assert curve["fitted_on"] == "validation" and len(curve["points"]) == 2
    lightness, hue = zip(*curve["points"], strict=True)
    assert lightness == tuple(sorted(lightness)) and hue[0] < hue[1]
    json.dumps(curve)


def test_manifest_validation(dataset):
    manifest = dataset / "manifest.csv"
    text = manifest.read_text()
    manifest.write_text(text.replace("as_is.png,p5,test", "as_is.png,p1,test"))
    with pytest.raises(ValueError, match="identity leakage"):
        MODULE.read_manifest(manifest, dataset)
    manifest.write_text(text.replace("validation,neutral,5", "validation,olive,5", 1))
    with pytest.raises(ValueError, match="undertone"):
        MODULE.read_manifest(manifest, dataset)
    manifest.write_text("path,person_id,split\n../x.png,p1,validation\n")
    with pytest.raises(ValueError, match="escapes"):
        MODULE.read_manifest(manifest, dataset)
