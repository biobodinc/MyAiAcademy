"""Phase 1 schema: AI profile, preferences, storage config, skill state, audit log.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_profile",
        sa.Column("ai_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("personality", sa.Text(), nullable=False, server_default=""),
        sa.Column("communication_style", sa.Text(), nullable=False, server_default=""),
        sa.Column("goals", sa.JSON(), nullable=False),
        sa.Column("interests", sa.JSON(), nullable=False),
        sa.Column("owner_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("origin_device_id", sa.String(64), nullable=True),
    )
    op.create_table(
        "preferences",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "storage_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("root_path", sa.Text(), nullable=False),
        sa.Column("category_overrides", sa.JSON(), nullable=False),
        sa.Column("configured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "skill_state",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "ai_id",
            sa.String(64),
            sa.ForeignKey("ai_profile.ai_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("skill_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="unlearned"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_evaluation_score", sa.Float(), nullable=True),
        sa.Column("learned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("ai_id", "skill_id", name="uq_skill_state_ai_skill"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("device_id", sa.String(64), nullable=True),
    )
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])
    op.create_index("ix_audit_events_category", "audit_events", ["category"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_category", table_name="audit_events")
    op.drop_index("ix_audit_events_occurred_at", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("skill_state")
    op.drop_table("storage_config")
    op.drop_table("preferences")
    op.drop_table("ai_profile")
