"""Alembic environment. Runs against the engine handed over by ``myai_core.db.migrate``."""

from __future__ import annotations

from alembic import context
from sqlalchemy import Engine

from myai_core.db import models  # noqa: F401  (registers tables on Base.metadata)
from myai_core.db.base import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine: Engine | None = context.config.attributes.get("engine")
    if engine is None:  # pragma: no cover - CLI usage only
        from sqlalchemy import create_engine

        url = context.config.get_main_option("sqlalchemy.url")
        if url is None:
            raise RuntimeError("sqlalchemy.url is not configured")
        engine = create_engine(url)

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite cannot ALTER most things without table rebuild
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
