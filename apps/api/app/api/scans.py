"""Face scans for an uploaded selfie: detection and landmarks (4.2), skin tone and undertone (4.3), face shape and attributes (4.4)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.api.images import CheckOut
from app.db import get_db, utcnow
from app.deps import current_user
from app.errors import ApiError
from app.models import FaceScan, ImageUpload, User
from app.ratelimit import enforce
from app.services.face_analysis import MODEL_NAME
from app.tasks import analyze_face_scan

log = logging.getLogger(__name__)
router = APIRouter(prefix="/scans", tags=["Scans"])


# ── Response schema ────────────────────────────────────────────────────────


class CreateScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    image_id: str = Field(min_length=1, max_length=40, description="An `img_` ID returned by POST /v1/images.")


class ScanWarning(BaseModel):
    code: str
    message: str


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class Detection(BaseModel):
    confidence: float | None = Field(description="BlazeFace detection score, 0-1. Null if only the landmarker found the face.")
    bounding_box: BoundingBox | None


class ImageInfo(BaseModel):
    width: int
    height: int
    orientation_corrected: bool = Field(description="EXIF orientation was applied; coordinates refer to the upright image.")
    rotation_applied_degrees: int = Field(description="Quarter turn used to find a sideways face (coordinates are mapped back).")


class Landmark(BaseModel):
    index: int
    x: float
    y: float
    z: float
    px: float
    py: float


class Landmarks(BaseModel):
    count: int
    topology: str
    coordinate_space: str
    points: list[Landmark]


class Region(BaseModel):
    kind: Literal["area", "contour"]
    landmark_indices: list[int]
    in_frame_ratio: float
    bounding_box: BoundingBox
    centroid: list[float]
    polygon: list[list[float]] | None = Field(default=None, description="Area regions: convex hull in pixels.")
    area_px: float | None = None
    polyline: list[list[float]] | None = Field(default=None, description="Contours: ordered points in pixels.")
    closed: bool | None = None
    visible: bool | None = Field(default=None, description="Area regions: usable for skin analysis.")


class KeyPoint(BaseModel):
    index: int
    x: float
    y: float
    px: float
    py: float


class HeadPose(BaseModel):
    pitch: float
    yaw: float
    roll: float


class ScanError(BaseModel):
    code: str
    message: str


class ScanModel(BaseModel):
    name: str


class Lab(BaseModel):
    l: float  # noqa: E741 — CIELAB channel name
    a: float
    b: float


class MonkTone(BaseModel):
    value: int = Field(ge=1, le=10)
    hex: str
    delta_e: float = Field(description="CIEDE2000 distance from the skin colour to this swatch.")


class SkinTone(BaseModel):
    hex: str
    lab: Lab
    depth: Literal["fair", "light", "medium", "tan", "deep"]
    confidence: float
    label: Literal["estimate"]
    ita_degrees: float = Field(description="Individual Typology Angle (Chardon et al., 1991).")
    ita_category: Literal["very_light", "light", "intermediate", "tan", "brown", "dark"]
    monk: MonkTone


class Undertone(BaseModel):
    value: Literal["warm", "cool", "neutral"]
    confidence: float
    label: Literal["estimate"]
    method: str
    hue_angle: float
    chroma: float
    reference_hue: float
    delta_h: float = Field(description="Signed perceptual hue difference from the neutral reference; + is yellower, - is pinker.")


class ColorCorrection(BaseModel):
    method: str
    reference_pixels: int
    gains: dict[str, float]
    clamped: bool
    applied: bool


class SkinCluster(BaseModel):
    lab: Lab
    hex: str
    share: float
    used: bool


class SkinRegion(BaseModel):
    used: bool
    pixels: int
    reason: str | None = None
    lab: Lab | None = None
    hex: str | None = None
    delta_e_from_consensus: float | None = None


class Skin(BaseModel):
    status: Literal["ok", "unavailable"]
    skin_tone: SkinTone | None = None
    undertone: Undertone | None = None
    color_correction: ColorCorrection | None = None
    clusters: list[SkinCluster] | None = None
    regions: dict[str, SkinRegion] | None = None
    pixels_used: int | None = None
    warnings: list[ScanWarning] = []
    error: ScanError | None = None


class ShapeAlternative(BaseModel):
    value: Literal["oval", "round", "square", "heart", "oblong", "diamond"]
    confidence: float


class FaceShape(BaseModel):
    status: Literal["ok", "unavailable"]
    value: Literal["oval", "round", "square", "heart", "oblong", "diamond"] | None = None
    confidence: float | None = None
    label: Literal["estimate"] | None = None
    alternatives: list[ShapeAlternative] | None = None
    method: str | None = None
    measurements: dict[str, float] | None = Field(default=None, description="Length/width, forehead/cheekbone, jaw/cheekbone, chin angle.")
    features: dict[str, float] | None = Field(default=None, description="Deviations from MediaPipe's canonical face.")
    probabilities: dict[str, float] | None = None
    warnings: list[ScanWarning] = []
    error: ScanError | None = None


class ColorAttribute(BaseModel):
    status: Literal["ok", "unavailable"]
    value: str | None = None
    confidence: float | None = None
    label: Literal["estimate"] | None = None
    hex: str | None = None
    lab: Lab | None = None
    eyes: dict[str, dict[str, Any]] | None = Field(default=None, description="Eye colour: per-eye sampling details.")
    band_pixels: int | None = Field(default=None, description="Hair colour: pixels sampled around the head.")
    background_delta_e: float | None = Field(default=None, description="Hair colour: CIEDE2000 from the background.")
    warnings: list[ScanWarning] = []
    error: ScanError | None = None


class Contrast(BaseModel):
    value: Literal["low", "medium", "high"]
    confidence: float
    label: Literal["estimate"]
    delta_l: float
    source: Literal["hair", "eyes"]


class Attributes(BaseModel):
    face_shape: FaceShape
    eye_color: ColorAttribute
    hair_color: ColorAttribute
    contrast: Contrast | None = None


class ScanOut(BaseModel):
    id: str
    image_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    face_count: int
    detection: Detection | None = None
    image: ImageInfo | None = None
    landmarks: Landmarks | None = None
    regions: dict[str, Region] = {}
    key_points: dict[str, KeyPoint] = {}
    head_pose: HeadPose | None = None
    skin: Skin | None = None
    attributes: Attributes | None = None
    recommendation_features: schemas.RecommendationFeatures | None = Field(
        default=None, description="This scan's estimates in the input format of POST /v1/recommendations and /v1/reports."
    )
    warnings: list[ScanWarning] = []
    error: ScanError | None = None
    validation: dict[str, CheckOut]
    model: ScanModel
    created_at: str
    expires_at: str
    processing_time_ms: float | None = Field(default=None, description="Worker processing duration; present for completed scans.")


# ── Helpers ────────────────────────────────────────────────────────────────


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)  # SQLite returns naive UTC datetimes.


def scan_json(scan: FaceScan) -> dict[str, Any]:
    return {
        "id": scan.id,
        "image_id": scan.image_id,
        "status": scan.status,
        "face_count": scan.face_count,
        **scan.result,
        "model": {"name": scan.model_version},
        "created_at": _aware(scan.created_at).isoformat(),
        "expires_at": _aware(scan.expires_at).isoformat(),
    }


def _owned_image(db: Session, user: User, image_id: str) -> ImageUpload:
    image = db.scalar(select(ImageUpload).where(ImageUpload.id == image_id, ImageUpload.user_id == user.id))
    if image is None:
        raise ApiError(404, "NOT_FOUND", "Image not found.")
    if _aware(image.expires_at) <= utcnow():
        raise ApiError(410, "UPLOAD_EXPIRED", "This image has expired. Upload a new selfie.")
    return image


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.post(
    "",
    status_code=202,
    response_model=ScanOut,
    response_model_exclude_none=True,
    operation_id="createFaceScan",
    summary="Queue face detection, landmark extraction and appearance analysis",
    responses={
        401: {"description": "Authentication is required."},
        404: {"description": "Image not found (or owned by someone else)."},
        410: {"description": "`UPLOAD_EXPIRED`: the image passed its retention window."},
        422: {"description": "Malformed request or invalid image data."},
        429: {"description": "Too many scans."},
        503: {"description": "The background job queue is unavailable."},
    },
)
def create_scan(
    body: CreateScanRequest, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Queue the full analysis pipeline. Poll the returned scan URL until status is terminal."""
    enforce("face-scan", user.id, limit=30, window_seconds=600)
    image = _owned_image(db, user, body.image_id)
    scan = FaceScan(
        user_id=user.id,
        image_id=image.id,
        status="queued",
        face_count=0,
        model_version=MODEL_NAME,
        result={"validation": image.validation_results},
        expires_at=image.expires_at,
    )
    db.add(scan)
    db.commit()
    try:
        analyze_face_scan.delay(scan.id)
    except Exception:
        log.exception("Could not enqueue face scan id=%s", scan.id)
        db.delete(scan)
        db.commit()
        raise ApiError(503, "SERVICE_UNAVAILABLE", "Analysis could not be queued. Please try again shortly.") from None
    db.refresh(scan)
    payload = ScanOut(**scan_json(scan)).model_dump(exclude_none=True)
    response.headers["Location"] = f"/v1/scans/{scan.id}"
    if scan.status in {"queued", "running"}:
        response.headers["Retry-After"] = "1"
    response.status_code = 202
    return payload


@router.get("/{scan_id}", response_model=ScanOut, response_model_exclude_none=True, operation_id="getFaceScan")
def get_scan(
    scan_id: str, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    scan = db.scalar(select(FaceScan).where(FaceScan.id == scan_id, FaceScan.user_id == user.id))
    if scan is None or _aware(scan.expires_at) <= utcnow():
        raise ApiError(404, "NOT_FOUND", "Scan not found.")
    if scan.status in {"queued", "running"}:
        response.headers["Retry-After"] = "1"
    return scan_json(scan)
