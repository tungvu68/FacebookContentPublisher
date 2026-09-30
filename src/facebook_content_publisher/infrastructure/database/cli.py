"""Database command-line helpers used by scripts and developers."""

import argparse
from pathlib import Path

from facebook_content_publisher.infrastructure.database.engine import (
    create_database,
    default_database_path,
)
from facebook_content_publisher.infrastructure.database.migrations import upgrade_database
from facebook_content_publisher.infrastructure.database.seed import seed_development_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Database utilities")
    parser.add_argument("command", choices=("upgrade", "seed", "initialize"))
    parser.add_argument("--database", type=Path, default=default_database_path())
    args = parser.parse_args()

    if args.command in {"upgrade", "initialize"}:
        upgrade_database(args.database)
    if args.command in {"seed", "initialize"}:
        database = create_database(args.database)
        count = seed_development_data(database.sessions)
        print(f"Seed complete: {count} country profile(s) inserted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
