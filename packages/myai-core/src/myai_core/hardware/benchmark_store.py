"""Persist benchmark results so the report can show the last measurement."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from myai_core.db.models import HardwareBenchmark
from myai_core.hardware.benchmark import BenchmarkResult


class BenchmarkStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def latest(self) -> BenchmarkResult | None:
        row = self._session.scalars(
            select(HardwareBenchmark).order_by(HardwareBenchmark.ran_at.desc()).limit(1)
        ).first()
        if row is None:
            return None
        try:
            return BenchmarkResult.model_validate(row.result)
        except ValueError:
            return None  # a result written by an incompatible version; ignore, never crash

    def record(self, result: BenchmarkResult) -> None:
        self._session.add(
            HardwareBenchmark(ran_at=result.ran_at, result=result.model_dump(mode="json"))
        )
        self._session.flush()
