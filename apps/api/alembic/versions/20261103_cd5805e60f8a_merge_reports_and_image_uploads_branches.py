"""merge reports and image uploads branches

Revision ID: cd5805e60f8a
Revises: b7e4c20f91a6, ba1248c6a390
Create Date: 2026-11-03 08:05:24.441398+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "cd5805e60f8a"
down_revision: str | None = ("b7e4c20f91a6", "ba1248c6a390")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
