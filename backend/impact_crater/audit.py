"""Append-only publish audit log per ADR-0006 + ADR-0013.

Two stores in lockstep:

  ~/.impact-crater/audit.jsonl  — append-only JSONL (authoritative)
  audit (SQLite table)          — mirror for fast queries

The JSONL file is the source-of-truth — append-only-file semantics
survive crashes better than a database row that may be in a partial
transaction state.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from impact_crater import paths
from impact_crater.storage.db import connection

_LOCK = threading.Lock()


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AuditEntry:
    project_id: str
    snapshot_id: str
    platform: str  # "youtube" / "instagram" / etc.
    external_id: str
    external_url: str
    user_approval_token: str
    render_content_hash: str = ""
    response_code: int = 200
    response_summary: str = ""
    description_full: str = ""
    visibility: str = "public"
    schema_version: int = 1
    timestamp: str = field(default_factory=_iso_now)


async def write(entry: AuditEntry) -> None:
    """Append to JSONL + INSERT into the audit SQLite table."""
    line = json.dumps(asdict(entry), separators=(",", ":"))
    target = paths.audit_path()
    with _LOCK:
        with target.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    async with connection() as db:
        await db.execute(
            """
            INSERT INTO audit
                (schema_version, project_id, snapshot_id, platform,
                 external_id, external_url, response_code, response_summary,
                 render_content_hash, user_approval_token, publish_metadata,
                 description_full, published_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.schema_version,
                entry.project_id,
                entry.snapshot_id,
                entry.platform,
                entry.external_id,
                entry.external_url,
                entry.response_code,
                entry.response_summary,
                entry.render_content_hash,
                entry.user_approval_token,
                json.dumps({"visibility": entry.visibility}),
                entry.description_full,
                entry.timestamp,
            ),
        )
        await db.commit()


async def list_for_project(project_id: str, limit: int = 50) -> list[dict]:
    async with connection() as db:
        cur = await db.execute(
            """
            SELECT id, schema_version, project_id, snapshot_id, platform,
                   external_id, external_url, response_code, response_summary,
                   render_content_hash, user_approval_token, publish_metadata,
                   description_full, published_at
            FROM audit
            WHERE project_id = ?
            ORDER BY published_at DESC
            LIMIT ?
            """,
            (project_id, limit),
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]
