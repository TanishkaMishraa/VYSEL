"""The attribute evaluation script: metric mechanics, rater agreement, prototype fitting (not an accuracy claim)."""

from __future__ import annotations

import importlib.util
import json
import sys

import cv2
import numpy as np
import pytest
from PIL import Image

from app.config import Settings
from app.services.evaluation import classification_metrics
from app.services.face_shape import FEATURES, analyze_face_shape
from tests.conftest import API_DIR, FIXTURES


def _script():
    spec = importlib.util.spec_from_file_location("evaluate_attributes", API_DIR / "scripts" / "evaluate_attributes.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = _script()


@pytest.fixture
def dataset(tmp_path):
    portrait = np.asarray(Image.open(FIXTURES / "portrait.jpg").convert("RGB"))
    h, w = portrait.shape[:2]
    Image.fromarray(portrait).save(tmp_path / "a.png")
    Image.fromarray(cv2.resize(portrait, (w, round(h * 0.85)))).save(tmp_path / "short.png")
    (tmp_path / "cat.jpg").write_bytes((FIXTURES / "cat.jpg").read_bytes())
    rows = [
        "path,person_id,split,face_shape,face_shape_rater2,eye_color,hair_color,groups",
        "a.png,p1,validation,oblong,oval,dark_brown,black,lighting=studio",
        "short.png,p2,validation,oval,oval,dark_brown,black,",
        "cat.jpg,p3,validation,,,,,",
        "a.png,p4,test,oblong,,,,",
    ]
    (tmp_path / "manifest.csv").write_text("\n".join(rows) + "\n")
    return tmp_path


def test_report(dataset, face_analyzer):
    rows = [r for r in MODULE.read_manifest(dataset / "manifest.csv", dataset) if r.split == "validation"]
    result = MODULE.report(rows, MODULE.analyze_rows(rows, face_analyzer.settings))
    overall = result["overall"]
    assert overall["images"] == 3 and overall["face_analyzed_rate"] == pytest.approx(0.6667, abs=1e-3)
    shape = overall["face_shape"]
    assert shape["n"] == 2 and shape["available_rate"] == 1.0 and 0 <= shape["accuracy"] <= 1
    assert shape["majority_baseline_accuracy"] == 0.5
    assert overall["eye_color"]["accuracy"] == 1.0  # the portrait's eyes are dark brown
    assert overall["face_shape_rater_agreement"] == {"n": 2, "accuracy": 0.5, "cohen_kappa": 0.0}
    assert result["groups"]["lighting=studio"]["conclusive"] is False
    json.dumps(result)


def test_classification_metrics():
    pairs = [("oval", "oval", 0.9), ("oval", "round", 0.4), ("round", "round", 0.8), ("heart", "oval", 0.6)]
    metrics = classification_metrics(pairs, ("oval", "round", "heart"))
    assert metrics["accuracy"] == 0.5 and metrics["majority_baseline_accuracy"] == 0.5
    assert metrics["per_class"]["round"] == {"precision": 0.5, "recall": 1.0, "f1": 0.6667, "support": 1}
    assert metrics["confident_only"] == {"coverage": 0.75, "accuracy": 0.6667}
    assert classification_metrics([], ("oval",)) == {"n": 0}


def test_fit_prototypes_learns_class_means_and_is_used(dataset, tmp_path, face_analyzer):
    rows = MODULE.read_manifest(dataset / "manifest.csv", dataset)
    with pytest.raises(ValueError, match="two or more shapes"):
        MODULE.fit_prototypes(rows, [{"features": dict.fromkeys(FEATURES, 0.0)}] * len(rows))

    rng = np.random.default_rng(0)
    centres = {"round": np.array([-0.08, 0.0, 0.02, 5.0]), "oblong": np.array([0.12, 0.0, 0.0, -2.0])}
    fake_rows, fake_outcomes = [], []
    for shape, centre in centres.items():
        for _ in range(20):
            fake_rows.append(MODULE.Row(rows[0].path, "x", "validation", {"face_shape": shape}, None))
            sample = centre + rng.normal(0, [0.02, 0.01, 0.01, 1.0])
            fake_outcomes.append({"features": dict(zip(FEATURES, sample.tolist(), strict=True))})
    model = MODULE.fit_prototypes(fake_rows, fake_outcomes)
    assert set(model["prototypes"]) == {"round", "oblong"} and model["fitted_on"] == "validation"
    assert model["spread"]["length"] == pytest.approx(0.02, rel=0.4)

    path = tmp_path / "shape.json"
    path.write_text(json.dumps(model))
    portrait = np.asarray(Image.open(FIXTURES / "portrait.jpg").convert("RGB"))
    result = analyze_face_shape(face_analyzer.analyze(portrait), Settings(_env_file=None, face_shape_prototypes_path=path))
    assert result["value"] == "oblong"  # the portrait's length feature (+0.12) sits on the oblong centre


def test_manifest_validation(dataset):
    manifest = dataset / "manifest.csv"
    text = manifest.read_text()
    manifest.write_text(text.replace("a.png,p4,test", "a.png,p1,test"))
    with pytest.raises(ValueError, match="identity leakage"):
        MODULE.read_manifest(manifest, dataset)
    manifest.write_text(text.replace("oblong,oval,dark_brown", "triangle,oval,dark_brown"))
    with pytest.raises(ValueError, match="face_shape must be"):
        MODULE.read_manifest(manifest, dataset)
