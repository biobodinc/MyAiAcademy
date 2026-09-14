"""Phase 5: Local account info linking device to central account.

Each device stores its account_id here to know which account on the central server
it belongs to. This is a singleton row (id=1) created when the device first joins
an account.

Revision ID: 0010_account_info
Revises: 0009_capabilities
Create Date: 2026-09-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_account_info"
down_revision = "0009_capabilities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_info",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.String(16), nullable=True),
        sa.Column("account_name", sa.String(128), nullable=True),
        sa.Column("paired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("account_info")
