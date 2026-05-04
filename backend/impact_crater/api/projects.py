"""Projects API — placeholder.

The project CRUD surface lands in M3 (E-2.4 UI MVP loop closed). M0
exposes only an empty list endpoint so the React Dashboard has
something to call without 404-ing.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_projects() -> list[dict[str, str]]:
    """Empty at M0; project rows arrive in M3."""
    return []
