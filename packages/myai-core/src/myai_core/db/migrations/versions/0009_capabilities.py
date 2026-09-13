"""Phase 9: what a paired client is allowed to do.

Clients paired before this migration were granted everything a client could do — there was
no narrower option — so recording the full set for them is a statement of what is already
true rather than a widening. New pairings get whatever the owner approved when they made
the code, which is usually far less.

Revoked clients are left empty: a revoked credential grants nothing, and writing a full
grant onto one would make the audit trail read as though it had been re-authorised.

Revision ID: 0009_capabilities
Revises: 0008_sync
Create Date: 2026-09-13
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0009_capabilities"
down_revision = "0008_sync"
branch_labels = None
depends_on = None

_EXISTING_GRANT = json.dumps(
    [
        "status:read",
        "hardware:read",
        "chat:read",
        "chat:write",
        "memory:read",
        "memory:write",
        "knowledge:read",
        "knowledge:write",
        "skills:read",
        "skills:train",
        "models:read",
        "models:manage",
        "sync",
        "activity:read",
    ]
)


def upgrade() -> None:
    op.add_column("devices", sa.Column("capabilities", sa.JSON(), nullable=True))
    op.add_column("pairing_codes", sa.Column("capabilities", sa.JSON(), nullable=True))

    op.execute(
        sa.text("UPDATE devices SET capabilities = :grant WHERE revoked_at IS NULL").bindparams(
            grant=_EXISTING_GRANT
        )
    )
    op.execute("UPDATE devices SET capabilities = '[]' WHERE capabilities IS NULL")
    op.execute("UPDATE pairing_codes SET capabilities = '[]' WHERE capabilities IS NULL")

    for table in ("devices", "pairing_codes"):
        with op.batch_alter_table(table) as batch:
            batch.alter_column("capabilities", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    op.drop_column("pairing_codes", "capabilities")
    op.drop_column("devices", "capabilities")
