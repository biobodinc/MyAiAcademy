"""Database connection for the account server."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from myai_server.config import ServerSettings
from myai_server.models import Base

__all__ = ["Base", "create_engine_from_env", "init_db", "make_engine", "make_session_factory"]


def make_engine(url: str) -> Engine:
    # pool_pre_ping costs one round trip on checkout and saves the first request after an
    # idle period from failing on a connection the database closed while nobody was looking.
    return create_engine(url, echo=False, pool_pre_ping=True)


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


def create_engine_from_env(settings: ServerSettings | None = None) -> tuple[Engine, sessionmaker]:
    """Create the engine and session factory described by the environment."""
    settings = settings or ServerSettings()
    engine = make_engine(settings.database_url)
    return engine, make_session_factory(engine)


def init_db(engine: Engine) -> None:
    """Create any missing tables.

    Enough for a server whose schema only grows. The day a column has to change type or a
    backfill has to run, this needs to become Alembic — the same way `myai_core` already
    manages the local database.
    """
    Base.metadata.create_all(engine)
