"""add norm source fields

Revision ID: 20260105143000
Revises: 20260104120000
Create Date: 2026-01-05 14:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260105143000"
down_revision: Union[str, None] = "20260104120000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("norms", sa.Column("source_reference", sa.String(length=255), nullable=True))
    op.add_column("norms", sa.Column("source_excerpt", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("norms", "source_excerpt")
    op.drop_column("norms", "source_reference")
