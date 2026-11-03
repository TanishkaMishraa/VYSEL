"""Product listings matched against a user's saved report recommendations."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_db
from app.deps import current_user
from app.errors import ApiError
from app.models import RecommendationReport, User
from app.services.product_catalog import match_products

router = APIRouter(prefix="/reports", tags=["Products"])


@router.get("/{report_id}/products", response_model=schemas.ProductMatchesResponse)
def get_report_product_matches(
    report_id: str,
    budget: schemas.ProductBudgetFilter | None = Query(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    report = db.scalar(
        select(RecommendationReport).where(
            RecommendationReport.id == report_id,
            RecommendationReport.user_id == user.id,
        )
    )
    if report is None:
        raise ApiError(404, "NOT_FOUND", "Report not found.")
    effective_budget = budget if budget != "all" else None
    if budget is None:
        effective_budget = user.preferences.budget if user.preferences else None
    return match_products(report.report_data, effective_budget)
