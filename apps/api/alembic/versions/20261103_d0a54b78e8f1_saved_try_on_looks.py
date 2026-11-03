"""Persist user-owned try-on looks by occasion.

Revision ID: d0a54b78e8f1
Revises: cd5805e60f8a
Create Date: 2026-11-03 14:15:00+05:30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d0a54b78e8f1"
down_revision: str | None = "cd5805e60f8a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_try_on_looks",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("occasion", sa.String(length=20), nullable=False),
        sa.Column("look_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_saved_try_on_looks_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_saved_try_on_looks")),
    )
    op.create_index(op.f("ix_saved_try_on_looks_user_id"), "saved_try_on_looks", ["user_id"], unique=False)
    op.create_index(op.f("ix_saved_try_on_looks_occasion"), "saved_try_on_looks", ["occasion"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_saved_try_on_looks_occasion"), table_name="saved_try_on_looks")
    op.drop_index(op.f("ix_saved_try_on_looks_user_id"), table_name="saved_try_on_looks")
    op.drop_table("saved_try_on_looks")
