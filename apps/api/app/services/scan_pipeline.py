"""Run the complete selfie analysis pipeline for one persisted face scan."""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import SessionLocal, utcnow
from app.models import FaceScan, ImageUpload
from app.services.appearance import analyze_appearance
from app.services.face_analysis import (
    FaceAnalysisError,
    FaceModelUnavailable,
    get_face_analyzer,
    load_oriented_rgb,
)
from app.services.image_storage import image_path
from app.services.image_validation import ImageValidationError, validate_image

log = logging.getLogger(__name__)


def _fail(scan: FaceScan, code: str, message: str, **details: Any) -> None:
    scan.status = "failed"
    scan.error_code = code
    scan.result = {**(scan.result or {}), **details, "error": {"code": code, "message": message}}


def _analyze(db: Session, scan: FaceScan, cfg: Settings) -> dict[str, Any]:
    image = db.get(ImageUpload, scan.image_id)
    if image is None:
        _fail(scan, "UPLOAD_EXPIRED", "This image is no longer available. Upload a new selfie.")
        return {"status": scan.status, "code": scan.error_code}
    expiry = image.expires_at
    if (expiry if expiry.tzinfo else expiry.replace(tzinfo=utcnow().tzinfo)) <= utcnow():
        _fail(scan, "UPLOAD_EXPIRED", "This image is no longer available. Upload a new selfie.")
        return {"status": scan.status, "code": scan.error_code}

    started = perf_counter()
    try:
        data = image_path(cfg.selfie_storage_dir, image.storage_key).read_bytes()
    except (OSError, ValueError):
        _fail(scan, "UPLOAD_EXPIRED", "This image is no longer available. Upload a new selfie.")
        return {"status": scan.status, "code": scan.error_code}
    extension = "jpg" if image.content_type == "image/jpeg" else "png"
    validation = validate_image(data, f"selfie.{extension}", image.content_type, cfg)
    if not validation.valid:
        _fail(
            scan,
            "IMAGE_QUALITY_FAILED",
            "Image quality requirements were not met.",
            validation_errors=list(validation.errors),
            validation=validation.json_checks(),
        )
        return {"status": scan.status, "code": scan.error_code}

    analyzer = get_face_analyzer()
    rgb, orientation_corrected = load_oriented_rgb(data)
    try:
        analysis = analyzer.analyze(rgb, orientation_corrected=orientation_corrected)
    except FaceAnalysisError as exc:
        scan.face_count = exc.face_count
        _fail(scan, exc.code, exc.message, validation=validation.json_checks(), warnings=exc.warnings)
        return {"status": scan.status, "code": scan.error_code}

    result = analysis.as_json()
    result["validation"] = validation.json_checks()
    result |= analyze_appearance(rgb, analysis, cfg)
    result["processing_time_ms"] = round((perf_counter() - started) * 1000, 2)
    scan.status = "succeeded"
    scan.error_code = None
    scan.face_count = analysis.face_count
    scan.detection_confidence = analysis.detection["confidence"]
    scan.result = result
    return {"status": scan.status, "processing_time_ms": result["processing_time_ms"]}


def process_face_scan(scan_id: str, settings: Settings | None = None) -> dict[str, Any]:
    """Process or safely fail a scan; never return internal paths or exception details."""
    cfg = settings or get_settings()
    with SessionLocal() as db:
        scan = db.get(FaceScan, scan_id)
        if scan is None:
            log.warning("Face scan task references missing scan=%s", scan_id)
            return {"status": "missing"}
        if scan.status in {"succeeded", "failed"}:
            return {"status": scan.status, "code": scan.error_code}

        scan.status = "running"
        db.commit()
        try:
            outcome = _analyze(db, scan, cfg)
        except ImageValidationError as exc:
            log.info("Stored image rejected during scan=%s code=%s", scan.id, exc.code)
            _fail(scan, exc.code, str(exc))
            outcome = {"status": scan.status, "code": scan.error_code}
        except FaceModelUnavailable:
            log.exception("Face model unavailable for scan=%s", scan.id)
            _fail(scan, "FACE_ANALYSIS_UNAVAILABLE", "Face analysis is temporarily unavailable. Please try again later.")
            outcome = {"status": scan.status, "code": scan.error_code}
        except Exception:
            log.exception("Unexpected analysis failure for scan=%s", scan.id)
            _fail(scan, "ANALYSIS_FAILED", "We could not analyze this image. Please try another selfie.")
            outcome = {"status": scan.status, "code": scan.error_code}
        db.commit()
        log.info("Face scan complete id=%s status=%s code=%s", scan.id, scan.status, scan.error_code)
        return outcome
