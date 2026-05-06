import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import JobInProgress from "../routes/JobInProgress";

// ---- Tiny in-test WebSocket mock ---------------------------------------

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  readyState = 0;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  close(): void {
    this.readyState = 3;
    this.onclose?.();
  }

  emit(event: unknown): void {
    this.onmessage?.({ data: JSON.stringify(event) });
  }
}

function mockFetchByUrl(map: Record<string, { ok: boolean; status: number; body: unknown }>): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const path = url.replace(/^https?:\/\/[^/]+/, "");
      const r = map[path];
      if (!r) throw new Error(`No mock for fetch ${url}`);
      return {
        ok: r.ok,
        status: r.status,
        json: async () => r.body,
      };
    }) as unknown as typeof fetch
  );
}

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.unstubAllGlobals();
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  // jsdom's window.location.host is "localhost:3000" by default — fine.
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function baseSnapshot(): unknown {
  return {
    job_id: "job-1",
    project_id: "proj-1",
    snapshot_id: null,
    state: "running",
    submitted_at: "2026-05-05T00:00:00Z",
    started_at: "2026-05-05T00:00:01Z",
    completed_at: null,
    stages: [
      "stage_1_ingest",
      "stage_2_bulk_ops",
      "stage_3_metadata",
      "stage_4_prefilter",
      "stage_5_judge",
      "stage_6_plan",
      "stage_7_render",
    ].map((s) => ({
      stage: s,
      state: "pending",
      started_at: null,
      completed_at: null,
      detail: "",
    })),
    cost_by_tier_usd: {},
    cost_by_provider_usd: {},
    total_cost_usd: 0,
    cache_hits: 0,
    cache_misses: 0,
    render_path: null,
    failure_reason: null,
    correlation_id: "cid",
  };
}

// ---- Tests -------------------------------------------------------------

describe("JobInProgress", () => {
  it("renders the 7 stages from the initial snapshot", async () => {
    mockFetchByUrl({
      "/api/jobs/job-1": { ok: true, status: 200, body: baseSnapshot() },
    });
    render(
      <MemoryRouter initialEntries={["/jobs/job-1"]}>
        <Routes>
          <Route path="/jobs/:job_id" element={<JobInProgress />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText(/Stage 1 · Ingest/)).toBeInTheDocument();
      expect(screen.getByText(/Stage 7 · Render/)).toBeInTheDocument();
    });
  });

  it("updates a stage to running when a `stage` event arrives", async () => {
    mockFetchByUrl({
      "/api/jobs/job-1": { ok: true, status: 200, body: baseSnapshot() },
    });
    render(
      <MemoryRouter initialEntries={["/jobs/job-1"]}>
        <Routes>
          <Route path="/jobs/:job_id" element={<JobInProgress />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBeGreaterThan(0);
    });
    act(() => {
      MockWebSocket.instances[0].emit({
        type: "stage",
        job_id: "job-1",
        timestamp: "2026-05-05T00:00:02Z",
        payload: {
          stage: "stage_1_ingest",
          state: "running",
          detail: "ingesting…",
          started_at: "2026-05-05T00:00:02Z",
          completed_at: null,
        },
      });
    });
    await waitFor(() => {
      expect(screen.getByText(/ingesting…/)).toBeInTheDocument();
    });
  });

  it("aggregates cost from llm_call events", async () => {
    mockFetchByUrl({
      "/api/jobs/job-1": { ok: true, status: 200, body: baseSnapshot() },
    });
    render(
      <MemoryRouter initialEntries={["/jobs/job-1"]}>
        <Routes>
          <Route path="/jobs/:job_id" element={<JobInProgress />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBeGreaterThan(0);
    });
    act(() => {
      MockWebSocket.instances[0].emit({
        type: "llm_call",
        job_id: "job-1",
        timestamp: "2026-05-05T00:00:03Z",
        payload: {
          operation: "caption_image",
          provider: "google",
          tier: "S",
          cost_usd: 0.001,
          cache_hit: false,
          total_cost_usd: 0.42,
          cost_by_tier_usd: { S: 0.001, M: 0.42 },
          cost_by_provider_usd: { google: 0.001 },
        },
      });
    });
    await waitFor(() => {
      // Both the headline ($0.42) and the per-tier breakdown ($0.4200)
      // contain the substring; assert at least one match.
      expect(screen.getAllByText(/\$0\.42/).length).toBeGreaterThanOrEqual(1);
    });
  });

  it("redirects to /jobs/:id/preview when state event reports succeeded", async () => {
    mockFetchByUrl({
      "/api/jobs/job-1": { ok: true, status: 200, body: baseSnapshot() },
    });
    render(
      <MemoryRouter initialEntries={["/jobs/job-1"]}>
        <Routes>
          <Route path="/jobs/:job_id" element={<JobInProgress />} />
          <Route path="/jobs/:job_id/preview" element={<div>PREVIEW</div>} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBeGreaterThan(0);
    });
    act(() => {
      MockWebSocket.instances[0].emit({
        type: "state",
        job_id: "job-1",
        timestamp: "now",
        payload: {
          state: "succeeded",
          snapshot_id: "snap-1",
          failure_reason: null,
          render_path: "/some/render.mp4",
        },
      });
    });
    await waitFor(() => {
      expect(screen.getByText("PREVIEW")).toBeInTheDocument();
    });
  });

  it("renders the failure detail when state event reports failed", async () => {
    mockFetchByUrl({
      "/api/jobs/job-1": { ok: true, status: 200, body: baseSnapshot() },
    });
    render(
      <MemoryRouter initialEntries={["/jobs/job-1"]}>
        <Routes>
          <Route path="/jobs/:job_id" element={<JobInProgress />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBeGreaterThan(0);
    });
    act(() => {
      MockWebSocket.instances[0].emit({
        type: "state",
        job_id: "job-1",
        timestamp: "now",
        payload: {
          state: "failed",
          snapshot_id: null,
          failure_reason: "render_failed:loudnorm",
          render_path: null,
        },
      });
    });
    await waitFor(() => {
      expect(screen.getByText(/render_failed:loudnorm/)).toBeInTheDocument();
      expect(screen.getByText(/Job failed/)).toBeInTheDocument();
    });
  });
});
