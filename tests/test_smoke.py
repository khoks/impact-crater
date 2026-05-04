"""Smoke test — confirms the package imports and the test infra is wired.

Per-feature tests grow with each milestone; this file's job is to fail
loudly if the basics break.
"""

from __future__ import annotations

import os
from pathlib import Path

import impact_crater


def test_package_version_exposed() -> None:
    assert isinstance(impact_crater.__version__, str)
    assert impact_crater.__version__.count(".") == 2


def test_isolated_home_active(isolated_home: Path) -> None:
    """Confirms the conftest fixture took effect."""
    assert os.environ["IMPACT_CRATER_HOME"] == str(isolated_home)
    assert isolated_home.exists()
    assert isolated_home.is_dir()


def test_cli_module_importable() -> None:
    """The console-script entry point must resolve."""
    from impact_crater import cli

    assert callable(cli.main)
