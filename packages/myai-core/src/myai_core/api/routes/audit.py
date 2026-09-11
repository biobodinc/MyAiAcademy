from __future__ import annotations

from fastapi import APIRouter, Query

from myai_core.api.deps import AuditDep
from myai_core.audit.service import AuditCategory, AuditEventRead

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditEventRead])
def read_audit(
    audit: AuditDep,
    limit: int = Query(default=100, ge=1, le=1000),
    category: AuditCategory | None = None,
) -> list[AuditEventRead]:
    return [AuditEventRead.model_validate(e) for e in audit.recent(limit=limit, category=category)]
