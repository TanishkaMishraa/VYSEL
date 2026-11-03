"""Record the product-matches and analysis migration graph merge.

Revision ID: 6c27e11d8a4f
Revises: e3c91f7a2b54
Create Date: 2026-11-04
"""

from collections.abc import Sequence

revision: str = "6c27e11d8a4f"
down_revision: str = "e3c91f7a2b54"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
