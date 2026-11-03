"""Landmark-to-region mapping: derived from MediaPipe's documented topology, anatomically sane."""

from __future__ import annotations

import importlib.util
import sys

import numpy as np
import pytest

from app.services.face_region_data import FEATURE_LANDMARKS, REGION_LANDMARKS
from app.services.face_regions import AREA_REGIONS, CONTOUR_REGIONS, KEY_POINTS, REGIONS, region_geometry
from tests.conftest import API_DIR

pytest.importorskip("mediapipe", reason="MediaPipe not installed (python scripts/setup_face_analysis.py)")
from mediapipe.tasks.python.vision import FaceLandmarksConnections as C  # noqa: E402


def _generator():
    spec = importlib.util.spec_from_file_location("generate_face_regions", API_DIR / "scripts" / "generate_face_regions.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


GEN = _generator()
CANON = GEN.load_canonical()  # canonical face: y up, +x = subject's left
X, Y = CANON[:, 0], CANON[:, 1]


def _set(connections) -> set[int]:
    return {i for c in connections for i in (c.start, c.end)}


def test_committed_regions_match_generator():
    """Fails if face_region_data.py was hand-edited or MediaPipe's topology changed."""
    derived = {name: tuple(indices) for name, indices in GEN.derive_regions(CANON).items()}
    assert derived == REGION_LANDMARKS
    assert {name: tuple(indices) for name, indices in GEN.derive_features().items()} == FEATURE_LANDMARKS


def test_eye_and_iris_sets_are_mediapipes_documented_contours():
    for side in ("left", "right"):
        eye, iris = FEATURE_LANDMARKS[f"{side}_eye"], FEATURE_LANDMARKS[f"{side}_iris"]
        documented_eye = {frozenset((c.start, c.end)) for c in getattr(C, f"FACE_LANDMARKS_{side.upper()}_EYE")}
        assert {frozenset((eye[i], eye[(i + 1) % len(eye)])) for i in range(len(eye))} == documented_eye
        assert set(iris) == _set(getattr(C, f"FACE_LANDMARKS_{side.upper()}_IRIS")) and len(iris) == 4
        assert FEATURE_LANDMARKS[f"{side}_iris_center"][0] not in iris


def test_every_region_is_defined_and_uses_valid_mesh_indices():
    assert set(REGIONS) == set(AREA_REGIONS + CONTOUR_REGIONS + KEY_POINTS)
    for region in REGIONS.values():
        assert region.landmark_indices, region.name
        assert all(0 <= i < 468 for i in region.landmark_indices), region.name
        assert len(set(region.landmark_indices)) == len(region.landmark_indices), region.name
    for name in AREA_REGIONS:
        assert len(REGIONS[name].landmark_indices) >= 10, f"{name} too coarse for skin sampling"


def test_face_oval_is_mediapipes_documented_contour():
    oval = REGIONS["face_oval"].landmark_indices
    assert set(oval) == _set(C.FACE_LANDMARKS_FACE_OVAL)
    documented_edges = {frozenset((c.start, c.end)) for c in C.FACE_LANDMARKS_FACE_OVAL}
    walked = {frozenset((oval[i], oval[(i + 1) % len(oval)])) for i in range(len(oval))}
    assert walked == documented_edges


def test_skin_regions_avoid_eyes_brows_and_lips():
    features = (
        _set(C.FACE_LANDMARKS_LEFT_EYE)
        | _set(C.FACE_LANDMARKS_RIGHT_EYE)
        | _set(C.FACE_LANDMARKS_LEFT_EYEBROW)
        | _set(C.FACE_LANDMARKS_RIGHT_EYEBROW)
        | _set(C.FACE_LANDMARKS_LIPS)
    )
    for name in ("forehead", "left_cheek", "right_cheek", "chin"):
        assert not features & set(REGIONS[name].landmark_indices), name
    assert not _set(C.FACE_LANDMARKS_NOSE) & (set(REGIONS["left_cheek"].landmark_indices) | set(REGIONS["right_cheek"].landmark_indices))


def test_regions_are_anatomically_placed_on_the_canonical_face():
    def ys(name):
        return Y[list(REGIONS[name].landmark_indices)]

    brows = list(_set(C.FACE_LANDMARKS_LEFT_EYEBROW) | _set(C.FACE_LANDMARKS_RIGHT_EYEBROW))
    eyes = list(_set(C.FACE_LANDMARKS_LEFT_EYE) | _set(C.FACE_LANDMARKS_RIGHT_EYE))
    lips = list(_set(C.FACE_LANDMARKS_LIPS))
    assert ys("forehead").min() > Y[brows].max()
    assert ys("chin").max() < Y[lips].min()
    for name in ("left_cheek", "right_cheek"):
        assert ys(name).max() < Y[eyes].min() and ys(name).min() >= Y[lips].min()
    assert (X[list(REGIONS["left_cheek"].landmark_indices)] > 0).all()  # subject's left
    assert (X[list(REGIONS["right_cheek"].landmark_indices)] < 0).all()


def test_cheeks_are_mirror_images():
    left = CANON[list(REGIONS["left_cheek"].landmark_indices)][:, :2]
    right = CANON[list(REGIONS["right_cheek"].landmark_indices)][:, :2] * [-1, 1]
    assert len(left) == len(right)
    nearest = np.min(np.linalg.norm(left[:, None] - right[None], axis=2), axis=1)
    assert nearest.max() < 1e-3


def test_jawline_runs_ear_to_ear_through_the_chin():
    jaw = REGIONS["jawline"].landmark_indices
    assert set(jaw) < set(REGIONS["face_oval"].landmark_indices)
    assert X[jaw[0]] < 0 < X[jaw[-1]]  # subject's right -> left
    assert REGIONS["chin_bottom"].landmark_indices[0] in jaw
    assert REGIONS["left_jaw_angle"].landmark_indices[0] in jaw and REGIONS["right_jaw_angle"].landmark_indices[0] in jaw


def test_key_points():
    oval = list(REGIONS["face_oval"].landmark_indices)
    assert REGIONS["forehead_top"].landmark_indices[0] == oval[int(np.argmax(Y[oval]))]
    assert REGIONS["chin_bottom"].landmark_indices[0] == oval[int(np.argmin(Y[oval]))]
    assert REGIONS["nose_tip"].landmark_indices[0] in _set(C.FACE_LANDMARKS_NOSE)
    assert X[REGIONS["left_face_edge"].landmark_indices[0]] > 0 > X[REGIONS["right_face_edge"].landmark_indices[0]]
    for side, sign in (("left", 1), ("right", -1)):
        forehead_edge = REGIONS[f"{side}_forehead_edge"].landmark_indices[0]
        assert forehead_edge in oval and sign * X[forehead_edge] > 0
        assert Y[forehead_edge] > Y[REGIONS[f"{side}_jaw_angle"].landmark_indices[0]]


def test_region_geometry_from_projected_canonical_face():
    # Project the canonical face to a 1000x1000 image (y down) and check the geometry output.
    pixels = np.stack([500 + X * 40, 500 - Y * 40], axis=1)
    forehead = region_geometry(REGIONS["forehead"], pixels, 1000, 1000)
    assert forehead["kind"] == "area" and forehead["in_frame_ratio"] == 1.0
    assert len(forehead["polygon"]) >= 3 and forehead["area_px"] > 0
    box = forehead["bounding_box"]
    assert box["y"] + box["height"] < 500 - Y[list(_set(C.FACE_LANDMARKS_LEFT_EYEBROW))].max() * 40 + 1

    jaw = region_geometry(REGIONS["jawline"], pixels, 1000, 1000)
    assert jaw["closed"] is False and len(jaw["polyline"]) == len(REGIONS["jawline"].landmark_indices)

    cropped = region_geometry(REGIONS["left_cheek"], pixels - [450, 0], 100, 1000)  # cheek mostly cut off
    assert cropped["in_frame_ratio"] < 0.5
