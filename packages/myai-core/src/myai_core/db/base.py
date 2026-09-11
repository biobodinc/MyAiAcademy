"""Engine, session factory and declarative base."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def make_engine(database_file: Path | str) -> Engine:
    """Create a SQLite engine with sane durability/concurrency pragmas.

    * WAL journal: readers do not block the writer (the UI polls while jobs write).
    * ``synchronous=NORMAL``: safe with WAL, far fewer fsyncs than FULL.
    * ``foreign_keys=ON``: SQLite disables FK enforcement per-connection by default.
    """
    if database_file == ":memory:":
        url = "sqlite+pysqlite:///:memory:"
    else:
        url = f"sqlite+pysqlite:///{Path(database_file)}"
    engine = create_engine(url, future=True)

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        if database_file != ":memory:":
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Transactional scope: commit on success, roll back on error."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
