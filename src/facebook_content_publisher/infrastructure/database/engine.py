"""Database paths, engine, and transaction factory."""

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True, slots=True)
class Database:
    path: Path
    engine: Engine
    sessions: sessionmaker[Session]


def default_database_path() -> Path:
    """Return the configured or Windows-appropriate application database path."""

    override = os.getenv("FCP_DATA_DIR")
    data_dir = Path(override) if override else user_data_path("FacebookContentPublisher")
    return data_dir / "data" / "app.db"


def create_database(path: Path | None = None) -> Database:
    """Create an SQLite engine; callers may override the path for tests."""

    database_path = (path or default_database_path()).resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection: object, connection_record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return Database(database_path, engine, sessionmaker(engine, expire_on_commit=False))
