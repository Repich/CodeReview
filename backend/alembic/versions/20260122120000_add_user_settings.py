"""add user settings jsonb

Revision ID: 20260122120000
Revises: 20260119130000
Create Date: 2026-01-22 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260122120000"
down_revision = "20260119130000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_accounts",
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.execute("UPDATE user_accounts SET settings = '{}'::jsonb WHERE settings IS NULL")


def downgrade() -> None:
    op.drop_column("user_accounts", "settings")
