"""Connector Protocol + error hierarchy per ADR-0013."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

Visibility = Literal["private", "unlisted", "public"]

# v1 multi-platform publish — D-007 (MVP=YouTube only) → I-3. Each
# platform implements the `Connector` Protocol and is dispatched via
# `connectors.get_connector(platform)`.
Platform = Literal["youtube", "instagram", "facebook"]
LIVE_PUBLISH_PLATFORMS: tuple[Platform, ...] = ("youtube", "instagram", "facebook")


@dataclass
class PublishMetadata:
    """Per-platform-agnostic publish metadata. Connectors map fields onto
    their platform's schema."""

    title: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    visibility: Visibility = "public"  # ADR-0013 default per D-032
    category: str | None = None  # platform-specific (e.g. YouTube category id)


@dataclass
class ConnectorValidationResult:
    valid: bool
    issues: list[str] = field(default_factory=list)
    suggested_actions: list[str] = field(default_factory=list)


@dataclass
class ConnectorUploadResult:
    external_id: str
    external_url: str
    visibility: Visibility
    response_code: int
    response_summary: str = ""


# ---- Errors -----------------------------------------------------------


class ConnectorError(Exception):
    """Base for all connector errors. Carries a structured payload."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        suggested_action: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.suggested_action = suggested_action


class ConnectorAuthError(ConnectorError):
    """OAuth token expired / revoked / never granted."""


class ConnectorValidationError(ConnectorError):
    """Local validation rejected the artifact (title too long, file missing, etc)."""


class ConnectorRateLimitError(ConnectorError):
    """Platform returned a 429 / quota-exhausted response."""


# ---- Protocol ---------------------------------------------------------


ProgressCallback = Callable[[float], Awaitable[None]]
"""Called with [0.0, 1.0] upload progress."""


@runtime_checkable
class Connector(Protocol):
    """Publishing target abstraction."""

    name: str  # "youtube" / "instagram" / etc.

    async def validate_artifact(
        self, render_path: Path, metadata: PublishMetadata
    ) -> ConnectorValidationResult: ...

    async def upload(
        self,
        render_path: Path,
        metadata: PublishMetadata,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> ConnectorUploadResult: ...

    async def refresh_credentials(self) -> None: ...

    async def is_connected(self) -> bool: ...

    async def disconnect(self) -> None: ...
