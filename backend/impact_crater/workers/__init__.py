"""Worker-pool subpackage per ADR-0010 §"Subprocess worker pool"."""

from impact_crater.workers.pool import (
    JobCancelled,
    WorkerClass,
    WorkerPool,
    default_pool,
)

__all__ = ["JobCancelled", "WorkerClass", "WorkerPool", "default_pool"]
