"""Account-owned recommendation reports, revocable sharing, and feedback."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_db, utcnow
from app.deps import current_user
from app.errors import ApiError
from app.models import RecommendationFeedback, RecommendationReport, User
from app.security import hash_token, new_opaque_token
from app.services.recommendations import generate_recommendations

router = APIRouter(prefix="/reports", tags=["Reports"])


def _owned_report(db: Session, user_id: str, report_id: str) -> RecommendationReport:
    report = db.scalar(
        select(RecommendationReport).where(
            RecommendationReport.id == report_id,
            RecommendationReport.user_id == user_id,
        )
    )
    if report is None:
        raise ApiError(404, "NOT_FOUND", "Report not found.")
    return report


def _report_out(report: RecommendationReport, db: Session) -> schemas.ReportOut:
    feedback = db.scalars(
        select(RecommendationFeedback).where(
            RecommendationFeedback.report_id == report.id,
            RecommendationFeedback.user_id == report.user_id,
        )
    ).all()
    return schemas.ReportOut(
        id=report.id,
        created_at=report.created_at,
        report_data=report.report_data,
        share_enabled=report.share_token_hash is not None,
        feedback=[
            schemas.ReportFeedbackOut(
                recommendation_id=item.recommendation_id,
                helpful=item.helpful,
                updated_at=item.created_at,
            )
            for item in feedback
        ],
    )


@router.post("", response_model=schemas.ReportOut, status_code=201)
def create_report(
    body: schemas.CreateReportRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    result = generate_recommendations(body.features, user.preferences)
    report = RecommendationReport(user_id=user.id, report_data=result.model_dump(mode="json"))
    db.add(report)
    db.commit()
    db.refresh(report)
    return _report_out(report, db)


@router.get("", response_model=list[schemas.ReportListItem])
def list_reports(user: User = Depends(current_user), db: Session = Depends(get_db)):
    reports = db.scalars(
        select(RecommendationReport).where(RecommendationReport.user_id == user.id).order_by(RecommendationReport.created_at.desc())
    ).all()
    return [
        schemas.ReportListItem(
            id=report.id,
            created_at=report.created_at,
            season=report.report_data["season"]["value"],
            recommendation_count=sum(len(group["items"]) for group in report.report_data["recommendations"]),
            share_enabled=report.share_token_hash is not None,
        )
        for report in reports
    ]


@router.get("/shared/{token}", response_model=schemas.RecommendationsResponse)
def get_shared_report(token: str, db: Session = Depends(get_db)):
    report = db.scalar(select(RecommendationReport).where(RecommendationReport.share_token_hash == hash_token(token)))
    if report is None:
        raise ApiError(404, "NOT_FOUND", "Shared report not found or sharing has been turned off.")
    return report.report_data


@router.get("/{report_id}", response_model=schemas.ReportOut)
def get_report(report_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _report_out(_owned_report(db, user.id, report_id), db)


@router.delete("/{report_id}", status_code=204)
def delete_report(report_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    report = _owned_report(db, user.id, report_id)
    db.execute(delete(RecommendationFeedback).where(RecommendationFeedback.report_id == report.id))
    db.delete(report)
    db.commit()
    return Response(status_code=204)


@router.post("/{report_id}/share", response_model=schemas.ShareLinkOut)
def enable_report_sharing(report_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    report = _owned_report(db, user.id, report_id)
    token, token_hash = new_opaque_token()
    report.share_token_hash = token_hash
    db.commit()
    return schemas.ShareLinkOut(share_url=f"/shared/{token}")


@router.delete("/{report_id}/share", status_code=204)
def disable_report_sharing(report_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    report = _owned_report(db, user.id, report_id)
    report.share_token_hash = None
    db.commit()
    return Response(status_code=204)


@router.put("/{report_id}/feedback", response_model=schemas.ReportFeedbackOut)
def save_report_feedback(
    report_id: str,
    body: schemas.ReportFeedbackRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    report = _owned_report(db, user.id, report_id)
    recommendation_ids = {item["id"] for group in report.report_data["recommendations"] for item in group["items"]}
    if body.recommendation_id not in recommendation_ids:
        raise ApiError(404, "NOT_FOUND", "Recommendation not found in this report.")

    feedback = db.scalar(
        select(RecommendationFeedback).where(
            RecommendationFeedback.report_id == report.id,
            RecommendationFeedback.user_id == user.id,
            RecommendationFeedback.recommendation_id == body.recommendation_id,
        )
    )
    if feedback is None:
        feedback = RecommendationFeedback(
            report_id=report.id,
            user_id=user.id,
            recommendation_id=body.recommendation_id,
            helpful=body.helpful,
        )
        db.add(feedback)
    else:
        feedback.helpful = body.helpful
        feedback.created_at = utcnow()
    db.commit()
    db.refresh(feedback)
    return schemas.ReportFeedbackOut(
        recommendation_id=feedback.recommendation_id,
        helpful=feedback.helpful,
        updated_at=feedback.created_at,
    )
