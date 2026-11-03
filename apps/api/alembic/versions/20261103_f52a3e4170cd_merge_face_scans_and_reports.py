"""merge face scans and report/image upload migrations

Revision ID: f52a3e4170cd
Revises: cd5805e60f8a, 3016a577dbd1
Create Date: 2026-11-03
"""

from collections.abc import Sequence

revision: str = "f52a3e4170cd"
down_revision: tuple[str, str] = ("cd5805e60f8a", "3016a577dbd1")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
