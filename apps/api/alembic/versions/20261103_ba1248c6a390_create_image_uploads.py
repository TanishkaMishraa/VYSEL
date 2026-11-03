"""create image_uploads

Revision ID: ba1248c6a390
Revises: 80ef34bd02c0
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ba1248c6a390"
down_revision: str | None = "80ef34bd02c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "image_uploads",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("storage_key", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=128), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("blur_variance", sa.Float(), nullable=False),
        sa.Column("mean_brightness", sa.Float(), nullable=False),
        sa.Column("validation_results", sa.JSON(), nullable=False),
        sa.Column("consent_policy_version", sa.String(length=32), nullable=False),
        sa.Column("retention", sa.String(length=16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_image_uploads_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_image_uploads")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_image_uploads_storage_key")),
    )
    op.create_index(op.f("ix_image_uploads_user_id"), "image_uploads", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_image_uploads_user_id"), table_name="image_uploads")
    op.drop_table("image_uploads")
