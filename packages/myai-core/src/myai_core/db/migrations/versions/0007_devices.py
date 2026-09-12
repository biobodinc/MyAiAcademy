"""Phase 5: per-client credentials and pairing codes.

Credentials and codes are stored as SHA-256 hashes, never as the secret itself, so a copy
of this database does not hand anyone a working key.

Revision ID: 0007_devices
Revises: 0006_training
Create Date: 2026-09-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_devices"
down_revision = "0006_training"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False, server_default="unknown"),
        sa.Column("platform", sa.String(120), nullable=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_devices_token_hash", "devices", ["token_hash"])

    op.create_table(
        "pairing_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("label", sa.String(120), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_id", sa.String(64), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("pairing_codes")
    op.drop_index("ix_devices_token_hash", table_name="devices")
    op.drop_table("devices")
