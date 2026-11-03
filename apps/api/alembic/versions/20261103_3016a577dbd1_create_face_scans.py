"""create face_scans

Revision ID: 3016a577dbd1
Revises: ba1248c6a390
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3016a577dbd1"
down_revision: str | None = "ba1248c6a390"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "face_scans",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("image_id", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("face_count", sa.Integer(), nullable=False),
        sa.Column("detection_confidence", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["image_id"],
            ["image_uploads.id"],
            name=op.f("fk_face_scans_image_id_image_uploads"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_face_scans_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_face_scans")),
    )
    op.create_index(op.f("ix_face_scans_image_id"), "face_scans", ["image_id"])
    op.create_index(op.f("ix_face_scans_user_id"), "face_scans", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_face_scans_user_id"), table_name="face_scans")
    op.drop_index(op.f("ix_face_scans_image_id"), table_name="face_scans")
    op.drop_table("face_scans")
