"""The face evaluation script: metric mechanics and identity-leakage protection (not an accuracy claim)."""

from __future__ import annotations

import importlib.util
import json
import re
import sys

import numpy as np
import pytest
from PIL import Image

from tests.conftest import API_DIR, FIXTURES


def _script():
    spec = importlib.util.spec_from_file_location("evaluate_faces", API_DIR / "scripts" / "evaluate_faces.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def dataset(tmp_path):
    portrait = np.asarray(Image.open(FIXTURES / "portrait.jpg").convert("RGB"))
    h, w = portrait.shape[:2]
    Image.fromarray(portrait).save(tmp_path / "one.jpg", quality=95)
    Image.fromarray(np.concatenate([portrait, portrait], axis=1)).save(tmp_path / "two.jpg", quality=95)
    (tmp_path / "none.jpg").write_bytes((FIXTURES / "cat.jpg").read_bytes())
    # Ground truth: MediaPipe's published expected landmarks for this portrait, in pixels.
    text = (FIXTURES / "portrait_expected_face_landmarks.pbtxt").read_text()
    points = [(float(x) * w, float(y) * h) for x, y in re.findall(r"x: ([-\d.e]+)\s+y: ([-\d.e]+)", text)]
    keys = (10, 33, 133, 362, 263, 4, 61, 291, 152)
    (tmp_path / "one.json").write_text(json.dumps({"landmarks": {str(i): points[i] for i in keys}}))
    rows = [
        "path,person_id,split,expected_faces,groups,annotation",
        "one.jpg,p1,validation,1,lighting=studio;eyewear=none,one.json",
        "two.jpg,p2,validation,2+,crowd=yes,",
        "none.jpg,p3,validation,0,,",
        "one.jpg,p4,test,1,,",
    ]
    (tmp_path / "manifest.csv").write_text("\n".join(rows) + "\n")
    return tmp_path


def test_reports_detection_landmark_and_group_metrics(dataset, face_analyzer):
    module = _script()
    report = module.evaluate(module.read_manifest(dataset / "manifest.csv", dataset), "validation", face_analyzer.settings)
    overall = report["overall"]
    assert overall["images"] == 3 and overall["people"] == 3
    assert overall["detection"] == {"tp": 2, "fp": 0, "fn": 0, "tn": 1, "precision": 1.0, "recall": 1.0, "f1": 1.0}
    assert overall["single_face_acceptance_rate"] == 1.0
    assert overall["multiple_face_rejection_rate"] == 1.0
    assert overall["no_face_rejection_rate"] == 1.0
    assert overall["landmarks"]["annotated_images"] == 1
    assert overall["landmarks"]["mean_nme"] < 0.05 and overall["landmarks"]["within_0.05"] == 1.0
    assert set(report["groups"]) == {"lighting=studio", "eyewear=none", "crowd=yes", "unlabelled"}
    assert report["groups"]["crowd=yes"]["conclusive"] is False  # 1 person is far below the minimum


def test_region_iou_against_annotated_polygons(dataset, face_analyzer):
    module = _script()
    polygon = face_analyzer.analyze_bytes((dataset / "one.jpg").read_bytes()).regions["left_cheek"]["polygon"]
    (dataset / "one.json").write_text(json.dumps({"regions": {"left_cheek": polygon}}))
    rows = module.read_manifest(dataset / "manifest.csv", dataset)
    outcome = module.evaluate_row(face_analyzer, rows[0])
    assert outcome["region_iou"]["left_cheek"] > 0.95


def test_rejects_identity_leakage_and_path_escapes(dataset):
    module = _script()
    manifest = dataset / "manifest.csv"
    manifest.write_text(manifest.read_text().replace("one.jpg,p4,test", "one.jpg,p1,test"))
    with pytest.raises(ValueError, match="identity leakage"):
        module.read_manifest(manifest, dataset)
    manifest.write_text("path,person_id,split,expected_faces\n../secret.jpg,p1,validation,1\n")
    with pytest.raises(ValueError, match="escapes"):
        module.read_manifest(manifest, dataset)
