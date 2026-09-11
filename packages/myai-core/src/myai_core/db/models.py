"""ORM models for Phase 1.

Design notes
------------
* Every row that will later be synchronised between devices (spec §16, §72) carries
  ``version`` and ``updated_at`` from day one so that conflict detection does not require
  a painful migration later. ``origin_device_id`` is nullable until Phase 5 introduces
  device identity.
* JSON columns hold small, schema-validated lists (goals, interests). Pydantic models in
  the service layer are the source of truth for their shape.
* Timestamps are timezone-aware UTC. SQLite stores them as ISO-8601 text.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from myai_core.db.base import Base, utcnow


class AIProfile(Base):
    """The user's AI identity (spec §28, §78). One per installation for now."""

    __tablename__ = "ai_profile"

    ai_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    personality: Mapped[str] = mapped_column(Text, nullable=False, default="")
    communication_style: Mapped[str] = mapped_column(Text, nullable=False, default="")
    goals: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    interests: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    owner_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    origin_device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Preference(Base):
    """Key/value user preferences validated by ``myai_core.preferences.schemas``."""

    __tablename__ = "preferences"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[object] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class StorageConfig(Base):
    """The user-chosen MyAI storage root and optional per-category overrides (spec §21–§22)."""

    __tablename__ = "storage_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    root_path: Mapped[str] = mapped_column(Text, nullable=False)
    # {"models": "E:/MyAI-Models", ...}; categories absent here live under root_path.
    category_overrides: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    configured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SkillState(Base):
    """Per-skill learned state. Definitions live in the static catalog; this is progress.

    ``level`` is only ever changed by an evaluation (spec §33, §89): it starts at 0 for a
    skill that has not been learned and becomes 1 when learning completes.
    """

    __tablename__ = "skill_state"
    __table_args__ = (UniqueConstraint("ai_id", "skill_id", name="uq_skill_state_ai_skill"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ai_id: Mapped[str] = mapped_column(ForeignKey("ai_profile.ai_id", ondelete="CASCADE"))
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="unlearned")
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_evaluation_score: Mapped[float | None] = mapped_column(nullable=True)
    learned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Phase 3: which package version is installed and where (spec §36).
    package_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    installed_path: Mapped[str | None] = mapped_column(Text, nullable=True)


class Job(Base):
    """A background job (spec §40 shape). Phase 3 kinds: ``learn`` and ``evaluate``;
    Phase 4 adds ``train``. One job runs at a time."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    ai_id: Mapped[str] = mapped_column(ForeignKey("ai_profile.ai_id", ondelete="CASCADE"))
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    model_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    progress_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    compute_preset: Mapped[str | None] = mapped_column(String(16), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class SkillEvaluation(Base):
    """One benchmark run (spec §43, §42 history). The only thing that ever sets a level."""

    __tablename__ = "skill_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ai_id: Mapped[str] = mapped_column(ForeignKey("ai_profile.ai_id", ondelete="CASCADE"))
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    package_version: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[float] = mapped_column(nullable=False)
    level_before: Mapped[int] = mapped_column(Integer, nullable=False)
    level_after: Mapped[int] = mapped_column(Integer, nullable=False)
    area_scores: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    task_results: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )


class AuditEvent(Base):
    """Local security/activity log (spec §61). Summaries only, never private content."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class HardwareBenchmark(Base):
    """A recorded benchmark run (spec §30). The JSON is a ``BenchmarkResult``."""

    __tablename__ = "hardware_benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    result: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


# --- Phase 2: local AI --------------------------------------------------------------------


class InstalledModel(Base):
    """A model file present under the storage root's Models/ folder."""

    __tablename__ = "installed_models"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # catalog id
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    family: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    license_id: Mapped[str] = mapped_column(String(64), nullable=False)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ModelLicenseAcceptance(Base):
    """Explicit, per-model acceptance recorded before any download (spec §69)."""

    __tablename__ = "model_license_acceptances"

    model_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    license_id: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModelDownload(Base):
    __tablename__ = "model_downloads"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    bytes_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bytes_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ai_id: Mapped[str] = mapped_column(ForeignKey("ai_profile.ai_id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    origin_device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    model_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Ids of knowledge chunks shown to the model for this reply (provenance, spec §54).
    retrieved_chunk_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
    finish_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Memory(Base):
    """An explicit, user-visible fact the AI remembers (spec §44). Never auto-created."""

    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )  # stable across devices
    ai_id: Mapped[str] = mapped_column(ForeignKey("ai_profile.ai_id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="fact")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    origin_device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Document(Base):
    """A knowledge source (spec §45): a file the user added for local retrieval."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ai_id: Mapped[str] = mapped_column(ForeignKey("ai_profile.ai_id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ready")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
