"""Disable the historical admin account created with a public password.

Revision ID: 20260818120000
Revises: 20260321150000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260818120000"
down_revision = "20260321150000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            """
            UPDATE user_accounts
            SET status = 'disabled', password_hash = NULL
            WHERE email = 'admin@localhost'
            """
        )
    )


def downgrade() -> None:
    # The public password is intentionally never restored.
    pass
