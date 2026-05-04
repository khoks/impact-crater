"""Typed read/write of the SQLite `settings` key/value table.

Per ADR-0006 + ADR-0013, sensitive values (API keys, OAuth tokens at
the `connector_credentials` layer) are Fernet-encrypted at rest. The
`encrypted` column on the row records whether the value was stored
through the encrypted path so reads decrypt correctly.
"""

from __future__ import annotations

from impact_crater import crypto
from impact_crater.storage.db import connection

# Reserved keys used by M0 + M1+ — listed here so typos surface as type
# errors / IDE warnings during development. Adding a new key elsewhere
# in the codebase is allowed (the table is generic K/V); this is a
# convenience registry, not an enforced enum.
KEY_SETUP_COMPLETE = "setup_complete"               # "true" | "false"
KEY_ANTHROPIC_API_KEY = "anthropic_api_key"          # encrypted
KEY_GOOGLE_API_KEY = "google_api_key"                # encrypted
KEY_TOTAL_CAP_USD = "spend_cap_total_usd"            # plain numeric string
KEY_ANTHROPIC_CAP_USD = "spend_cap_anthropic_usd"    # plain numeric string (or "")
KEY_GOOGLE_CAP_USD = "spend_cap_google_usd"          # plain numeric string (or "")


async def set_value(key: str, value: str, *, encrypted: bool = False) -> None:
    """Upsert a setting. Encrypts the value at rest if `encrypted=True`."""
    stored = crypto.encrypt(value) if encrypted else value
    async with connection() as db:
        await db.execute(
            "INSERT INTO settings (key, value, encrypted, updated_at) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET "
            "  value = excluded.value, "
            "  encrypted = excluded.encrypted, "
            "  updated_at = CURRENT_TIMESTAMP",
            (key, stored, 1 if encrypted else 0),
        )
        await db.commit()


async def get_value(key: str, *, default: str | None = None) -> str | None:
    """Return the decrypted setting value, or `default` if the key is unset."""
    async with connection() as db:
        cursor = await db.execute(
            "SELECT value, encrypted FROM settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
    if row is None:
        return default
    raw = row["value"]
    return crypto.decrypt(raw) if row["encrypted"] else raw


async def is_setup_complete() -> bool:
    return (await get_value(KEY_SETUP_COMPLETE, default="false")) == "true"


async def mark_setup_complete() -> None:
    await set_value(KEY_SETUP_COMPLETE, "true")
