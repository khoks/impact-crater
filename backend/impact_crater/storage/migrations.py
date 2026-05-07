"""Hand-written SQL migration runner.

Per ADR-0006 the project doesn't use SQLAlchemy, so Alembic is overkill.
This runner reads `migrations_sql/{NNN}_{name}.sql` files in order and
applies any whose `version` integer is not yet recorded in the
`schema_migrations` table.

Idempotent. Safe to re-run on every process startup (the FastAPI
lifespan calls `run_pending_migrations()`).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import aiosqlite

from impact_crater.storage.db import connection

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations_sql"
_VERSION_RE = re.compile(r"^(\d+)_.+\.sql$")


async def run_pending_migrations() -> None:
    """Apply any migration files not yet recorded in `schema_migrations`."""
    files = _discover_migrations()

    async with connection() as db:
        await _ensure_migrations_table(db)
        applied = await _applied_versions(db)
        pending = [(v, p) for v, p in files if v not in applied]
        if pending:
            log.info(
                "migrations_pending count=%d versions=%s",
                len(pending),
                [v for v, _ in pending],
            )
        for version, path in pending:
            log.info("migration_applying version=%d filename=%s", version, path.name)
            try:
                sql = path.read_text(encoding="utf-8")
                await db.executescript(sql)
                await db.execute(
                    "INSERT INTO schema_migrations (version, filename, applied_at) "
                    "VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (version, path.name),
                )
                await db.commit()
            except Exception as exc:
                log.error(
                    "migration_failed version=%d filename=%s error=%r",
                    version,
                    path.name,
                    str(exc)[:300],
                )
                raise
            log.info("migration_applied version=%d filename=%s", version, path.name)


def _discover_migrations() -> list[tuple[int, Path]]:
    if not MIGRATIONS_DIR.is_dir():
        return []
    out: list[tuple[int, Path]] = []
    for entry in sorted(MIGRATIONS_DIR.iterdir()):
        m = _VERSION_RE.match(entry.name)
        if not m:
            continue
        out.append((int(m.group(1)), entry))
    return out


async def _ensure_migrations_table(db: aiosqlite.Connection) -> None:
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    INTEGER PRIMARY KEY,
            filename   TEXT NOT NULL,
            applied_at TEXT NOT NULL
        );
        """
    )
    await db.commit()


async def _applied_versions(db: aiosqlite.Connection) -> set[int]:
    cursor = await db.execute("SELECT version FROM schema_migrations")
    rows = await cursor.fetchall()
    return {int(row["version"]) for row in rows}
