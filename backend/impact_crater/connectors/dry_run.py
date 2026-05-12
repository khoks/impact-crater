"""Dry-run wrapper for any `Connector`.

`IC_PUBLISH_DRY_RUN=1` (default) causes the publish API to wrap each
real connector with `DryRunConnector` before calling `upload()`. The
wrapper runs the full `validate_artifact()` preflight (size, MIME,
title length, scopes) so config errors still surface — but on a valid
artifact it returns a synthetic `ConnectorUploadResult` instead of
hitting the platform.

The user flips `IC_PUBLISH_DRY_RUN=0` once they're ready to actually
post. Per the v1 plan we default to dry-run so accidental real posts
don't happen during integration testing.
"""

from __future__ import annotations

import logging
import secrets
from pathlib import Path
from typing import Any

from impact_crater.connectors.base import (
    Connector,
    ConnectorUploadResult,
    ConnectorValidationError,
    ConnectorValidationResult,
    ProgressCallback,
    PublishMetadata,
)

log = logging.getLogger(__name__)


class DryRunConnector:
    """Adapts any `Connector` to a no-op upload that still validates.

    Carries the wrapped connector's `name` so the audit log + UI show
    `youtube (dry-run)` rather than `dry_run`.
    """

    def __init__(self, wrapped: Connector) -> None:
        self._wrapped = wrapped
        self.name = f"{wrapped.name}"

    async def validate_artifact(
        self, render_path: Path, metadata: PublishMetadata
    ) -> ConnectorValidationResult:
        # Delegate validation unchanged — that's the whole point of dry-run.
        return await self._wrapped.validate_artifact(render_path, metadata)

    async def upload(
        self,
        render_path: Path,
        metadata: PublishMetadata,
        *,
        on_progress: ProgressCallback | None = None,
    ) -> ConnectorUploadResult:
        validation = await self.validate_artifact(render_path, metadata)
        if not validation.valid:
            raise ConnectorValidationError(
                "; ".join(validation.issues),
                status_code=400,
                suggested_action="; ".join(validation.suggested_actions),
            )

        # Fake an upload-progress sequence so any UI progress meter still ticks.
        if on_progress is not None:
            for f in (0.0, 0.5, 1.0):
                try:
                    await on_progress(f)
                except Exception:  # pragma: no cover
                    pass

        fake_id = f"dry-run-{secrets.token_urlsafe(12)}"
        log.info(
            "publish_dry_run platform=%s render_path=%s title=%r visibility=%s "
            "fake_external_id=%s",
            self._wrapped.name,
            str(render_path),
            metadata.title[:80],
            metadata.visibility,
            fake_id,
        )
        return ConnectorUploadResult(
            external_id=fake_id,
            external_url=f"https://dry-run.local/{self._wrapped.name}/{fake_id}",
            visibility=metadata.visibility,
            response_code=200,
            response_summary=f"DRY-RUN — validated {self._wrapped.name} request without posting",
        )

    async def refresh_credentials(self) -> None:
        await self._wrapped.refresh_credentials()

    async def is_connected(self) -> bool:
        return await self._wrapped.is_connected()

    async def disconnect(self) -> None:  # pragma: no cover — symmetric
        await self._wrapped.disconnect()


def is_dry_run_enabled() -> bool:
    """Read the env flag. Default: True (safe-by-default per v1 plan).

    User explicitly sets `IC_PUBLISH_DRY_RUN=0` to enable real posting.
    Anything else (unset, 1, true, yes) keeps dry-run on.
    """
    import os

    raw = os.environ.get("IC_PUBLISH_DRY_RUN", "1").strip().lower()
    return raw not in ("0", "false", "no", "off", "")


def wrap_if_dry_run(connector: Connector) -> Connector:
    """If dry-run is enabled, wrap the connector. Otherwise pass through."""
    if is_dry_run_enabled():
        return DryRunConnector(connector)  # type: ignore[return-value]
    return connector


# `Any` import kept for callers that need the protocol annotation.
_ = Any
