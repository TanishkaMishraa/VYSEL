"""Personalised, explainable styling recommendations."""

from fastapi import APIRouter, Depends

from app import schemas
from app.deps import current_user
from app.models import User
from app.services.recommendations import generate_recommendations

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.post("", response_model=schemas.RecommendationsResponse)
def get_recommendations(body: schemas.RecommendationFeatures, user: User = Depends(current_user)):
    """Rank style ideas from explicitly supplied estimates and the user's saved preferences."""
    return generate_recommendations(body, user.preferences)
