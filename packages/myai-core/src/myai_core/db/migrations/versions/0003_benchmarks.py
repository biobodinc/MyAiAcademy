"""Hardware benchmark results (spec §30).

Revision ID: 0003_benchmarks
Revises: 0002_local_ai
Create Date: 2026-09-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_benchmarks"
down_revision = "0002_local_ai"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hardware_benchmarks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ran_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
    )
    op.create_index("ix_hardware_benchmarks_ran_at", "hardware_benchmarks", ["ran_at"])


def downgrade() -> None:
    op.drop_index("ix_hardware_benchmarks_ran_at", table_name="hardware_benchmarks")
    op.drop_table("hardware_benchmarks")
