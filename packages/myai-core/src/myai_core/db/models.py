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
