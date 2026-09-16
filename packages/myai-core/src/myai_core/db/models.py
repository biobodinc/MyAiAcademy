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

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from ulid import ULID

from myai_core.db.base import Base, utcnow


def new_message_uid() -> str:
    return f"msg_{ULID()}"


class SyncedBase(Base):
    """A row that travels between a user's own devices (spec §16, §72).

    Both columns are maintained by the listener in ``sync/changes.py``, never by a service.
    ``sync_seq`` is this installation's counter at the moment the row last changed;
    ``sync_origin`` is the installation that made that change, which is what stops an edit
    travelling forever around a ring of three devices.
    """

    __abstract__ = True

    sync_seq: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    sync_origin: Mapped[str | None] = mapped_column(String(64), nullable=True)


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


class SkillState(SyncedBase):
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
    # Phase 4: when training last replaced this skill's instructions (spec §37).
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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


class TrainingRun(Base):
    """One training run (spec §37, §40): the record of a search for better instructions.

    The row is written when the run starts and updated after every round, so a run
    interrupted by a crash leaves both an explanation and the best candidate it had found.
    That candidate is where the next run starts, which is what makes training resumable
    across restarts rather than only across a pause.

    Levels are not written here. ``evaluation_id`` points at the benchmark run that
    measured the result, and that evaluation is what set the level (ADR-0007).
    """

    __tablename__ = "training_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ai_id: Mapped[str] = mapped_column(ForeignKey("ai_profile.ai_id", ondelete="CASCADE"))
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    package_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    budget_seconds: Mapped[float] = mapped_column(nullable=False, default=0.0)
    target_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    focus_area: Mapped[str | None] = mapped_column(String(64), nullable=True)
    seed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rounds_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rounds: Mapped[list[object]] = mapped_column(JSON, nullable=False, default=list)
    best_candidate: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    baseline_practice: Mapped[float | None] = mapped_column(nullable=True)
    best_practice: Mapped[float | None] = mapped_column(nullable=True)
    benchmark_before: Mapped[float | None] = mapped_column(nullable=True)
    benchmark_after: Mapped[float | None] = mapped_column(nullable=True)
    level_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    level_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    evaluation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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


class Device(Base):
    """A client allowed to act as this AI (spec §47, §51-§53).

    "Device" is the spec's word; on one machine these are really *clients*: the desktop
    app, the CLI, a third-party tool. Each holds its own credential so a grant can be
    revoked on its own, and every action can say which client performed it.

    Only the SHA-256 of a credential is stored. The secret itself is shown once, when the
    credential is issued, and cannot be recovered afterwards — which is the point.
    """

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    platform: Mapped[str | None] = mapped_column(String(120), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    """What this client may do (spec §53). An empty list grants nothing but pairing itself."""


class PairingCode(Base):
    """A short-lived, single-use code that lets a new client ask for its own credential.

    The code is stored hashed for the same reason a password is: the database should not
    hand an attacker a working credential. Codes expire, are used once, and every attempt
    is counted so guessing is visible and bounded.
    """

    __tablename__ = "pairing_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    """What the owner approved when they made this code. The client cannot widen it."""


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
    """The hash we computed while downloading. Present even when nothing verified it."""
    verified_against: Mapped[str] = mapped_column(String(24), nullable=False, default="none")
    """What ``sha256`` was checked against: pinned, publisher-hash, host-etag or none."""
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


class Project(SyncedBase):
    """A named piece of work: the conversations, memories and documents that belong together.

    A project is a *grouping*, not a container. Nothing lives inside it — conversations,
    memories and documents carry a nullable `project_id` and are perfectly usable with none.
    That shape is what makes the delete question answerable without losing anything: see
    `ProjectService.delete`.
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ai_id: Mapped[str] = mapped_column(ForeignKey("ai_profile.ai_id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    """Archiving is the reversible way to get a project out of the way. Deleting is the other
    one, and it asks what should happen to the contents rather than guessing."""


class Conversation(SyncedBase):
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
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    """Which project this belongs to, if any. `SET NULL` rather than `CASCADE`: losing a
    project must never take a year of conversation with it."""


class Message(SyncedBase):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, default=new_message_uid
    )
    """Stable across devices. The primary key is local and cannot be, so sync uses this."""
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


class Memory(SyncedBase):
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
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )


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
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)


# --------------------------------------------------------------------------------------
# Phase 7: synchronisation between a user's own installations (spec §16, §18, §72).
# --------------------------------------------------------------------------------------


class SyncIdentity(Base):
    """This installation's name among the user's devices, and its logical clock.

    The clock is a plain counter, not a timestamp. Two machines' wall clocks disagree —
    sometimes by hours, and a laptop that has been asleep can disagree with itself — so
    ordering changes by ``updated_at`` would make sync depend on something no one controls.
    ``next_seq`` is only ever compared against a cursor from *this* installation, which
    makes "everything you have not seen from me" an exact question.
    """

    __tablename__ = "sync_identity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    install_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    next_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SyncTombstone(Base):
    """A row that was deleted here, so the deletion can travel like any other change.

    Without these, sync would treat a deletion as "the other device has something I lack"
    and helpfully restore it. A delete that will not stay deleted is worse than no sync.
    """

    __tablename__ = "sync_tombstones"
    __table_args__ = (UniqueConstraint("entity", "uid", name="uq_tombstone_entity_uid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity: Mapped[str] = mapped_column(String(32), nullable=False)
    uid: Mapped[str] = mapped_column(String(64), nullable=False)
    sync_seq: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sync_origin: Mapped[str | None] = mapped_column(String(64), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SyncPeer(Base):
    """Another installation of the user's own, and how far the two have got.

    The two cursors are deliberately separate. ``received_through`` is a fact about the
    peer's clock and ``sent_through`` about ours; conflating them is how sync engines end up
    skipping changes after a restore from backup.
    """

    __tablename__ = "sync_peers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    peer_install_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="Another device")
    device_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    """The paired credential this peer uses, when it reached us over the network."""
    received_through: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_through: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SyncConflict(Base):
    """Two devices changed the same thing, and this is the version that did not win.

    Sync has to pick one, but it does not have to throw the other away. The losing side is
    kept whole here so the user can look at it and put it back. Silently discarding a
    person's writing because two clocks disagreed is not a trade-off this program makes.
    """

    __tablename__ = "sync_conflicts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity: Mapped[str] = mapped_column(String(32), nullable=False)
    uid: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    kept: Mapped[str] = mapped_column(String(16), nullable=False)
    """``local`` or ``remote``: which side is in the table now."""
    losing_payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    losing_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    losing_origin: Mapped[str | None] = mapped_column(String(64), nullable=True)
    losing_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AccountInfo(Base):
    """This device's link to a central account (Phase 5).

    Each device stores its account_id here to know which account on the central server
    it belongs to. This is a singleton row (id=1) created when the device first joins
    an account, and updated if the account association changes.
    """

    __tablename__ = "account_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    """Singleton: always id=1."""

    account_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    """16-digit account ID from the central server, or None if not yet paired."""

    account_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    """Display name of the account (for reference)."""

    paired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    """When this device was first paired with the account."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
