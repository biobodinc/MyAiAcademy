"""Projects: a named grouping for conversations, memories and documents.

Membership is a nullable column on each of the three, not a join table. A row belongs to at
most one project and is perfectly usable belonging to none, so a column says exactly that and
a join table would only add a way for it to say something else.

`ON DELETE SET NULL`, never CASCADE. What happens to a project's contents when the project
goes is the one decision here that could quietly destroy a year of someone's work, and the
database is not the right place to make it: the service asks the caller, every time.

Revision ID: 0011_projects
Revises: 0010_account_info
Create Date: 2026-09-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0011_projects"
down_revision = "0010_account_info"
branch_labels = None
depends_on = None

MEMBERS = ("conversations", "memories", "documents")

# `memories` carries an external-content FTS5 index kept current by triggers (migration
# 0002). SQLite has no real ALTER, so `batch_alter_table` copies the table and drops
# everything attached to the old one — triggers included — silently. Search would then
# return nothing for anything written afterwards, with no error anywhere. They are recreated
# verbatim below.
MEMORY_TRIGGERS = (
    "CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN "
    "INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content); END",
    "CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN "
    "INSERT INTO memories_fts(memories_fts, rowid, content) "
    "VALUES ('delete', old.id, old.content); END",
    "CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN "
    "INSERT INTO memories_fts(memories_fts, rowid, content) "
    "VALUES ('delete', old.id, old.content); "
    "INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content); END",
)


def _restore_memory_search() -> None:
    """Put the FTS triggers back, and reindex what is already there."""
    if op.get_bind().dialect.name != "sqlite":
        return
    for statement in MEMORY_TRIGGERS:
        op.execute(statement)
    op.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(64), nullable=False),
        sa.Column("ai_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_seq", sa.Integer(), nullable=True),
        sa.Column("sync_origin", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(["ai_id"], ["ai_profile.ai_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_sync_seq", "projects", ["sync_seq"])

    for table in MEMBERS:
        # Batch mode: SQLite cannot add a foreign key to an existing table in place, so
        # Alembic rebuilds it. Postgres ignores the ceremony and does the ALTER directly.
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("project_id", sa.String(64), nullable=True))
            batch.create_foreign_key(
                f"fk_{table}_project_id", "projects", ["project_id"], ["id"], ondelete="SET NULL"
            )
        op.create_index(f"ix_{table}_project_id", table, ["project_id"])
        if table == "memories":
            _restore_memory_search()


def downgrade() -> None:
    for table in MEMBERS:
        op.drop_index(f"ix_{table}_project_id", table_name=table)
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"fk_{table}_project_id", type_="foreignkey")
            batch.drop_column("project_id")
        if table == "memories":
            _restore_memory_search()
    op.drop_index("ix_projects_sync_seq", table_name="projects")
    op.drop_table("projects")
