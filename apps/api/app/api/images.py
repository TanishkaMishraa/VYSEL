"""Authenticated multipart selfie upload and metadata endpoints."""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, utcnow
from app.deps import current_user
from app.errors import ApiError
from app.models import ImageUpload, User
from app.services.image_storage import delete_image, store_image
from app.services.image_validation import ImageValidationError, safe_filename, validate_image

log = logging.getLogger(__name__)
router = APIRouter(prefix="/images", tags=["Images"])


class CheckOut(BaseModel):
    passed: bool
    value: str | int | float
    threshold: str | int | float
    message: str


class ImageOut(BaseModel):
    id: str
    status: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    retention: str
    expires_at: str
    created_at: str


class ImageUploadOut(BaseModel):
    image: ImageOut
    validation: dict[str, CheckOut]


@router.post(
    "",
    status_code=201,
    response_model=ImageUploadOut,
    operation_id="uploadImage",
    summary="Upload and validate a selfie image",
    responses={
        400: {"description": "Empty upload or missing processing consent."},
        401: {"description": "Authentication is required."},
        413: {"description": "Image exceeds size or dimension limits."},
        415: {"description": "Only matching JPG/JPEG or PNG files are supported."},
        422: {"description": "Image quality checks failed."},
    },
)
async def upload_image(
    response: Response,
    file: UploadFile = File(..., description="JPG/JPEG or PNG selfie"),
    consent: bool = Form(..., description="Explicit consent to process this image"),
    policy_version: str = Form(..., min_length=1, max_length=32),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ImageUploadOut:
    """Receive one consented selfie via multipart/form-data and store it privately."""
    if not consent:
        raise ApiError(400, "CONSENT_REQUIRED", "Image processing consent must be granted before upload.")
    cfg = get_settings()
    # One extra byte detects oversized files even when Content-Length is absent.
    content = await file.read(cfg.selfie_max_file_size_bytes + 1)
    await file.close()
    try:
        result = validate_image(content, file.filename or "", file.content_type or "", cfg)
    except ImageValidationError as exc:
        log.info("Image upload rejected for user=%s code=%s", user.id, exc.code)
        raise ApiError(exc.status_code, exc.code, str(exc)) from None
    if not result.valid:
        log.info("Image quality rejection for user=%s: %s", user.id, "; ".join(result.errors))
        raise ApiError(
            422,
            "IMAGE_QUALITY_FAILED",
            "Image quality requirements were not met.",
            validation_errors=list(result.errors),
            validation=result.json_checks(),
        )

    storage_key = f"{secrets.token_hex(16)}.{'jpg' if result.image_format == 'JPEG' else 'png'}"
    destination = None
    try:
        destination = store_image(cfg.selfie_storage_dir, storage_key, content)
        created_at = utcnow()
        expires_at = created_at + timedelta(hours=24)
        image = ImageUpload(
            user_id=user.id,
            storage_key=storage_key,
            filename=safe_filename(file.filename or "selfie", result.image_format),
            content_type="image/jpeg" if result.image_format == "JPEG" else "image/png",
            size_bytes=len(content),
            width=result.width,
            height=result.height,
            blur_variance=result.blur_variance,
            mean_brightness=result.mean_brightness,
            validation_results=result.json_checks(),
            consent_policy_version=policy_version,
            retention="ephemeral",
            expires_at=expires_at,
        )
        db.add(image)
        db.commit()
        db.refresh(image)
    except Exception as exc:
        db.rollback()
        if destination is not None:
            delete_image(cfg.selfie_storage_dir, storage_key)
        log.exception("Could not store image upload for user=%s", user.id)
        raise ApiError(503, "SERVICE_UNAVAILABLE", "The image could not be stored. Please try again.") from exc

    log.info("Image accepted: id=%s user=%s format=%s bytes=%d", image.id, user.id, result.image_format, len(content))
    response.headers["Location"] = f"/v1/images/{image.id}"
    return ImageUploadOut(
        image=ImageOut(
            id=image.id,
            status="uploaded",
            content_type=image.content_type,
            size_bytes=image.size_bytes,
            width=image.width,
            height=image.height,
            retention=image.retention,
            expires_at=image.expires_at.isoformat(),
            created_at=image.created_at.isoformat(),
        ),
        validation={key: CheckOut(**check) for key, check in result.json_checks().items()},
    )


@router.get("/{image_id}", response_model=ImageOut, operation_id="getImageMetadata")
def get_image(image_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ImageOut:
    image = db.scalar(select(ImageUpload).where(ImageUpload.id == image_id, ImageUpload.user_id == user.id))
    if image is None:
        raise ApiError(404, "NOT_FOUND", "Image not found.")
    return ImageOut(
        id=image.id,
        status="uploaded",
        content_type=image.content_type,
        size_bytes=image.size_bytes,
        width=image.width,
        height=image.height,
        retention=image.retention,
        expires_at=image.expires_at.isoformat(),
        created_at=image.created_at.isoformat(),
    )


@router.delete("/{image_id}", status_code=204, operation_id="deleteImage")
def delete_image_upload(image_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    image = db.scalar(select(ImageUpload).where(ImageUpload.id == image_id, ImageUpload.user_id == user.id))
    if image is None:
        raise ApiError(404, "NOT_FOUND", "Image not found.")
    delete_image(get_settings().selfie_storage_dir, image.storage_key)
    db.delete(image)
    db.commit()
    return Response(status_code=204)
