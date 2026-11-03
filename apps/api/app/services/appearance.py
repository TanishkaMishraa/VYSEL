"""Everything a scan estimates beyond detection: skin (4.3), face shape and attributes (4.4).

Each part fails independently: if hair can't be read, skin tone and face shape are still returned.
`recommendation_features` matches `schemas.RecommendationFeatures`, so a client can pass a scan's
estimates straight to POST /v1/recommendations or /v1/reports.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app import schemas
from app.config import Settings, get_settings
from app.services.face_analysis import FaceAnalysis
from app.services.face_shape import FaceShapeUnavailable, analyze_face_shape
from app.services.facial_attributes import AttributeUnavailable, analyze_eye_color, analyze_hair_color, feature_contrast
from app.services.skin_analysis import SkinAnalysisUnavailable, analyze_skin, prepare_scene


def analyze_appearance(rgb: np.ndarray, face: FaceAnalysis, settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    scene = prepare_scene(rgb, face, cfg)

    try:
        skin = analyze_skin(rgb, face, cfg, scene)
    except SkinAnalysisUnavailable as exc:
        skin = exc.as_json()
    try:
        face_shape = analyze_face_shape(face, cfg)
    except FaceShapeUnavailable as exc:
        face_shape = exc.as_json()
    try:
        eye_color = analyze_eye_color(face, scene, cfg)
    except AttributeUnavailable as exc:
        eye_color = exc.as_json()
    # Hair is told apart from skin using the forehead's colour when available: it is the skin
    # nearest the hairline and lit the same way, so a lower threshold separates blonde hair.
    reference = None
    if skin["status"] == "ok":
        forehead = skin["regions"].get("forehead", {})
        lab = forehead["lab"] if forehead.get("used") else skin["skin_tone"]["lab"]
        reference = np.array([lab["l"], lab["a"], lab["b"]])
    try:
        hair_color = analyze_hair_color(face, scene, reference, cfg)
    except AttributeUnavailable as exc:
        hair_color = exc.as_json()
    contrast = feature_contrast(skin, hair_color, eye_color, cfg)

    attributes: dict[str, Any] = {"face_shape": face_shape, "eye_color": eye_color, "hair_color": hair_color}
    if contrast:
        attributes["contrast"] = contrast
    return {"skin": skin, "attributes": attributes, "recommendation_features": recommendation_features(skin, face_shape, contrast)}


def recommendation_features(skin: dict[str, Any], face_shape: dict[str, Any], contrast: dict[str, Any] | None) -> dict[str, Any] | None:
    """The scan's estimates in the recommendation engine's input format, or None if incomplete."""
    if skin["status"] != "ok" or face_shape["status"] != "ok":
        return None
    features: dict[str, Any] = {
        "face_shape": {"value": face_shape["value"], "confidence": face_shape["confidence"]},
        "undertone": {"value": skin["undertone"]["value"], "confidence": skin["undertone"]["confidence"]},
        "skin_depth": {"value": skin["skin_tone"]["depth"], "confidence": skin["skin_tone"]["confidence"]},
    }
    if contrast:
        features["contrast"] = {"value": contrast["value"], "confidence": contrast["confidence"]}
    return schemas.RecommendationFeatures(**features).model_dump()
