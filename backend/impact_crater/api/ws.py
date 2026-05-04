"""WebSocket router — placeholder.

Per ADR-0005, the job-progress WebSocket lands in M3 and streams
`OrchestratorTurnEvent` / `LLMCallEvent` / `RenderEvent` / etc. to
the in-progress UI. M0 ships an empty router so the include_router
call in app.py doesn't crash.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()
