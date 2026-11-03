"""The signed-in user's profile and onboarding preferences."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_db, utcnow
from app.deps import current_user
from app.models import ImageUpload, User, UserPreferences
from app.services import auth as sessions
from app.services.image_storage import delete_image

router = APIRouter(prefix="/me", tags=["Profile"])


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
    """Erase the account; sessions, tokens, links and preferences cascade."""
    from app.config import get_settings

    for image in db.query(ImageUpload).filter_by(user_id=user.id).all():
        delete_image(get_settings().selfie_storage_dir, image.storage_key)
    db.delete(user)
    db.commit()
    sessions.clear_refresh_cookie(response)
    response.status_code = 204
    return response
