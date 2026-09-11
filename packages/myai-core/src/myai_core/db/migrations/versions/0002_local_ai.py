"""Phase 2 schema: installed models, downloads, conversations, memory, knowledge (FTS5).

Revision ID: 0002_local_ai
Revises: 0001_initial
Create Date: 2026-09-11
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "0002_local_ai"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _ts(name: str, nullable: bool = False) -> sa.Column[datetime]:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "installed_models",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("family", sa.String(64), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("license_id", sa.String(64), nullable=False),
        _ts("installed_at"),
        _ts("last_used_at", nullable=True),
    )
    op.create_table(
        "model_license_acceptances",
        sa.Column("model_id", sa.String(64), primary_key=True),
        sa.Column("license_id", sa.String(64), nullable=False),
        _ts("accepted_at"),
    )
    op.create_table(
        "model_downloads",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("model_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("bytes_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bytes_total", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        _ts("started_at"),
        _ts("finished_at", nullable=True),
        _ts("updated_at"),
    )
    op.create_index("ix_model_downloads_model_id", "model_downloads", ["model_id"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "ai_id",
            sa.String(64),
            sa.ForeignKey("ai_profile.ai_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False, server_default="New conversation"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("origin_device_id", sa.String(64), nullable=True),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "conversation_id",
            sa.String(64),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        _ts("created_at"),
        sa.Column("model_id", sa.String(64), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("retrieved_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("finish_reason", sa.String(32), nullable=True),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.create_table(
        "memories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uid", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "ai_id",
            sa.String(64),
            sa.ForeignKey("ai_profile.ai_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False, server_default="fact"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("origin_device_id", sa.String(64), nullable=True),
    )
    # External-content FTS5 index kept in sync by triggers (standard SQLite pattern).
    op.execute(
        "CREATE VIRTUAL TABLE memories_fts USING fts5("
        "content, content='memories', content_rowid='id', tokenize='porter unicode61')"
    )
    op.execute(
        "CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN "
        "INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content); END"
    )
    op.execute(
        "CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN "
        "INSERT INTO memories_fts(memories_fts, rowid, content) "
        "VALUES ('delete', old.id, old.content); END"
    )
    op.execute(
        "CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN "
        "INSERT INTO memories_fts(memories_fts, rowid, content) "
        "VALUES ('delete', old.id, old.content); "
        "INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content); END"
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "ai_id",
            sa.String(64),
            sa.ForeignKey("ai_profile.ai_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("media_type", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="ready"),
        sa.Column("error", sa.Text(), nullable=True),
        _ts("added_at"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.String(64),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.execute(
        "CREATE VIRTUAL TABLE chunks_fts USING fts5("
        "content, content='chunks', content_rowid='id', tokenize='porter unicode61')"
    )
    op.execute(
        "CREATE TRIGGER chunks_ai AFTER INSERT ON chunks BEGIN "
        "INSERT INTO chunks_fts(rowid, content) VALUES (new.id, new.content); END"
    )
    op.execute(
        "CREATE TRIGGER chunks_ad AFTER DELETE ON chunks BEGIN "
        "INSERT INTO chunks_fts(chunks_fts, rowid, content) "
        "VALUES ('delete', old.id, old.content); END"
    )


def downgrade() -> None:
    for trigger in ("chunks_ad", "chunks_ai", "memories_au", "memories_ad", "memories_ai"):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}")
    op.execute("DROP TABLE IF EXISTS chunks_fts")
    op.execute("DROP TABLE IF EXISTS memories_fts")
    op.drop_index("ix_chunks_document_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("memories")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_index("ix_model_downloads_model_id", table_name="model_downloads")
    op.drop_table("model_downloads")
    op.drop_table("model_license_acceptances")
    op.drop_table("installed_models")
