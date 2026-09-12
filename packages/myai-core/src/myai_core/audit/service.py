from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from myai_core.db.models import AuditEvent
from myai_core.schemas import ApiModel


class AuditCategory(StrEnum):
    PROFILE = "profile"
    STORAGE = "storage"
    PREFERENCES = "preferences"
    SECURITY = "security"
    PRIVACY = "privacy"
    SYSTEM = "system"


class AuditEventRead(ApiModel):
    id: int
    occurred_at: datetime
    category: AuditCategory
    action: str
    summary: str
    details: dict[str, object]
    device_id: str | None

    model_config = ConfigDict(
        from_attributes=True, json_schema_serialization_defaults_required=True
    )


class AuditService:
    """Records *what happened*, never private content.

    Callers must pass summaries that are safe to display and safe to keep: no memory
    text, no document contents, no tokens. ``details`` is for small structured facts
    such as a storage path or a version number.
    """

    def __init__(self, session: Session, actor_device_id: str | None = None) -> None:
        self._session = session
        self._actor_device_id = actor_device_id
        """Who is acting, when the caller is known. Recorded on every event it writes."""

    def record(
        self,
        category: AuditCategory,
        action: str,
        summary: str,
        details: dict[str, object] | None = None,
        device_id: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            category=category.value,
            action=action,
            summary=summary,
            details=details or {},
            device_id=device_id or self._actor_device_id,
        )
        self._session.add(event)
        self._session.flush()
        return event

    def recent(
        self,
        limit: int = 100,
        category: AuditCategory | None = None,
        device_id: str | None = None,
        since: datetime | None = None,
    ) -> list[AuditEvent]:
        """Most recent first, narrowed by category, by which client acted, or by date."""
        stmt = select(AuditEvent).order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        if category is not None:
            stmt = stmt.where(AuditEvent.category == category.value)
        if device_id is not None:
            stmt = stmt.where(AuditEvent.device_id == device_id)
        if since is not None:
            stmt = stmt.where(AuditEvent.occurred_at >= since)
        return list(self._session.scalars(stmt.limit(max(1, min(limit, 1000)))).all())
