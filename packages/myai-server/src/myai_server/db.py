"""Database connection and initialization for the account server."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from myai_server.models import Base


def create_engine_from_env() -> tuple:
    """Create SQLAlchemy engine from environment variables."""
    import os

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "myai_academy")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")

    url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    engine = create_engine(url, echo=False)
    session_factory = sessionmaker(bind=engine)
    return engine, session_factory


def init_db(engine) -> None:
    """Create all tables."""
    Base.metadata.create_all(engine)
