from pathlib import Path

from alembic import command
from sqlalchemy import inspect

from myai_core.db.base import make_engine
from myai_core.db.migrate import alembic_config, upgrade_to_head


def test_upgrade_and_downgrade_round_trip(tmp_path: Path) -> None:
    engine = make_engine(tmp_path / "m.sqlite3")
    upgrade_to_head(engine)
    tables = set(inspect(engine).get_table_names())
    assert {"ai_profile", "preferences", "storage_config", "skill_state", "audit_events"} <= tables
    command.downgrade(alembic_config(engine), "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    upgrade_to_head(engine)  # idempotent re-upgrade
    engine.dispose()


def test_models_match_migrations(tmp_path: Path) -> None:
    """The ORM metadata and the migration chain must describe the same tables/columns."""
    from myai_core.db.base import Base

    engine = make_engine(tmp_path / "m.sqlite3")
    upgrade_to_head(engine)
    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        db_columns = {c["name"] for c in inspector.get_columns(table.name)}
        assert db_columns == {c.name for c in table.columns}, table.name
    engine.dispose()
