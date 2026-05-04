"""LLM error hierarchy.

`LLMTransientError` is what `tenacity` retries; `LLMOperationFailed`
is the permanent-failure sentinel that propagates to the orchestrator
and the cost-transparency UI.
"""

from __future__ import annotations


class LLMError(Exception):
    """Base class for all LLM-stack errors."""


class LLMTransientError(LLMError):
    """A retryable failure (HTTP 429, 5xx, network reset)."""


class LLMOperationFailed(LLMError):
    """Permanent failure for a specific operation/provider/model triple.

    Wraps the underlying SDK exception so callers can decide how to
    surface the failure to the user (via the cost-transparency UI).
    """

    def __init__(
        self,
        *,
        operation: str,
        provider: str,
        model: str,
        attempts: int,
        last_error: Exception | str,
        cost_consumed_usd: float = 0.0,
    ) -> None:
        self.operation = operation
        self.provider = provider
        self.model = model
        self.attempts = attempts
        self.last_error = last_error
        self.cost_consumed_usd = cost_consumed_usd
        super().__init__(
            f"{operation}@{provider}/{model} failed after {attempts} attempt(s): {last_error}"
        )
