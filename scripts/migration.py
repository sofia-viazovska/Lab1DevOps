"""Database migration script.

Idempotent — safe to run against either an empty database or a database that
was previously migrated by an earlier (or current) version of this script.

The script connects to PostgreSQL using the same configuration as the
application (see ``app/database.py``) and creates the ``tasks`` table together
with the supporting index on ``created_at``.
"""

import sys

from sqlalchemy import text

from app.database import Base, engine
from app import models  # noqa: F401 — register models with Base.metadata


def run_migrations() -> None:
    Base.metadata.create_all(bind=engine)

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_tasks_created_at "
                "ON tasks (created_at)"
            )
        )

    print("Migration successful")


if __name__ == "__main__":
    try:
        run_migrations()
    except Exception as exc:  # pragma: no cover — surfaced to systemd
        print(f"Migration failed: {exc}", file=sys.stderr)
        sys.exit(1)
