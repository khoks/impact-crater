"""First-time-setup wizard API.

Skeleton in S-2.1.2 (only `/status` works); full implementation in S-2.1.5
adds `/test-key` + `/complete` etc.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def status() -> dict[str, bool]:
    """Whether the first-time-setup wizard has been completed.

    Stub at S-2.1.2 — always returns False so the React shell routes
    to /setup. S-2.1.5 reads the real value from the SQLite settings
    table.
    """
    return {"setup_complete": False}
