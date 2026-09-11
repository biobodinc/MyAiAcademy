"""Phase 3: skill packages, jobs and evaluations.

Revision ID: 0004_skills
Revises: 0003_benchmarks
Create Date: 2026-09-11
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "0004_skills"
down_revision = "0003_benchmarks"
branch_labels = None
depends_on = None


def _ts(name: str, nullable: bool = False) -> sa.Column[datetime]:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    with op.batch_alter_table("skill_state") as batch:
        batch.add_column(sa.Column("package_version", sa.String(32), nullable=True))
        batch.add_column(sa.Column("installed_path", sa.Text(), nullable=True))

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("ai_id", sa.String(64), sa.ForeignKey("ai_profile.ai_id", ondelete="CASCADE")),
        sa.Column("skill_id", sa.String(64), nullable=False),
        sa.Column("model_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("progress_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("compute_preset", sa.String(16), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=False),
        _ts("created_at"),
        _ts("started_at", nullable=True),
        _ts("finished_at", nullable=True),
        _ts("updated_at"),
    )
    op.create_index("ix_jobs_skill_id", "jobs", ["skill_id"])

    op.create_table(
        "skill_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ai_id", sa.String(64), sa.ForeignKey("ai_profile.ai_id", ondelete="CASCADE")),
        sa.Column("skill_id", sa.String(64), nullable=False),
        sa.Column("job_id", sa.String(64), nullable=True),
        sa.Column("model_id", sa.String(64), nullable=False),
        sa.Column("package_version", sa.String(32), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("level_before", sa.Integer(), nullable=False),
        sa.Column("level_after", sa.Integer(), nullable=False),
        sa.Column("area_scores", sa.JSON(), nullable=False),
        sa.Column("task_results", sa.JSON(), nullable=False),
        _ts("evaluated_at"),
    )
    op.create_index("ix_skill_evaluations_skill_id", "skill_evaluations", ["skill_id"])
    op.create_index("ix_skill_evaluations_evaluated_at", "skill_evaluations", ["evaluated_at"])


def downgrade() -> None:
    op.drop_index("ix_skill_evaluations_evaluated_at", table_name="skill_evaluations")
    op.drop_index("ix_skill_evaluations_skill_id", table_name="skill_evaluations")
    op.drop_table("skill_evaluations")
    op.drop_index("ix_jobs_skill_id", table_name="jobs")
    op.drop_table("jobs")
    with op.batch_alter_table("skill_state") as batch:
        batch.drop_column("installed_path")
        batch.drop_column("package_version")
