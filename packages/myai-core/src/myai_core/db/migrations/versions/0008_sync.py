"""Phase 7: keeping a user's own devices in step.

Adds a logical clock to the rows that travel, a stable identifier for messages, and the
four tables sync needs: who we are, who we sync with, what was deleted, and what a conflict
displaced.

Messages had only an autoincrementing primary key, which is a fact about one database's
insert order and means nothing on another machine. Existing rows are given a stable uid
here; the value is generated in SQL so that a database with a long history does not have to
be loaded into Python to be upgraded.

Revision ID: 0008_sync
Revises: 0007_devices
Create Date: 2026-09-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_sync"
down_revision = "0007_devices"
branch_labels = None
depends_on = None

SYNCED_TABLES = ("conversations", "messages", "memories", "skill_state")


def upgrade() -> None:
    for table in SYNCED_TABLES:
        op.add_column(table, sa.Column("sync_seq", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("sync_origin", sa.String(64), nullable=True))
        op.create_index(f"ix_{table}_sync_seq", table, ["sync_seq"])

    # A stable identifier for messages. Crockford-ish base32 is not worth reproducing in
    # SQL; a hex string from randomblob is just as unique and just as opaque.
    op.add_column("messages", sa.Column("uid", sa.String(64), nullable=True))
    op.execute("UPDATE messages SET uid = 'msg_' || lower(hex(randomblob(16))) WHERE uid IS NULL")
    # Backfilled, so it can now be required. SQLite cannot alter a column in place; batch
    # mode rebuilds the table, which is why the backfill above has to come first.
    with op.batch_alter_table("messages") as batch:
        batch.alter_column("uid", existing_type=sa.String(64), nullable=False)
    op.create_index("ix_messages_uid", "messages", ["uid"], unique=True)

    op.create_table(
        "sync_identity",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("install_id", sa.String(64), nullable=False, unique=True),
        sa.Column("next_seq", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "sync_tombstones",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity", sa.String(32), nullable=False),
        sa.Column("uid", sa.String(64), nullable=False),
        sa.Column("sync_seq", sa.Integer(), nullable=False),
        sa.Column("sync_origin", sa.String(64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("entity", "uid", name="uq_tombstone_entity_uid"),
    )
    op.create_index("ix_sync_tombstones_sync_seq", "sync_tombstones", ["sync_seq"])

    op.create_table(
        "sync_peers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("peer_install_id", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False, server_default="Another device"),
        sa.Column("device_id", sa.String(64), nullable=True),
        sa.Column("received_through", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_through", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "sync_conflicts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity", sa.String(32), nullable=False),
        sa.Column("uid", sa.String(64), nullable=False),
        sa.Column("kept", sa.String(16), nullable=False),
        sa.Column("losing_payload", sa.JSON(), nullable=False),
        sa.Column("losing_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("losing_origin", sa.String(64), nullable=True),
        sa.Column("losing_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sync_conflicts_uid", "sync_conflicts", ["uid"])


def downgrade() -> None:
    op.drop_index("ix_sync_conflicts_uid", table_name="sync_conflicts")
    op.drop_table("sync_conflicts")
    op.drop_table("sync_peers")
    op.drop_index("ix_sync_tombstones_sync_seq", table_name="sync_tombstones")
    op.drop_table("sync_tombstones")
    op.drop_table("sync_identity")
    op.drop_index("ix_messages_uid", table_name="messages")
    op.drop_column("messages", "uid")
    for table in SYNCED_TABLES:
        op.drop_index(f"ix_{table}_sync_seq", table_name=table)
        op.drop_column(table, "sync_origin")
        op.drop_column(table, "sync_seq")
