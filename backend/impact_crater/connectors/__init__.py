"""Connector layer per ADR-0013.

A `Connector` is a publishing target (YouTube at MVP; Instagram /
Facebook / X at v1). The protocol abstracts:

    validate_artifact(plan, render_path) → ConnectorValidationResult
    upload(render_path, metadata, on_progress) → ConnectorUploadResult
    refresh_credentials() → None
"""

from impact_crater.connectors.base import (
    Connector,
    ConnectorAuthError,
    ConnectorError,
    ConnectorRateLimitError,
    ConnectorUploadResult,
    ConnectorValidationError,
    ConnectorValidationResult,
    PublishMetadata,
    Visibility,
)

__all__ = [
    "Connector",
    "ConnectorAuthError",
    "ConnectorError",
    "ConnectorRateLimitError",
    "ConnectorUploadResult",
    "ConnectorValidationError",
    "ConnectorValidationResult",
    "PublishMetadata",
    "Visibility",
]
