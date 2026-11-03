"""Face scans for an uploaded selfie: one-face detection, landmarks and regions (Phase 4.2), skin tone and undertone (Phase 4.3)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.images import CheckOut
from app.config import get_settings
from app.db import get_db, utcnow
from app.deps import current_user
from app.errors import ApiError
from app.models import FaceScan, ImageUpload, User
from app.ratelimit import enforce
from app.services.face_analysis import MODEL_NAME, FaceAnalysisError, FaceModelUnavailable, get_face_analyzer, load_oriented_rgb
from app.services.image_storage import image_path
from app.services.image_validation import ImageValidationError, validate_image
from app.services.skin_analysis import SkinAnalysisUnavailable, analyze_skin

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


class ScanOut(BaseModel):
    id: str
    image_id: str
    status: Literal["succeeded", "failed"]
    face_count: int
    detection: Detection | None = None
    image: ImageInfo | None = None
    landmarks: Landmarks | None = None
    regions: dict[str, Region] = {}
    key_points: dict[str, KeyPoint] = {}
    head_pose: HeadPose | None = None
    skin: Skin | None = None
    warnings: list[ScanWarning] = []
    error: ScanError | None = None
    validation: dict[str, CheckOut]
    model: ScanModel
    created_at: str
    expires_at: str


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
    status_code=201,
    response_model=ScanOut,
    response_model_exclude_none=True,
    operation_id="createFaceScan",
    summary="Detect one face and extract landmarks and facial regions",
    responses={
        401: {"description": "Authentication is required."},
        404: {"description": "Image not found (or owned by someone else)."},
        410: {"description": "`UPLOAD_EXPIRED`: the image passed its retention window."},
        422: {
            "description": "`NO_FACE_DETECTED`, `MULTIPLE_FACES_DETECTED`, `FACE_LANDMARKS_NOT_FOUND` (body includes the failed "
            "`scan`), or a Phase 4.1 validation code such as `IMAGE_QUALITY_FAILED`."
        },
        429: {"description": "Too many scans."},
        503: {"description": "`FACE_ANALYSIS_UNAVAILABLE`: the face model is not installed."},
    },
)
def create_scan(
    body: CreateScanRequest, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Runs synchronously (about 25 ms on a laptop CPU once the model is loaded). Only images that pass Phase 4.1
    validation are analyzed: the stored bytes are re-validated with the current rules first."""
    enforce("face-scan", user.id, limit=30, window_seconds=600)
    cfg = get_settings()
    image = _owned_image(db, user, body.image_id)
    try:
        data = image_path(cfg.selfie_storage_dir, image.storage_key).read_bytes()
    except (OSError, ValueError):
        log.warning("Stored file missing for image=%s", image.id)
        raise ApiError(410, "UPLOAD_EXPIRED", "This image is no longer available. Upload a new selfie.") from None

    extension = "jpg" if image.content_type == "image/jpeg" else "png"
    try:
        validation = validate_image(data, f"selfie.{extension}", image.content_type, cfg)
    except ImageValidationError as exc:
        raise ApiError(422, exc.code, str(exc)) from None
    if not validation.valid:
        raise ApiError(
            422,
            "IMAGE_QUALITY_FAILED",
            "Image quality requirements were not met.",
            validation_errors=list(validation.errors),
            validation=validation.json_checks(),
        )

    try:
        analyzer = get_face_analyzer()
    except FaceModelUnavailable as exc:
        log.error("Face analysis unavailable: %s", exc)
        raise ApiError(503, "FACE_ANALYSIS_UNAVAILABLE", "Face analysis is temporarily unavailable.", retry_after=30) from None

    result: dict[str, Any] = {"validation": validation.json_checks()}
    failure: FaceAnalysisError | None = None
    try:
        rgb, orientation_corrected = load_oriented_rgb(data)
        analysis = analyzer.analyze(rgb, orientation_corrected=orientation_corrected)
        result |= analysis.as_json()
        face_count, confidence = analysis.face_count, analysis.detection["confidence"]
        try:
            result["skin"] = analyze_skin(rgb, analysis, cfg)
        except SkinAnalysisUnavailable as exc:  # The face scan still succeeds; skin is reported unavailable.
            result["skin"] = exc.as_json()
    except FaceAnalysisError as exc:
        failure = exc
        result |= {"warnings": exc.warnings, "error": {"code": exc.code, "message": exc.message}}
        face_count, confidence = exc.face_count, None
    result.pop("face_count", None)

    scan = FaceScan(
        user_id=user.id,
        image_id=image.id,
        status="failed" if failure else "succeeded",
        error_code=failure.code if failure else None,
        face_count=face_count,
        detection_confidence=confidence,
        model_version=MODEL_NAME,
        result=result,
        expires_at=image.expires_at,
    )
    db.add(scan)
    db.commit()
    log.info("Face scan %s image=%s status=%s code=%s faces=%d", scan.id, image.id, scan.status, scan.error_code, face_count)

    payload = ScanOut(**scan_json(scan)).model_dump(exclude_none=True)
    if failure:
        raise ApiError(422, failure.code, failure.message, scan=payload)
    response.headers["Location"] = f"/v1/scans/{scan.id}"
    return payload


@router.get("/{scan_id}", response_model=ScanOut, response_model_exclude_none=True, operation_id="getFaceScan")
def get_scan(scan_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, Any]:
    scan = db.scalar(select(FaceScan).where(FaceScan.id == scan_id, FaceScan.user_id == user.id))
    if scan is None or _aware(scan.expires_at) <= utcnow():
        raise ApiError(404, "NOT_FOUND", "Scan not found.")
    return scan_json(scan)
