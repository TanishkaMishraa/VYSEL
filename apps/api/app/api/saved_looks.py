"""Private saved makeup looks for the virtual try-on studio."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_db
from app.deps import current_user
from app.errors import ApiError
from app.models import SavedTryOnLook, User

router = APIRouter(prefix="/saved-looks", tags=["Saved looks"])


def _owned_look(db: Session, user_id: str, look_id: str) -> SavedTryOnLook:
    look = db.scalar(select(SavedTryOnLook).where(SavedTryOnLook.id == look_id, SavedTryOnLook.user_id == user_id))
    if look is None:
        raise ApiError(404, "NOT_FOUND", "Saved look not found.")
    return look


def _to_out(look: SavedTryOnLook) -> schemas.SavedLookOut:
    return schemas.SavedLookOut(
        id=look.id,
        name=look.name,
        occasion=look.occasion,
        look=look.look_data,
        created_at=look.created_at,
        updated_at=look.updated_at,
    )


@router.post("", response_model=schemas.SavedLookOut, status_code=201)
def create_saved_look(body: schemas.CreateSavedLookRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    look = SavedTryOnLook(
        user_id=user.id,
        name=body.name,
        occasion=body.occasion,
        look_data=body.look.model_dump(mode="json"),
    )
    db.add(look)
    db.commit()
    db.refresh(look)
    return _to_out(look)


@router.get("", response_model=list[schemas.SavedLookOut])
def list_saved_looks(
    occasion: schemas.SavedLookOccasion | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    query = (
        select(SavedTryOnLook).where(SavedTryOnLook.user_id == user.id).order_by(SavedTryOnLook.occasion, SavedTryOnLook.updated_at.desc())
    )
    if occasion is not None:
        query = query.where(SavedTryOnLook.occasion == occasion)
    return [_to_out(look) for look in db.scalars(query).all()]


@router.get("/{look_id}", response_model=schemas.SavedLookOut)
def get_saved_look(look_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _to_out(_owned_look(db, user.id, look_id))


@router.delete("/{look_id}", status_code=204)
def delete_saved_look(look_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    look = _owned_look(db, user.id, look_id)
    db.delete(look)
    db.commit()
    return Response(status_code=204)
