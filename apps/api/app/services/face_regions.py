"""Landmark-to-region mapping for skin analysis and face-shape classification.

Index sets come from `face_region_data.py`, generated from MediaPipe's documented topology by
scripts/generate_face_regions.py. This module only turns landmark coordinates into region
geometry; it does not import MediaPipe, so downstream phases can reuse it cheaply.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

from app.services.face_region_data import REGION_LANDMARKS

RegionKind = Literal["area", "contour", "point"]


@dataclass(frozen=True)
class RegionDefinition:
    name: str
    kind: RegionKind
    landmark_indices: tuple[int, ...]
    description: str


_DESCRIPTIONS: dict[str, tuple[RegionKind, str]] = {
    "forehead": ("area", "Skin above the eyebrows, up to the top of the landmark mesh (below the hairline)."),
    "left_cheek": ("area", "Subject's left cheek: below the eye, beside the nose, above the mouth corner."),
    "right_cheek": ("area", "Subject's right cheek: below the eye, beside the nose, above the mouth corner."),
    "chin": ("area", "Below the lower lip, within the width of the mouth."),
    "face_oval": ("contour", "Closed face boundary (MediaPipe FACE_OVAL), clockwise from the forehead top."),
    "jawline": ("contour", "Lower face boundary from the subject's right ear, through the chin, to the left ear."),
    "forehead_top": ("point", "Highest point of the face oval."),
    "chin_bottom": ("point", "Lowest point of the face oval."),
    "nose_tip": ("point", "Most forward point of the nose."),
    "left_face_edge": ("point", "Widest point of the face oval on the subject's left."),
    "right_face_edge": ("point", "Widest point of the face oval on the subject's right."),
    "left_jaw_angle": ("point", "Face oval point level with the mouth corners, subject's left."),
    "right_jaw_angle": ("point", "Face oval point level with the mouth corners, subject's right."),
}

REGIONS: dict[str, RegionDefinition] = {
    name: RegionDefinition(name, _DESCRIPTIONS[name][0], indices, _DESCRIPTIONS[name][1]) for name, indices in REGION_LANDMARKS.items()
}
AREA_REGIONS = tuple(name for name, region in REGIONS.items() if region.kind == "area")
CONTOUR_REGIONS = tuple(name for name, region in REGIONS.items() if region.kind == "contour")
KEY_POINTS = tuple(name for name, region in REGIONS.items() if region.kind == "point")


def _bbox(points: np.ndarray) -> dict[str, float]:
    x0, y0 = points.min(axis=0)
    x1, y1 = points.max(axis=0)
    return {"x": round(float(x0), 1), "y": round(float(y0), 1), "width": round(float(x1 - x0), 1), "height": round(float(y1 - y0), 1)}


def in_frame_ratio(points: np.ndarray, width: int, height: int) -> float:
    inside = (points[:, 0] >= 0) & (points[:, 0] < width) & (points[:, 1] >= 0) & (points[:, 1] < height)
    return float(inside.mean())


def region_geometry(region: RegionDefinition, points_px: np.ndarray, width: int, height: int) -> dict:
    """Pixel geometry of one region. `points_px` is the (N, 2) array of all landmark pixels."""
    points = points_px[list(region.landmark_indices)]
    geometry: dict = {
        "kind": region.kind,
        "landmark_indices": list(region.landmark_indices),
        "in_frame_ratio": round(in_frame_ratio(points, width, height), 3),
    }
    if region.kind == "point":
        geometry["point"] = [round(float(points[0, 0]), 1), round(float(points[0, 1]), 1)]
        return geometry
    if region.kind == "area":
        # Convex hull of the member landmarks: always a simple polygon, even under head rotation.
        hull = cv2.convexHull(points.astype(np.float32)).reshape(-1, 2)
        geometry["polygon"] = [[round(float(x), 1), round(float(y), 1)] for x, y in hull]
        geometry["area_px"] = round(float(cv2.contourArea(hull)), 1)
    else:
        geometry["polyline"] = [[round(float(x), 1), round(float(y), 1)] for x, y in points]
        geometry["closed"] = region.name == "face_oval"
    geometry["bounding_box"] = _bbox(points)
    centroid = points.mean(axis=0)
    geometry["centroid"] = [round(float(centroid[0]), 1), round(float(centroid[1]), 1)]
    return geometry
