"""Read-only operational metrics for explicitly allowlisted administrators."""

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app import schemas
from app.db import get_db, utcnow
from app.deps import admin_user
from app.models import (
    AnalysisResult,
    BackgroundJob,
    FaceScan,
    ImageUpload,
    JobStatus,
    Recommendation,
    RecommendationFeedback,
    User,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/overview", response_model=schemas.AdminOverview)
def get_admin_overview(_admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.created_at.desc()).limit(50)).all()
    user_count = db.scalar(select(func.count()).select_from(User)) or 0
    analysis_count = db.scalar(select(func.count()).select_from(AnalysisResult)) or 0

    scan_rows = db.execute(
        select(FaceScan.status, FaceScan.model_version, func.count()).group_by(FaceScan.status, FaceScan.model_version)
    ).all()
    scan_counts = {"queued": 0, "running": 0, "succeeded": 0, "failed": 0}
    model_versions: dict[str, dict[str, int]] = defaultdict(lambda: {"queued": 0, "running": 0, "succeeded": 0, "failed": 0})
    for status, model_version, count in scan_rows:
        status_name = str(status)
        if status_name in scan_counts:
            scan_counts[status_name] += count
            model_versions[model_version][status_name] += count
    scan_total = sum(scan_counts.values())

    feedback_rows = db.execute(
        select(Recommendation.category, RecommendationFeedback.helpful, func.count())
        .join(
            Recommendation,
            and_(
                Recommendation.report_id == RecommendationFeedback.report_id,
                Recommendation.item_key == RecommendationFeedback.recommendation_id,
            ),
        )
        .group_by(Recommendation.category, RecommendationFeedback.helpful)
    ).all()
    feedback_by_category: dict[str, dict[str, int]] = defaultdict(lambda: {"helpful": 0, "not_helpful": 0})
    feedback_total = 0
    for category, helpful, count in feedback_rows:
        key = "helpful" if helpful else "not_helpful"
        feedback_by_category[category][key] += count
        feedback_total += count

    scan_failures = db.scalars(
        select(FaceScan).where(FaceScan.status == "failed").order_by(FaceScan.created_at.desc()).limit(25)
    ).all()
    job_failures = db.scalars(
        select(BackgroundJob).where(BackgroundJob.status == JobStatus.failed).order_by(BackgroundJob.updated_at.desc()).limit(25)
    ).all()
    failures = [
        schemas.AdminFailure(
            id=scan.id,
            source="scan",
            category=scan.error_code or "ANALYSIS_FAILED",
            status=scan.status,
            occurred_at=scan.updated_at,
        )
        for scan in scan_failures
    ] + [
        schemas.AdminFailure(
            id=job.id,
            source="job",
            category="BACKGROUND_JOB_FAILED",
            status=job.status.value,
            occurred_at=job.updated_at,
        )
        for job in job_failures
    ]
    failures.sort(key=lambda failure: failure.occurred_at, reverse=True)

    scan_image_rows = db.execute(
        select(FaceScan, ImageUpload)
        .join(ImageUpload, ImageUpload.id == FaceScan.image_id)
        .order_by(FaceScan.created_at.desc())
        .limit(200)
    ).all()
    flagged_images: list[schemas.AdminFlaggedImage] = []
    for scan, image in scan_image_rows:
        checks = image.validation_results or {}
        quality_flags = sorted(name for name, check in checks.items() if isinstance(check, dict) and check.get("passed") is False)
        warning_codes = sorted(
            {warning.get("code", "UNSPECIFIED_WARNING") for warning in (scan.result or {}).get("warnings", []) if isinstance(warning, dict)}
        )
        if scan.status != "failed" and not quality_flags and not warning_codes:
            continue
        flagged_images.append(
            schemas.AdminFlaggedImage(
                scan_id=scan.id,
                image_id=image.id,
                status=scan.status,
                model_version=scan.model_version,
                error_code=scan.error_code,
                quality_flags=quality_flags,
                warning_codes=warning_codes,
                created_at=scan.created_at,
            )
        )
        if len(flagged_images) == 25:
            break

    return schemas.AdminOverview(
        generated_at=utcnow(),
        registered_users=user_count,
        recent_users=[
            schemas.AdminUserSummary(
                id=user.id,
                email=user.email,
                display_name=user.display_name,
                email_verified=user.email_verified,
                created_at=user.created_at,
            )
            for user in users
        ],
        analyses=analysis_count,
        scans=schemas.AdminScanMetrics(
            total=scan_total,
            queued=scan_counts["queued"],
            running=scan_counts["running"],
            succeeded=scan_counts["succeeded"],
            failed=scan_counts["failed"],
            model_versions=dict(model_versions),
        ),
        feedback_total=feedback_total,
        feedback=[
            schemas.AdminFeedbackMetric(
                category=category,
                helpful=counts["helpful"],
                not_helpful=counts["not_helpful"],
            )
            for category, counts in sorted(feedback_by_category.items())
        ],
        flagged_images=flagged_images,
        system_failures=failures[:25],
        model_evaluation=schemas.AdminEvaluationStatus(
            status="not_available",
            sample_count=0,
            message="No privacy-reviewed labeled evaluation results are configured. Production scan outcomes are not accuracy labels.",
        ),
    )
