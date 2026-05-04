"""Migration runner — stub for S-2.1.2; full impl in S-2.1.3.

Exposed at the module level so `app.py`'s lifespan can import it; the
real implementation reads `migrations_sql/*.sql` and applies them in
order against `~/.impact-crater/db/impact-crater.sqlite`.
"""

from __future__ import annotations


async def run_pending_migrations() -> None:
    """No-op stub. Real implementation lands in S-2.1.3."""
    return None
