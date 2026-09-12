from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query

from myai_core.api.deps import AuditDep
from myai_core.audit.service import AuditCategory, AuditEventRead

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventRead])
def read_audit(
    audit: AuditDep,
    limit: int = Query(default=100, ge=1, le=1000),
    category: AuditCategory | None = None,
    device_id: Annotated[str | None, Query(description="Only what this client did.")] = None,
    since: Annotated[datetime | None, Query(description="Only events at or after this.")] = None,
) -> list[AuditEventRead]:
    """The local activity log. Summaries only: it never holds message or document text."""
    events = audit.recent(limit=limit, category=category, device_id=device_id, since=since)
    return [AuditEventRead.model_validate(e) for e in events]
