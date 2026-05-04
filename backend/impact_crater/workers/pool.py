"""Asyncio worker pool with per-class concurrency limits per ADR-0010.

Three worker classes by resource profile:

  - `cpu`     — perceptual hash, smart-crop, scene-detect (default: cpu_count())
  - `ffmpeg`  — ffmpeg subprocess decode/encode (default: 2; serialized hot path)
  - `network` — LLM calls and any other I/O-bound network work (default: 8)

Each class has an independent `asyncio.Semaphore` cap. Submissions block on
the cap so we never start more concurrent work than the class allows.

`JobCancelled` propagates through `await pool.submit(...)`. If a job is
cancelled mid-flight, every in-flight task in the pool is asyncio-cancelled;
ffmpeg subprocess wrappers hook into this via `asyncio.subprocess`'s built-in
cancellation propagation (caller passes a process handle to `register_subprocess`).

Defaults are configurable via `IC_WORKER_CPU` / `IC_WORKER_FFMPEG` /
`IC_WORKER_NETWORK` env vars, which is what the M1 pipeline reads at boot.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Literal, TypeVar

WorkerClass = Literal["cpu", "ffmpeg", "network"]

T = TypeVar("T")


class JobCancelled(Exception):
    """Raised inside any worker callable when the job is cancelled."""


def _default_cpu_workers() -> int:
    return max(1, os.cpu_count() or 4)


def _read_int(env: str, default: int) -> int:
    raw = os.environ.get(env)
    if not raw:
        return default
    try:
        v = int(raw)
        return v if v >= 1 else default
    except ValueError:
        return default


class WorkerPool:
    """Run async callables under per-class concurrency limits.

    Construct one pool per job (or one global pool reused across jobs — the
    semaphore is per-pool, not per-job). Jobs that need cancellation should
    keep a reference and call `cancel()`.
    """

    def __init__(
        self,
        *,
        cpu_workers: int | None = None,
        ffmpeg_workers: int | None = None,
        network_workers: int | None = None,
    ) -> None:
        self._limits = {
            "cpu": cpu_workers or _read_int("IC_WORKER_CPU", _default_cpu_workers()),
            "ffmpeg": ffmpeg_workers or _read_int("IC_WORKER_FFMPEG", 2),
            "network": network_workers or _read_int("IC_WORKER_NETWORK", 8),
        }
        self._semaphores = {
            cls: asyncio.Semaphore(limit) for cls, limit in self._limits.items()
        }
        self._tasks: set[asyncio.Task[Any]] = set()
        self._cancelled = False
        self._subprocesses: set[asyncio.subprocess.Process] = set()

    @property
    def limits(self) -> dict[str, int]:
        return dict(self._limits)

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    async def submit(
        self,
        worker_class: WorkerClass,
        coro_factory: Callable[[], Awaitable[T]],
    ) -> T:
        """Run `coro_factory()` under the given class's concurrency cap.

        `coro_factory` is a zero-arg callable returning a coroutine — passing
        a coroutine directly would mean it can't be retried on cancellation.
        We don't retry today, but the factory shape leaves the door open.
        """
        if self._cancelled:
            raise JobCancelled("pool cancelled")
        if worker_class not in self._semaphores:
            raise KeyError(f"unknown worker class {worker_class!r}")
        sem = self._semaphores[worker_class]

        async def _run() -> T:
            async with sem:
                if self._cancelled:
                    raise JobCancelled("pool cancelled before task start")
                return await coro_factory()

        task = asyncio.create_task(_run())
        self._tasks.add(task)
        try:
            return await task
        except asyncio.CancelledError as e:
            raise JobCancelled("task cancelled") from e
        finally:
            self._tasks.discard(task)

    async def submit_many(
        self,
        worker_class: WorkerClass,
        items: Iterable[Any],
        coro_factory: Callable[[Any], Awaitable[T]],
    ) -> list[T]:
        """Submit one task per `item` and await all results in order.

        Concurrency is bounded by the class's semaphore, not by the number
        of items, so callers can pass thousands of items safely.
        """
        async def _one(item: Any) -> T:
            return await self.submit(worker_class, lambda: coro_factory(item))

        return await asyncio.gather(*[_one(item) for item in items])

    def register_subprocess(self, proc: asyncio.subprocess.Process) -> None:
        """Track a subprocess so `cancel()` can SIGTERM it."""
        self._subprocesses.add(proc)

    def unregister_subprocess(self, proc: asyncio.subprocess.Process) -> None:
        self._subprocesses.discard(proc)

    async def cancel(self, *, grace_period_s: float = 2.0) -> None:
        """Cancel every in-flight task + signal any tracked subprocesses.

        SIGTERM on POSIX; on Windows, asyncio sends terminate which maps to
        TerminateProcess. After `grace_period_s` we kill any survivors.
        """
        self._cancelled = True
        for task in list(self._tasks):
            task.cancel()
        for proc in list(self._subprocesses):
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
        if self._subprocesses:
            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        *(p.wait() for p in self._subprocesses),
                        return_exceptions=True,
                    ),
                    timeout=grace_period_s,
                )
            except asyncio.TimeoutError:
                for proc in list(self._subprocesses):
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass

    def in_flight(self, worker_class: WorkerClass | None = None) -> int:
        """Approximate in-flight count, optionally per class.

        Best-effort; reads the semaphore's internal `_value` (private but
        stable across CPython versions). Used by the UI websocket to surface
        backpressure per ADR-0010 §"Backpressure".
        """
        if worker_class is None:
            return len(self._tasks)
        if worker_class not in self._semaphores:
            return 0
        sem = self._semaphores[worker_class]
        # Semaphore._value is the remaining capacity; in-flight = limit - remaining.
        remaining = getattr(sem, "_value", self._limits[worker_class])
        return max(0, self._limits[worker_class] - remaining)


_GLOBAL_POOL: WorkerPool | None = None


def default_pool() -> WorkerPool:
    """Return a process-wide singleton pool for callers that don't manage one."""
    global _GLOBAL_POOL
    if _GLOBAL_POOL is None:
        _GLOBAL_POOL = WorkerPool()
    return _GLOBAL_POOL
