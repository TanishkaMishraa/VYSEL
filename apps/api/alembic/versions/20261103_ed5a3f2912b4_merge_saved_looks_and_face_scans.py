"""Merge the saved-look and face-scan migration branches.

Revision ID: ed5a3f2912b4
Revises: d0a54b78e8f1, f52a3e4170cd
Create Date: 2026-11-03
"""

from collections.abc import Sequence

revision: str = "ed5a3f2912b4"
down_revision: tuple[str, str] = ("d0a54b78e8f1", "f52a3e4170cd")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
