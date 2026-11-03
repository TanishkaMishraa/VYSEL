"""Profiles, analysis results and per-item recommendations; link reports and feedback to them.

Also merges the saved-looks and face-scans heads.

Revision ID: e3c91f7a2b54
Revises: d0a54b78e8f1, f52a3e4170cd
Create Date: 2026-11-03 18:00:00+05:30
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3c91f7a2b54"
down_revision: tuple[str, str] = ("d0a54b78e8f1", "f52a3e4170cd")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_results",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("scan_id", sa.String(length=40), nullable=True),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("skin_tone_hex", sa.String(length=7), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["face_scans.id"], name=op.f("fk_analysis_results_scan_id_face_scans"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_analysis_results_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analysis_results")),
    )
    op.create_index(op.f("ix_analysis_results_scan_id"), "analysis_results", ["scan_id"], unique=False)
    op.create_index(op.f("ix_analysis_results_user_id"), "analysis_results", ["user_id"], unique=False)

    op.create_table(
        "profiles",
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("skin_type", sa.String(length=20), nullable=True),
        sa.Column("skin_concerns", sa.JSON(), nullable=False),
        sa.Column("latest_analysis_id", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["latest_analysis_id"],
            ["analysis_results.id"],
            name=op.f("fk_profiles_latest_analysis_id_analysis_results"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_profiles_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_profiles")),
    )
    op.create_index(op.f("ix_profiles_latest_analysis_id"), "profiles", ["latest_analysis_id"], unique=False)

    with op.batch_alter_table("recommendation_reports") as batch:
        batch.add_column(sa.Column("analysis_id", sa.String(length=40), nullable=True))
        batch.create_foreign_key(
            op.f("fk_recommendation_reports_analysis_id_analysis_results"), "analysis_results", ["analysis_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index(op.f("ix_recommendation_reports_analysis_id"), ["analysis_id"], unique=False)

    recommendations = op.create_table(
        "recommendations",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("report_id", sa.String(length=40), nullable=False),
        sa.Column("item_key", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["recommendation_reports.id"],
            name=op.f("fk_recommendations_report_id_recommendation_reports"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendations")),
        sa.UniqueConstraint("report_id", "item_key", name=op.f("uq_recommendations_report_id")),
    )
    op.create_index(op.f("ix_recommendations_category"), "recommendations", ["category"], unique=False)
    op.create_index(op.f("ix_recommendations_report_id"), "recommendations", ["report_id"], unique=False)

    # Backfill one row per item already stored in each report snapshot.
    conn = op.get_bind()
    reports = sa.table("recommendation_reports", sa.column("id", sa.String), sa.column("report_data", sa.JSON))
    rows = []
    for report_id, data in conn.execute(sa.select(reports.c.id, reports.c.report_data)):
        for group in (data or {}).get("recommendations", []):
            for rank, item in enumerate(group["items"], start=1):
                rows.append(
                    {
                        "id": f"rec_{uuid.uuid4().hex}",
                        "report_id": report_id,
                        "item_key": item["id"],
                        "category": group["category"],
                        "rank": rank,
                        "score": item["score"],
                    }
                )
    if rows:
        op.bulk_insert(recommendations, rows)

    # Votes on items a report never contained cannot satisfy the new foreign key (the API never accepted them).
    feedback = sa.table("recommendation_feedback", sa.column("report_id", sa.String), sa.column("recommendation_id", sa.String))
    known = sa.select(recommendations.c.id).where(
        recommendations.c.report_id == feedback.c.report_id, recommendations.c.item_key == feedback.c.recommendation_id
    )
    conn.execute(sa.delete(feedback).where(~sa.exists(known)))

    with op.batch_alter_table("recommendation_feedback") as batch:
        batch.create_foreign_key(
            op.f("fk_recommendation_feedback_report_id_recommendations"),
            "recommendations",
            ["report_id", "recommendation_id"],
            ["report_id", "item_key"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("recommendation_feedback") as batch:
        batch.drop_constraint(op.f("fk_recommendation_feedback_report_id_recommendations"), type_="foreignkey")

    op.drop_index(op.f("ix_recommendations_report_id"), table_name="recommendations")
    op.drop_index(op.f("ix_recommendations_category"), table_name="recommendations")
    op.drop_table("recommendations")

    with op.batch_alter_table("recommendation_reports") as batch:
        batch.drop_index(op.f("ix_recommendation_reports_analysis_id"))
        batch.drop_constraint(op.f("fk_recommendation_reports_analysis_id_analysis_results"), type_="foreignkey")
        batch.drop_column("analysis_id")

    op.drop_index(op.f("ix_profiles_latest_analysis_id"), table_name="profiles")
    op.drop_table("profiles")
    op.drop_index(op.f("ix_analysis_results_user_id"), table_name="analysis_results")
    op.drop_index(op.f("ix_analysis_results_scan_id"), table_name="analysis_results")
    op.drop_table("analysis_results")
