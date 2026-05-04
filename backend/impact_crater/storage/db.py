"""aiosqlite connection helpers.

A single SQLite file at `~/.impact-crater/db/impact-crater.sqlite`
(per ADR-0006). All queries go through `connection()` so PRAGMAs are
applied consistently.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite

from impact_crater import paths


@asynccontextmanager
async def connection() -> AsyncIterator[aiosqlite.Connection]:
    """Open a connection with the project's standard PRAGMAs applied."""
    db = await aiosqlite.connect(paths.db_path())
    try:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        await db.execute("PRAGMA synchronous = NORMAL")
        db.row_factory = aiosqlite.Row
        yield db
    finally:
        await db.close()
