"""Persist recommendation reports, revocable links and user feedback.

Revision ID: b7e4c20f91a6
Revises: 80ef34bd02c0
Create Date: 2026-11-03 12:30:00+05:30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e4c20f91a6"
down_revision: str | None = "80ef34bd02c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_reports",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("report_data", sa.JSON(), nullable=False),
        sa.Column("share_token_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_recommendation_reports_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendation_reports")),
        sa.UniqueConstraint("share_token_hash", name=op.f("uq_recommendation_reports_share_token_hash")),
    )
    op.create_index(op.f("ix_recommendation_reports_user_id"), "recommendation_reports", ["user_id"], unique=False)

    op.create_table(
        "recommendation_feedback",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("report_id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("recommendation_id", sa.String(length=100), nullable=False),
        sa.Column("helpful", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["recommendation_reports.id"], name=op.f("fk_recommendation_feedback_report_id_recommendation_reports"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_recommendation_feedback_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendation_feedback")),
        sa.UniqueConstraint("report_id", "user_id", "recommendation_id", name="uq_recommendation_feedback_report_id"),
    )
    op.create_index(op.f("ix_recommendation_feedback_report_id"), "recommendation_feedback", ["report_id"], unique=False)
    op.create_index(op.f("ix_recommendation_feedback_user_id"), "recommendation_feedback", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_recommendation_feedback_user_id"), table_name="recommendation_feedback")
    op.drop_index(op.f("ix_recommendation_feedback_report_id"), table_name="recommendation_feedback")
    op.drop_table("recommendation_feedback")
    op.drop_index(op.f("ix_recommendation_reports_user_id"), table_name="recommendation_reports")
    op.drop_table("recommendation_reports")
