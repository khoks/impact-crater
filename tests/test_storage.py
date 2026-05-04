"""Tests for the storage layer (paths, db, migrations, settings)."""

from __future__ import annotations

from pathlib import Path

from impact_crater import paths
from impact_crater.storage import migrations, settings
from impact_crater.storage.db import connection


def test_home_resolves_to_isolated_dir(isolated_home: Path) -> None:
    assert paths.home() == isolated_home


def test_subdirs_created_lazily(isolated_home: Path) -> None:
    db = paths.db_dir()
    proj = paths.projects_dir()
    cache = paths.cache_dir()
    profile = paths.profile_dir()
    assert db.is_dir()
    assert proj.is_dir()
    assert cache.is_dir()
    assert profile.is_dir()


async def test_migrations_apply_001_init_to_fresh_db() -> None:
    await migrations.run_pending_migrations()
    async with connection() as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
        rows = await cursor.fetchall()
    table_names = {row["name"] for row in rows}
    assert "schema_migrations" in table_names
    assert "settings" in table_names
    assert "projects" in table_names
    assert "media" in table_names
    assert "project_media" in table_names
    assert "snapshots" in table_names
    assert "audit" in table_names
    assert "cache_index" in table_names
    assert "connector_credentials" in table_names
    assert "quota_state" in table_names
    assert "persons" in table_names
    assert "person_face_photos" in table_names


async def test_migrations_are_idempotent() -> None:
    await migrations.run_pending_migrations()
    await migrations.run_pending_migrations()  # second call is a no-op
    async with connection() as db:
        cursor = await db.execute("SELECT version FROM schema_migrations")
        rows = await cursor.fetchall()
    versions = [row["version"] for row in rows]
    assert versions == sorted(versions)
    # Every version recorded once.
    assert len(versions) == len(set(versions))


async def test_settings_round_trip_plain() -> None:
    await migrations.run_pending_migrations()
    await settings.set_value("foo", "bar")
    assert await settings.get_value("foo") == "bar"
    assert await settings.get_value("missing", default="fallback") == "fallback"


async def test_settings_round_trip_encrypted() -> None:
    await migrations.run_pending_migrations()
    await settings.set_value(settings.KEY_ANTHROPIC_API_KEY, "sk-ant-secret-xyz", encrypted=True)
    decrypted = await settings.get_value(settings.KEY_ANTHROPIC_API_KEY)
    assert decrypted == "sk-ant-secret-xyz"

    # The on-disk value is NOT plaintext.
    async with connection() as db:
        cursor = await db.execute(
            "SELECT value, encrypted FROM settings WHERE key = ?",
            (settings.KEY_ANTHROPIC_API_KEY,),
        )
        row = await cursor.fetchone()
    assert row is not None
    assert row["encrypted"] == 1
    assert row["value"] != "sk-ant-secret-xyz"


async def test_setup_complete_flag() -> None:
    await migrations.run_pending_migrations()
    assert await settings.is_setup_complete() is False
    await settings.mark_setup_complete()
    assert await settings.is_setup_complete() is True
