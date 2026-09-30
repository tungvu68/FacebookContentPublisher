"""SQLite persistence adapter."""

from facebook_content_publisher.infrastructure.database.engine import (
    Database,
    create_database,
)

__all__ = ["Database", "create_database"]
