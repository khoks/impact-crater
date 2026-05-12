"""Connector layer per ADR-0013 + v1 multi-platform extension.

A `Connector` is a publishing target. MVP shipped YouTube; v1 adds
Instagram + Facebook (and X / LinkedIn / TikTok as follow-ups). The
protocol is platform-agnostic:

    validate_artifact(render_path, metadata) → ConnectorValidationResult
    upload(render_path, metadata, on_progress) → ConnectorUploadResult
    refresh_credentials() → None
    is_connected() → bool
    disconnect() → None

Use `get_connector("youtube"|"instagram"|"facebook")` to look one up by
platform name. The factory respects `IC_PUBLISH_DRY_RUN` (default on)
and returns a `DryRunConnector` wrapper when set, so real posting only
happens when the user explicitly flips it off.

Per-platform creds live in env vars (v1 model):
- YouTube:   IC_YOUTUBE_CLIENT_ID + IC_YOUTUBE_CLIENT_SECRET + IC_YOUTUBE_REFRESH_TOKEN
- Instagram: IC_INSTAGRAM_ACCESS_TOKEN + IC_INSTAGRAM_USER_ID (+ IC_PUBLIC_BASE_URL for real posts)
- Facebook:  IC_FACEBOOK_PAGE_ACCESS_TOKEN + IC_FACEBOOK_PAGE_ID

See docs/connectors/*-setup.md for the per-platform credential setup.
"""

from impact_crater.connectors.base import (
    LIVE_PUBLISH_PLATFORMS,
    Connector,
    ConnectorAuthError,
    ConnectorError,
    ConnectorRateLimitError,
    ConnectorUploadResult,
    ConnectorValidationError,
    ConnectorValidationResult,
    Platform,
    PublishMetadata,
    Visibility,
)
from impact_crater.connectors.dry_run import DryRunConnector, is_dry_run_enabled, wrap_if_dry_run
from impact_crater.connectors.facebook import FacebookConnector
from impact_crater.connectors.instagram import InstagramConnector
from impact_crater.connectors.youtube import YouTubeConnector

__all__ = [
    "Connector",
    "ConnectorAuthError",
    "ConnectorError",
    "ConnectorRateLimitError",
    "ConnectorUploadResult",
    "ConnectorValidationError",
    "ConnectorValidationResult",
    "DryRunConnector",
    "FacebookConnector",
    "InstagramConnector",
    "LIVE_PUBLISH_PLATFORMS",
    "Platform",
    "PublishMetadata",
    "Visibility",
    "YouTubeConnector",
    "get_connector",
    "is_dry_run_enabled",
    "wrap_if_dry_run",
]


def get_connector(platform: str) -> Connector:
    """Return a fresh connector for `platform`, dry-run-wrapped if needed.

    Raises `ValueError` for unknown platform names so the publish API
    returns a 400 rather than a 500.
    """
    base: Connector
    if platform == "youtube":
        base = YouTubeConnector()  # type: ignore[assignment]
    elif platform == "instagram":
        base = InstagramConnector()  # type: ignore[assignment]
    elif platform == "facebook":
        base = FacebookConnector()  # type: ignore[assignment]
    else:
        raise ValueError(
            f"unknown publish platform {platform!r}; "
            f"supported: {LIVE_PUBLISH_PLATFORMS}"
        )
    return wrap_if_dry_run(base)
