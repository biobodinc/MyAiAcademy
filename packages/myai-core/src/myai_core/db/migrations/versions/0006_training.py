"""Phase 4: training runs and the marker for a trained skill.

A training run is recorded from the moment it starts and updated after every round, so a
run interrupted by a crash still holds the best candidate it had found. Levels are not
stored here: ``evaluation_id`` points at the benchmark run that set one.

Revision ID: 0006_training
Revises: 0005_model_verification
Create Date: 2026-09-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_training"
down_revision = "0005_model_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("skill_state") as batch:
        batch.add_column(sa.Column("trained_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "training_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ai_id", sa.String(64), sa.ForeignKey("ai_profile.ai_id", ondelete="CASCADE")),
        sa.Column("skill_id", sa.String(64), nullable=False),
        sa.Column("job_id", sa.String(64), nullable=True),
        sa.Column("model_id", sa.String(64), nullable=False),
        sa.Column("package_version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("budget_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("target_level", sa.Integer(), nullable=True),
        sa.Column("focus_area", sa.String(64), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rounds_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rounds", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("best_candidate", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("baseline_practice", sa.Float(), nullable=True),
        sa.Column("best_practice", sa.Float(), nullable=True),
        sa.Column("benchmark_before", sa.Float(), nullable=True),
        sa.Column("benchmark_after", sa.Float(), nullable=True),
        sa.Column("level_before", sa.Integer(), nullable=True),
        sa.Column("level_after", sa.Integer(), nullable=True),
        sa.Column("applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("evaluation_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_training_runs_skill_id", "training_runs", ["skill_id"])
    op.create_index("ix_training_runs_started_at", "training_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_training_runs_started_at", table_name="training_runs")
    op.drop_index("ix_training_runs_skill_id", table_name="training_runs")
    op.drop_table("training_runs")
    with op.batch_alter_table("skill_state") as batch:
        batch.drop_column("trained_at")
