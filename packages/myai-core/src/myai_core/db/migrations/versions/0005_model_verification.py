"""Record what an installed model's hash was verified against.

Until now the UI showed a SHA-256 for every installed model, which read as "verified"
when it was only "this is what we computed". Existing rows are backfilled as unverified
because we cannot know retrospectively what they were checked against.

Revision ID: 0005_model_verification
Revises: 0004_skills
Create Date: 2026-09-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_model_verification"
down_revision = "0004_skills"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("installed_models") as batch:
        batch.add_column(
            sa.Column("verified_against", sa.String(24), nullable=False, server_default="none")
        )


def downgrade() -> None:
    with op.batch_alter_table("installed_models") as batch:
        batch.drop_column("verified_against")
