"""Tests for the asyncio worker pool — concurrency caps, cancellation, isolation."""

from __future__ import annotations

import asyncio

import pytest

from impact_crater.workers import JobCancelled, WorkerPool


async def test_pool_default_limits_are_sensible() -> None:
    pool = WorkerPool()
    limits = pool.limits
    assert limits["cpu"] >= 1
    assert limits["ffmpeg"] == 2
    assert limits["network"] == 8


async def test_pool_respects_per_class_concurrency_cap() -> None:
    """At most `cpu_workers=2` should ever be in flight on the cpu class."""
    pool = WorkerPool(cpu_workers=2, ffmpeg_workers=1, network_workers=1)
    in_flight_high_water = 0
    current_in_flight = 0
    lock = asyncio.Lock()

    async def task(_: int) -> int:
        nonlocal in_flight_high_water, current_in_flight
        async with lock:
            current_in_flight += 1
            if current_in_flight > in_flight_high_water:
                in_flight_high_water = current_in_flight
        try:
            await asyncio.sleep(0.05)
            return current_in_flight
        finally:
            async with lock:
                current_in_flight -= 1

    items = list(range(8))
    results = await pool.submit_many("cpu", items, task)
    assert len(results) == 8
    assert in_flight_high_water <= 2


async def test_pool_classes_are_independent() -> None:
    """Saturating cpu workers should not block ffmpeg or network submissions."""
    pool = WorkerPool(cpu_workers=1, ffmpeg_workers=1, network_workers=1)

    cpu_started = asyncio.Event()
    cpu_release = asyncio.Event()

    async def cpu_task() -> str:
        cpu_started.set()
        await cpu_release.wait()
        return "cpu-done"

    async def ffmpeg_task() -> str:
        return "ffmpeg-done"

    cpu_future = asyncio.create_task(pool.submit("cpu", cpu_task))
    await cpu_started.wait()
    # CPU class is now saturated; ffmpeg should still execute promptly.
    ffmpeg_result = await asyncio.wait_for(pool.submit("ffmpeg", ffmpeg_task), timeout=1.0)
    assert ffmpeg_result == "ffmpeg-done"
    cpu_release.set()
    cpu_result = await cpu_future
    assert cpu_result == "cpu-done"


async def test_submit_propagates_callable_exception() -> None:
    pool = WorkerPool()

    async def boom() -> None:
        raise ValueError("intended")

    with pytest.raises(ValueError, match="intended"):
        await pool.submit("cpu", boom)


async def test_pool_cancel_translates_to_jobcancelled() -> None:
    pool = WorkerPool(cpu_workers=2)
    started = asyncio.Event()

    async def long_task() -> None:
        started.set()
        await asyncio.sleep(5.0)

    fut = asyncio.create_task(pool.submit("cpu", long_task))
    await started.wait()
    await pool.cancel()
    with pytest.raises(JobCancelled):
        await fut


async def test_unknown_worker_class_raises() -> None:
    pool = WorkerPool()
    with pytest.raises(KeyError):
        await pool.submit("gpu", lambda: asyncio.sleep(0))  # type: ignore[arg-type]


async def test_in_flight_counter_tracks_active_tasks() -> None:
    pool = WorkerPool(network_workers=4)
    started = [asyncio.Event() for _ in range(3)]
    release = asyncio.Event()

    async def hold(i: int) -> None:
        started[i].set()
        await release.wait()

    tasks = [asyncio.create_task(pool.submit("network", lambda i=i: hold(i))) for i in range(3)]
    for ev in started:
        await ev.wait()
    assert pool.in_flight() == 3
    assert pool.in_flight("network") == 3
    assert pool.in_flight("cpu") == 0
    release.set()
    await asyncio.gather(*tasks)


async def test_env_var_overrides_default_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IC_WORKER_CPU", "1")
    monkeypatch.setenv("IC_WORKER_FFMPEG", "5")
    monkeypatch.setenv("IC_WORKER_NETWORK", "16")
    pool = WorkerPool()
    assert pool.limits == {"cpu": 1, "ffmpeg": 5, "network": 16}


async def test_submit_after_cancel_raises_immediately() -> None:
    pool = WorkerPool()
    await pool.cancel()
    with pytest.raises(JobCancelled):
        await pool.submit("cpu", lambda: asyncio.sleep(0))


# ---- submit_many_tolerant: per-asset failure isolation -------------------


async def test_submit_many_tolerant_returns_none_for_failures() -> None:
    """One failing task must NOT kill the batch — it yields None and the
    other items complete. Real failure motivating this: one bad image in
    a 545-asset Stage 2 batch killed the whole job."""
    pool = WorkerPool()

    async def maybe_fail(item: int) -> int:
        if item == 3:
            raise ValueError("boom on item 3")
        return item * 10

    results = await pool.submit_many_tolerant("cpu", [1, 2, 3, 4, 5], maybe_fail)
    assert results == [10, 20, None, 40, 50]


async def test_submit_many_tolerant_calls_on_error_with_index_item_exc() -> None:
    pool = WorkerPool()
    captured: list[tuple[int, int, str]] = []

    def on_error(idx: int, item: int, exc: BaseException) -> None:
        captured.append((idx, item, type(exc).__name__))

    async def fail_evens(item: int) -> int:
        if item % 2 == 0:
            raise RuntimeError(f"even {item}")
        return item

    await pool.submit_many_tolerant("cpu", [1, 2, 3, 4], fail_evens, on_error=on_error)
    # Indices for items [1, 2, 3, 4] are [0, 1, 2, 3]; failures at 1 and 3.
    assert captured == [(1, 2, "RuntimeError"), (3, 4, "RuntimeError")]


async def test_submit_many_tolerant_propagates_cancellation() -> None:
    """JobCancelled (pool shutdown) must NOT be swallowed even by tolerant."""
    pool = WorkerPool()
    await pool.cancel()
    with pytest.raises(JobCancelled):
        await pool.submit_many_tolerant("cpu", [1, 2, 3], lambda i: asyncio.sleep(0))


async def test_submit_many_tolerant_on_error_callback_failure_doesnt_break_batch() -> None:
    """If the on_error callback itself raises, we still produce results
    for the surviving tasks (the callback is best-effort logging)."""
    pool = WorkerPool()

    def bad_callback(*_: object) -> None:
        raise RuntimeError("logger blew up")

    async def fail_threes(item: int) -> int:
        if item == 3:
            raise ValueError("boom")
        return item

    results = await pool.submit_many_tolerant(
        "cpu", [1, 2, 3, 4], fail_threes, on_error=bad_callback
    )
    assert results == [1, 2, None, 4]


async def test_submit_many_tolerant_empty_list() -> None:
    pool = WorkerPool()
    results = await pool.submit_many_tolerant("cpu", [], lambda _: asyncio.sleep(0))
    assert results == []
