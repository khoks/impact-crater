"""Job registry + progress event bus for the M3 UI per S-2.4.1.

The synchronous `POST /api/jobs/render` (M2) blocks until done — fine
for tests, useless for a UI. M3 adds async submission with a WS event
stream. This subpackage owns the in-process state.
"""

from impact_crater.jobs.registry import (
    JobProgressEvent,
    JobRegistry,
    JobSnapshot,
    JobState,
    get_registry,
)

__all__ = [
    "JobProgressEvent",
    "JobRegistry",
    "JobSnapshot",
    "JobState",
    "get_registry",
]
