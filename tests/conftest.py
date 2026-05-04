"""Test-suite configuration.

Per ADR-0006, the app writes to ~/.impact-crater/ by default. To prevent
tests from polluting the developer's real home directory, every test
session points IMPACT_CRATER_HOME at an isolated temp directory.

For M1+ integration tests that hit real Anthropic / Google APIs:
  - Loads `.env.test` if present (override=True; per user redirect 2026-05-04)
  - Falls back to system env vars (ANTHROPIC_API_KEY, GOOGLE_API_KEY)
  - Skips integration-marked tests unless `--integration` is passed
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="run integration tests against real Anthropic / Google APIs",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Load `.env.test` if present so integration tests pick up local keys.

    Path resolution: walk up from this file to the repo root, look for
    `.env.test`. Existing system env vars are overridden so the user can
    intentionally use a different key set in tests vs interactive use.
    """
    repo_root = Path(__file__).resolve().parent.parent
    env_test = repo_root / ".env.test"
    if env_test.is_file():
        try:
            from dotenv import load_dotenv  # type: ignore[import-not-found]

            load_dotenv(env_test, override=True)
        except ImportError:
            # python-dotenv is in dev deps; absence here implies the user
            # ran tests outside the [dev] extras. Fall back to system env.
            pass

    os.environ.setdefault("PYTEST_ASYNCIO_MODE", "auto")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--integration"):
        return  # run everything
    skip_integration = pytest.mark.skip(reason="needs --integration to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Redirect IMPACT_CRATER_HOME to a per-test temp dir for the test's lifetime."""
    home = tmp_path / "impact-crater"
    home.mkdir()
    monkeypatch.setenv("IMPACT_CRATER_HOME", str(home))
    yield home


@pytest.fixture
def project_root() -> Path:
    """Absolute path to the repo root, regardless of where pytest was invoked from."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def has_anthropic_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


@pytest.fixture
def has_google_key() -> bool:
    return bool(os.environ.get("GOOGLE_API_KEY"))
