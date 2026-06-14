"""User feedback capture for the in-app feedback loop (A-023).

Stores structured feedback on pipeline decisions in the `feedback` table
AND mirrors each item to an append-only `~/.impact-crater/feedback.jsonl`
so a later Claude session can pick it up out-of-band (read the JSONL or
query the table) and act on the improvements.
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from impact_crater import paths
from impact_crater.storage.db import connection

log = logging.getLogger(__name__)

router = APIRouter()


class FeedbackRequest(BaseModel):
    phase: str = Field(min_length=1, max_length=64)
    verdict: Literal["correct", "incorrect", "different"]
    job_id: str | None = None
    project_id: str | None = None
    snapshot_id: str | None = None
    decision_ref: str | None = Field(default=None, max_length=200)
    content_hash: str | None = Field(default=None, max_length=64)
    comment: str | None = Field(default=None, max_length=4000)
    context: dict[str, Any] | None = None
    # A page screenshot captured at submit time (data URL: "data:image/png;base64,...").
    # Best-effort — saved to disk if present; never required.
    screenshot_data_url: str | None = Field(default=None, max_length=20_000_000)


class FeedbackResponse(BaseModel):
    id: int
    created_at: str
    status: str


class FeedbackItem(BaseModel):
    id: int
    created_at: str
    job_id: str | None
    project_id: str | None
    snapshot_id: str | None
    phase: str
    decision_ref: str | None
    content_hash: str | None
    verdict: str
    comment: str | None
    status: str


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def post_feedback(req: FeedbackRequest) -> FeedbackResponse:
    """Store one piece of feedback; mirror it to feedback.jsonl."""
    context_json = json.dumps(req.context) if req.context is not None else None
    async with connection() as db:
        cursor = await db.execute(
            """
            INSERT INTO feedback
                (job_id, project_id, snapshot_id, phase, decision_ref,
                 content_hash, verdict, comment, context_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                req.job_id,
                req.project_id,
                req.snapshot_id,
                req.phase,
                req.decision_ref,
                req.content_hash,
                req.verdict,
                req.comment,
                context_json,
            ),
        )
        await db.commit()
        new_id = cursor.lastrowid
        row = await (
            await db.execute(
                "SELECT created_at, status FROM feedback WHERE id = ?", (new_id,)
            )
        ).fetchone()

    created_at = row["created_at"] if row else ""

    # Save the page screenshot (best-effort) and record its path.
    screenshot_path = _save_screenshot(int(new_id or 0), req.screenshot_data_url)
    if screenshot_path:
        async with connection() as db:
            await db.execute(
                "UPDATE feedback SET screenshot_path = ? WHERE id = ?",
                (screenshot_path, new_id),
            )
            await db.commit()
    _append_jsonl(
        {
            "id": new_id,
            "created_at": created_at,
            "phase": req.phase,
            "verdict": req.verdict,
            "job_id": req.job_id,
            "project_id": req.project_id,
            "snapshot_id": req.snapshot_id,
            "decision_ref": req.decision_ref,
            "content_hash": req.content_hash,
            "comment": req.comment,
            "context": req.context,
            "screenshot_path": screenshot_path,
        }
    )
    log.info(
        "feedback_stored id=%s phase=%s verdict=%s snapshot=%s ref=%s",
        new_id,
        req.phase,
        req.verdict,
        req.snapshot_id,
        req.decision_ref,
    )
    return FeedbackResponse(id=int(new_id or 0), created_at=created_at, status="new")


@router.get("", response_model=list[FeedbackItem])
async def list_feedback(
    status_filter: str | None = None, snapshot_id: str | None = None
) -> list[FeedbackItem]:
    """List feedback, newest first. Filter by `status_filter` (e.g. 'new')
    or `snapshot_id`. This is what a Claude session reads to pick up work."""
    clauses: list[str] = []
    params: list[Any] = []
    if status_filter:
        clauses.append("status = ?")
        params.append(status_filter)
    if snapshot_id:
        clauses.append("snapshot_id = ?")
        params.append(snapshot_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    async with connection() as db:
        cursor = await db.execute(
            "SELECT id, created_at, job_id, project_id, snapshot_id, phase, "
            "decision_ref, content_hash, verdict, comment, status "
            f"FROM feedback{where} ORDER BY created_at DESC, id DESC",
            params,
        )
        rows = await cursor.fetchall()
    return [
        FeedbackItem(
            id=r["id"],
            created_at=r["created_at"],
            job_id=r["job_id"],
            project_id=r["project_id"],
            snapshot_id=r["snapshot_id"],
            phase=r["phase"],
            decision_ref=r["decision_ref"],
            content_hash=r["content_hash"],
            verdict=r["verdict"],
            comment=r["comment"],
            status=r["status"],
        )
        for r in rows
    ]


@router.get("/{feedback_id}/screenshot.png")
async def get_feedback_screenshot(feedback_id: int) -> FileResponse:
    """Serve the page screenshot captured with a feedback item, if any."""
    async with connection() as db:
        row = await (
            await db.execute(
                "SELECT screenshot_path FROM feedback WHERE id = ?", (feedback_id,)
            )
        ).fetchone()
    if row is None or not row["screenshot_path"]:
        raise HTTPException(status_code=404, detail="no screenshot for this feedback")
    p = Path(row["screenshot_path"])
    if not p.is_absolute():
        p = paths.home() / row["screenshot_path"]  # stored relative to the home dir
    if not p.is_file():
        raise HTTPException(status_code=404, detail="screenshot file missing")
    return FileResponse(p, media_type="image/png", content_disposition_type="inline")


def _save_screenshot(feedback_id: int, data_url: str | None) -> str | None:
    """Decode a base64 PNG data URL and save it; return the path relative to
    the home dir (so it's portable), or None. Best-effort."""
    if not data_url or feedback_id <= 0:
        return None
    try:
        if "," in data_url:
            _, b64 = data_url.split(",", 1)
        else:
            b64 = data_url
        raw = base64.b64decode(b64)
        if not raw:
            return None
        rel = f"feedback_screenshots/{feedback_id}.png"
        dest = paths.home() / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        return rel
    except Exception as exc:
        log.warning("feedback_screenshot_save_failed id=%s error=%r", feedback_id, str(exc)[:200])
        return None


def _append_jsonl(payload: dict[str, Any]) -> None:
    """Append one feedback record to ~/.impact-crater/feedback.jsonl."""
    try:
        path = paths.home() / "feedback.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as exc:
        log.warning("feedback_jsonl_append_failed error=%r", str(exc)[:200])
