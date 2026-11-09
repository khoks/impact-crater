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


class JobHalted(LLMError):
    """A failure no later call in the same job can avoid: the daily spend cap is
    reached, or a provider has no credit left (S-3.11.1). The router refuses every
    later call once one is raised, and per-asset fail-soft loops re-raise it, so a
    job stops instead of failing the same way once per remaining asset."""


_RESUME_HINT = " The work done so far is cached, so a re-run resumes cheaply from where it stopped."


class QuotaExceededMidJob(JobHalted):
    """The pre-flight before a paid call found it would cross a daily cap."""

    def __init__(
        self,
        *,
        reason: str,
        provider: str,
        spent_usd: float,
        cap_usd: float | None,
        estimate_usd: float,
    ) -> None:
        self.reason = reason
        self.provider = provider
        self.spent_usd = spent_usd
        self.cap_usd = cap_usd
        self.estimate_usd = estimate_usd
        if cap_usd is None:
            message = "No daily spend cap is set. Set one in Settings, then re-run."
        else:
            which = "total" if reason.startswith("total") else f"{provider}-only"
            message = (
                f"Stopped at your daily spend cap: ${spent_usd:.2f} of your ${cap_usd:.2f} "
                f"{which} cap is spent today (UTC), and the next {provider} call (about "
                f"${estimate_usd:.4f}) would cross it. Raise the cap in Settings or re-run "
                "after midnight UTC." + _RESUME_HINT
            )
        super().__init__(message)


class ProviderCreditExhausted(JobHalted):
    """A provider refused a call because the account has no credit left."""

    def __init__(self, *, provider: str, detail: str) -> None:
        self.provider = provider
        self.detail = detail
        super().__init__(
            f"{provider.capitalize()} API credits exhausted: the provider refused the call "
            "because the account's credit balance is too low. Add credits in the provider's "
            "billing console, then re-run." + _RESUME_HINT
        )
