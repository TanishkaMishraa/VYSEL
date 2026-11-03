"""Face-shape classification from landmark geometry (Phase 4.4).

1. **Measurements** in 3D (x, y in pixels, z on x's scale, as MediaPipe documents), so a turned
   or tilted head foreshortens them less than 2D distances would: face length (mesh top to chin),
   forehead, cheekbone and jaw widths, and the chin angle (jaw angles seen from the chin).
2. **Features**: each ratio as a log-deviation from the same ratio on MediaPipe's canonical face
   model (an average, frontal face), divided by a typical spread. Using the canonical face as the
   zero point means no hand-set absolute thresholds, and mesh-specific quirks (the mesh ends
   below the hairline) cancel out.
3. **Classification**: Gaussian nearest-prototype. Each shape is a prototype point encoding its
   common stylist definition (e.g. heart = wide forehead, narrow jaw, pointed chin); class
   probabilities are softmax(-distance^2 / 2). Prototypes and spreads are *starting values*, not
   fitted to labelled faces. `scripts/evaluate_attributes.py --fit-prototypes` fits both on
   validation data (enable with FACE_SHAPE_PROTOTYPES_PATH).
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.config import Settings, get_settings
from app.services.face_analysis import FaceAnalysis
from app.services.face_region_data import REGION_LANDMARKS

SHAPES = ("oval", "round", "square", "heart", "oblong", "diamond")
FEATURES = ("length", "forehead", "jaw", "chin")
METHOD = "landmark-prototypes-v1"

# Canonical-face reference values, computed from tests/fixtures/mediapipe/canonical_face_model.obj
# by `canonical_reference()`; tests/test_face_shape.py checks they still match.
CANONICAL = {"length_ratio": 1.1408, "forehead_ratio": 0.9154, "jaw_ratio": 0.8678, "chin_angle": 83.135}

# Typical person-to-person spread of each feature (log-ratio, or degrees for the chin). Untuned.
DEFAULT_SPREAD = {"length": 0.06, "forehead": 0.04, "jaw": 0.05, "chin": 6.0}

# Prototypes in spread units (length, forehead width, jaw width, chin angle), from the usual
# descriptions. Untuned starting values; see the module docstring.
DEFAULT_PROTOTYPES: dict[str, tuple[float, float, float, float]] = {
    "oval": (0.5, 0.3, -0.3, 0.0),  # a little longer than wide, balanced, softly tapered chin
    "round": (-1.5, 0.0, 0.3, 1.0),  # about as long as wide, full cheeks, wide soft chin
    "square": (-1.0, 0.0, 1.5, 1.5),  # short-ish, jaw as wide as the cheeks, broad chin
    "heart": (0.0, 1.5, -1.5, -1.5),  # wide forehead, narrow jaw, pointed chin
    "oblong": (2.0, 0.0, 0.0, 0.0),  # clearly longer than wide, even widths
    "diamond": (0.5, -1.5, -1.0, -1.0),  # cheekbones widest, narrow forehead and jaw
}


class FaceShapeUnavailable(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message

    def as_json(self) -> dict[str, Any]:
        return {"status": "unavailable", "error": {"code": self.code, "message": self.message}}


def _point(points: np.ndarray, name: str) -> np.ndarray:
    return points[REGION_LANDMARKS[name][0]]


def measure(points: np.ndarray) -> dict[str, float]:
    """Ratios from (N, 3) landmark points (any consistent units)."""

    def distance(a: str, b: str) -> float:
        return float(np.linalg.norm(_point(points, a) - _point(points, b)))

    length = distance("forehead_top", "chin_bottom")
    cheekbones = distance("left_face_edge", "right_face_edge")
    chin = _point(points, "chin_bottom")
    left, right = _point(points, "left_jaw_angle") - chin, _point(points, "right_jaw_angle") - chin
    cosine = float(np.dot(left, right) / (np.linalg.norm(left) * np.linalg.norm(right)))
    return {
        "length_ratio": length / cheekbones,
        "forehead_ratio": distance("left_forehead_edge", "right_forehead_edge") / cheekbones,
        "jaw_ratio": distance("left_jaw_angle", "right_jaw_angle") / cheekbones,
        "chin_angle": math.degrees(math.acos(max(-1.0, min(1.0, cosine)))),
    }


def canonical_reference(vertices: np.ndarray) -> dict[str, float]:
    """The reference ratios, from the canonical face model's (468, 3) vertices."""
    return {k: round(v, 4 if k != "chin_angle" else 3) for k, v in measure(vertices).items()}


def features(ratios: dict[str, float]) -> dict[str, float]:
    """Deviations from the canonical face (log-ratios; degrees for the chin)."""
    return {
        "length": math.log(ratios["length_ratio"] / CANONICAL["length_ratio"]),
        "forehead": math.log(ratios["forehead_ratio"] / CANONICAL["forehead_ratio"]),
        "jaw": math.log(ratios["jaw_ratio"] / CANONICAL["jaw_ratio"]),
        "chin": ratios["chin_angle"] - CANONICAL["chin_angle"],
    }


@lru_cache
def _load_model(path: str | None) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    if not path:
        return {k: np.array(v) for k, v in DEFAULT_PROTOTYPES.items()}, DEFAULT_SPREAD
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    prototypes = {k: np.array(v, dtype=float) for k, v in data["prototypes"].items() if k in SHAPES}
    if not prototypes:
        raise ValueError(f"No known face shapes in {path}")
    return prototypes, {f: float(data["spread"][f]) for f in FEATURES}


def model(settings: Settings) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    path = settings.face_shape_prototypes_path
    return _load_model(str(path) if path else None)


def classify(feature_values: dict[str, float], settings: Settings) -> dict[str, float]:
    """Class probabilities (sum to 1), most likely first."""
    prototypes, spread = model(settings)
    z = np.array([feature_values[f] / spread[f] for f in FEATURES])
    scores = {shape: -0.5 * float(np.sum((z - centre) ** 2)) for shape, centre in prototypes.items()}
    top = max(scores.values())
    weights = {shape: math.exp(score - top) for shape, score in scores.items()}
    total = sum(weights.values())
    return dict(sorted(((s, w / total) for s, w in weights.items()), key=lambda item: -item[1]))


def landmark_points(face: FaceAnalysis) -> np.ndarray:
    """3D points: pixels for x and y, and MediaPipe's z on the same scale as x."""
    return np.array([(p["x"] * face.image_width, p["y"] * face.image_height, p["z"] * face.image_width) for p in face.landmarks])


def analyze_face_shape(face: FaceAnalysis, settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    if face.regions["face_oval"]["in_frame_ratio"] < cfg.face_min_in_frame_ratio:
        raise FaceShapeUnavailable(
            "FACE_NOT_FULLY_VISIBLE", "Part of the face outline is outside the photo, so its shape can't be measured."
        )

    ratios = measure(landmark_points(face))
    values = features(ratios)
    probabilities = classify(values, cfg)
    ranked = list(probabilities.items())
    confidence = ranked[0][1]
    warnings = []
    if any(w["code"] == "HIGH_HEAD_ROTATION" for w in face.warnings):
        confidence *= 0.7
        warnings.append({"code": "FACE_SHAPE_POSE", "message": "The head is turned or tilted, which distorts face proportions."})
    return {
        "status": "ok",
        "value": ranked[0][0],
        "confidence": round(confidence, 3),
        "label": "estimate",
        "alternatives": [{"value": shape, "confidence": round(p, 3)} for shape, p in ranked[1:3]],
        "method": METHOD,
        "measurements": {k: round(v, 3) for k, v in ratios.items()},
        "features": {k: round(v, 4) for k, v in values.items()},
        "probabilities": {k: round(v, 3) for k, v in probabilities.items()},
        "warnings": warnings,
    }
