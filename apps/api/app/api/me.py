"""The signed-in user's profile and onboarding preferences."""

import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import schemas
from app.config import get_settings
from app.db import get_db, utcnow
from app.deps import current_user
from app.errors import ApiError
from app.models import (
    AnalysisResult,
    FaceScan,
    ImageUpload,
    OAuthAccount,
    PasswordResetToken,
    Recommendation,
    RecommendationFeedback,
    RecommendationReport,
    RefreshToken,
    SavedTryOnLook,
    User,
    UserPreferences,
    UserProfile,
)
from app.services import auth as sessions
from app.services.image_storage import delete_image as remove_image

router = APIRouter(prefix="/me", tags=["Profile"])
log = logging.getLogger(__name__)


@router.get("", response_model=schemas.Profile)
def get_me(user: User = Depends(current_user)):
    return sessions.to_profile(user)


@router.patch("", response_model=schemas.Profile)
def update_me(body: schemas.ProfileUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Merge-patch (RFC 7396): only fields present in the body change; null clears budget/style."""
    if body.display_name is not None:
        user.display_name = body.display_name.strip() or user.display_name

    prefs = user.preferences or UserPreferences(user_id=user.id)
    if user.preferences is None:
        user.preferences = prefs
    if body.preferences is not None:
        for field in body.preferences.model_fields_set:
            value = getattr(body.preferences, field)
            if field in ("style_goals", "occasions", "categories"):
                value = value or []  # null clears a list
            setattr(prefs, field, value)
    if body.onboarding_completed is True and prefs.onboarding_completed_at is None:
        prefs.onboarding_completed_at = utcnow()
    elif body.onboarding_completed is False:
        prefs.onboarding_completed_at = None

    db.commit()
    db.refresh(user)
    return sessions.to_profile(user)


@router.delete("", status_code=204)
def delete_me(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Erase account-owned database rows and private image files."""
    images = db.scalars(select(ImageUpload).where(ImageUpload.user_id == user.id)).all()
    storage_dir = get_settings().selfie_storage_dir
    for image in images:
        try:
            remove_image(storage_dir, image.storage_key)
        except (OSError, ValueError) as exc:
            log.exception("Could not remove private image for account deletion user=%s image=%s", user.id, image.id)
            raise ApiError(
                503,
                "DATA_DELETION_INCOMPLETE",
                "Private images could not all be removed. Your account is still active; please retry.",
            ) from exc

    user_id = user.id
    db.execute(delete(RecommendationFeedback).where(RecommendationFeedback.user_id == user_id))
    db.execute(
        delete(Recommendation).where(
            Recommendation.report_id.in_(select(RecommendationReport.id).where(RecommendationReport.user_id == user_id))
        )
    )
    db.execute(delete(RecommendationReport).where(RecommendationReport.user_id == user_id))
    db.execute(delete(FaceScan).where(FaceScan.user_id == user_id))
    db.execute(delete(ImageUpload).where(ImageUpload.user_id == user_id))
    db.execute(delete(SavedTryOnLook).where(SavedTryOnLook.user_id == user_id))
    db.execute(delete(UserPreferences).where(UserPreferences.user_id == user_id))
    db.execute(delete(UserProfile).where(UserProfile.user_id == user_id))
    db.execute(delete(AnalysisResult).where(AnalysisResult.user_id == user_id))
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id))
    db.execute(delete(OAuthAccount).where(OAuthAccount.user_id == user_id))
    db.execute(delete(User).where(User.id == user_id))
    db.commit()
    sessions.clear_refresh_cookie(response)
    response.status_code = 204
    return response
