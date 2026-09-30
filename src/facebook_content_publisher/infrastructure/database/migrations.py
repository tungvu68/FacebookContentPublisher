"""Alembic migration entry points."""

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config


def upgrade_database(database_path: Path, revision: str = "head") -> None:
    """Upgrade a database using the project's Alembic configuration."""

    project_root = (
        Path(sys._MEIPASS)  # type: ignore[attr-defined]
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parents[4]
    )
    config = Config(project_root / "alembic.ini")
    config.set_main_option("script_location", str(project_root / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.resolve().as_posix()}")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(config, revision)
