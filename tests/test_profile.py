"""Tests for the cross-project user profile (N-010 deterministic MVP)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest

from impact_crater import paths, profile as profile_mod
from impact_crater.app import create_app
from impact_crater.profile import FeedbackEvent, derive_profile, emit, reset


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---- Repo-direct tests ------------------------------------------------


def test_emit_appends_jsonl_line(isolated_home: Path) -> None:
    emit(FeedbackEvent(event_type="approve", project_id="p1"))
    target = paths.profile_dir() / "feedback_log.jsonl"
    assert target.is_file()
    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1


def test_derive_empty_log_returns_empty_profile(isolated_home: Path) -> None:
    p = derive_profile()
    assert p.is_empty()
    assert p.derived_from_n_events == 0


def test_derive_counts_approvals_refinements_cancels(isolated_home: Path) -> None:
    emit(FeedbackEvent(event_type="approve", project_id="p1"))
    emit(FeedbackEvent(event_type="approve", project_id="p2"))
    emit(FeedbackEvent(event_type="refine", project_id="p1"))
    emit(FeedbackEvent(event_type="job_cancelled", project_id="p1"))
    p = derive_profile()
    assert p.narrative_patterns.approved_count == 2
    assert p.narrative_patterns.refined_count == 1
    assert p.narrative_patterns.cancelled_count == 1
    assert p.derived_from_n_events == 4


def test_derive_aggregates_target_durations(isolated_home: Path) -> None:
    for d in (60, 90, 120):
        emit(
            FeedbackEvent(
                event_type="approve",
                project_id="p",
                payload={"target_duration_seconds": d},
            )
        )
    p = derive_profile()
    assert p.style_preferences.target_duration_seconds_avg == 90.0
    assert p.style_preferences.target_duration_seconds_observed == [60, 90, 120]


def test_derive_second_guess_acceptance_rate(isolated_home: Path) -> None:
    emit(FeedbackEvent(event_type="second_guess_accepted", project_id="p"))
    emit(FeedbackEvent(event_type="second_guess_accepted", project_id="p"))
    emit(FeedbackEvent(event_type="second_guess_accepted", project_id="p"))
    emit(FeedbackEvent(event_type="second_guess_rejected", project_id="p"))
    p = derive_profile()
    assert p.orchestrator_priors.second_guess_acceptance_rate == 0.75


def test_derive_visibility_counts_from_publish_events(isolated_home: Path) -> None:
    emit(
        FeedbackEvent(
            event_type="publish_succeeded",
            project_id="p",
            payload={"visibility": "public"},
        )
    )
    emit(
        FeedbackEvent(
            event_type="publish_succeeded",
            project_id="p",
            payload={"visibility": "public"},
        )
    )
    emit(
        FeedbackEvent(
            event_type="publish_succeeded",
            project_id="p",
            payload={"visibility": "unlisted"},
        )
    )
    p = derive_profile()
    assert p.style_preferences.visibility_counts == {"public": 2, "unlisted": 1}


def test_reset_wipes_log_and_profile(isolated_home: Path) -> None:
    emit(FeedbackEvent(event_type="approve", project_id="p"))
    p = derive_profile()
    profile_mod.save_profile(p)
    reset()
    assert not (paths.profile_dir() / "feedback_log.jsonl").is_file()
    assert not (paths.profile_dir() / "profile.json").is_file()


def test_suggestions_empty_when_profile_empty(isolated_home: Path) -> None:
    s = profile_mod.suggestions_for_new_job()
    assert s.suggested_target_duration_seconds is None
    assert s.suggested_mode is None
    assert s.suggested_visibility is None


def test_suggestions_populated_after_derivation(isolated_home: Path) -> None:
    for d in (60, 90, 120, 90):
        emit(
            FeedbackEvent(
                event_type="approve",
                project_id="p",
                payload={"target_duration_seconds": d, "mode": "music_video"},
            )
        )
    emit(
        FeedbackEvent(
            event_type="publish_succeeded",
            project_id="p",
            payload={"visibility": "unlisted"},
        )
    )
    p = derive_profile()
    profile_mod.save_profile(p)
    s = profile_mod.suggestions_for_new_job(p)
    assert s.suggested_target_duration_seconds == 90  # round(90.0)
    assert s.suggested_mode == "music_video"
    assert s.suggested_visibility == "unlisted"
    assert "music_video" in s.rationale
    assert "unlisted" in s.rationale


# ---- HTTP tests -------------------------------------------------------


async def test_get_snapshot_returns_empty_profile(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/profile/snapshot")
    assert r.status_code == 200
    body = r.json()
    assert body["profile"]["derived_from_n_events"] == 0
    assert body["suggestions"]["suggested_target_duration_seconds"] is None


async def test_post_feedback_appends(client: httpx.AsyncClient, isolated_home: Path) -> None:
    r = await client.post(
        "/api/profile/feedback",
        json={"event_type": "approve", "project_id": "p1"},
    )
    assert r.status_code == 200
    assert (paths.profile_dir() / "feedback_log.jsonl").is_file()


async def test_post_derive_then_snapshot(client: httpx.AsyncClient, isolated_home: Path) -> None:
    await client.post(
        "/api/profile/feedback",
        json={
            "event_type": "approve",
            "project_id": "p1",
            "payload": {"target_duration_seconds": 120, "mode": "standard"},
        },
    )
    await client.post("/api/profile/feedback", json={"event_type": "approve", "project_id": "p2"})
    r = await client.post("/api/profile/derive")
    assert r.status_code == 200
    assert r.json()["derived_from_n_events"] == 2
    snap = (await client.get("/api/profile/snapshot")).json()
    assert snap["profile"]["narrative_patterns"]["approved_count"] == 2


async def test_post_reset_clears_state(client: httpx.AsyncClient, isolated_home: Path) -> None:
    await client.post("/api/profile/feedback", json={"event_type": "approve", "project_id": "p1"})
    await client.post("/api/profile/derive")
    r = await client.post("/api/profile/reset")
    assert r.status_code == 200
    snap = (await client.get("/api/profile/snapshot")).json()
    assert snap["profile"]["derived_from_n_events"] == 0


async def test_post_feedback_rejects_unknown_event_type(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/profile/feedback",
        json={"event_type": "definitely_not_a_real_event", "project_id": "p1"},
    )
    assert r.status_code == 422
