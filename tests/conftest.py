"""Test-suite configuration.

Per ADR-0006, the app writes to ~/.impact-crater/ by default. To prevent
tests from polluting the developer's real home directory, every test
session points IMPACT_CRATER_HOME at an isolated temp directory.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


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


def pytest_configure(config: pytest.Config) -> None:
    """Ensure pytest-asyncio defaults are sane even when missing in pyproject."""
    os.environ.setdefault("PYTEST_ASYNCIO_MODE", "auto")
