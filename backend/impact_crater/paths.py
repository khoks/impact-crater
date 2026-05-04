"""Filesystem path resolution per ADR-0006.

Every path the app reads from or writes to outside of the source tree
goes through this module. The root is `~/.impact-crater/` by default,
overridable via the `IMPACT_CRATER_HOME` environment variable.

Subdirectories are created on demand by the public helpers (idempotent).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def home() -> Path:
    """Return the application root directory.

    Resolution order:
      1. `IMPACT_CRATER_HOME` env var, if set
      2. `~/.impact-crater/` (cross-platform via Path.home())

    The directory is created if it does not exist.
    """
    override = os.environ.get("IMPACT_CRATER_HOME")
    root = Path(override).expanduser() if override else Path.home() / ".impact-crater"
    root.mkdir(parents=True, exist_ok=True)
    return root


def db_dir() -> Path:
    p = home() / "db"
    p.mkdir(parents=True, exist_ok=True)
    return p


def db_path() -> Path:
    return db_dir() / "impact-crater.sqlite"


def fernet_key_path() -> Path:
    return db_dir() / ".fernet-key"


def projects_dir() -> Path:
    p = home() / "projects"
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir() -> Path:
    p = home() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def telemetry_path() -> Path:
    """Per ADR-0015 — append-only JSONL stream."""
    return home() / "telemetry.jsonl"


def audit_path() -> Path:
    """Per ADR-0006 / ADR-0013 — append-only JSONL publish log."""
    return home() / "audit.jsonl"


def profile_dir() -> Path:
    """Per ADR-0014 / N-010 — cross-project user profile + feedback log."""
    p = home() / "profile"
    p.mkdir(parents=True, exist_ok=True)
    return p


def harden_secret_file(path: Path) -> None:
    """Set restrictive permissions on a secret file.

    On POSIX: chmod 0600. On Windows: best-effort via Path.chmod (limited
    semantics) — a fuller ACL approach is left for a v1 hardening pass.
    """
    if not path.exists():
        return
    if sys.platform == "win32":
        # Windows file-permission semantics through chmod are coarse; the
        # file is already in the user's home, which inherits user-only ACL
        # in default installs. A v1 hardening pass via win32security is
        # tracked elsewhere.
        return
    path.chmod(0o600)
