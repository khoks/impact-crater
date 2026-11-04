import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import JobPreview from "../routes/JobPreview";

const DRY_RUN_STATUS = {
  platforms: [
    { platform: "youtube", connected: false },
    { platform: "instagram", connected: false },
    { platform: "facebook", connected: false },
  ],
  dry_run: true,
};

function mockFetch(
  body: unknown,
  status = 200,
  extra: Record<string, unknown> = {}
): void {
  const routes: Record<string, unknown> = {
    "/api/connectors/status": DRY_RUN_STATUS,
    "/api/snapshots/snap-1/publish-defaults": {
      title: "Zion in Spring",
      description: "A short reel of our Zion hikes.",
    },
    ...extra,
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const routed = routes[url];
      return {
        ok: routed !== undefined || (status >= 200 && status < 300),
        status: routed !== undefined ? 200 : status,
        json: async () => routed ?? body,
      };
    }) as unknown as typeof fetch
  );
}

const SUCCEEDED_JOB = {
  job_id: "job-1",
  project_id: "p1",
  project_name: "",
  snapshot_id: "snap-1",
  state: "succeeded",
  submitted_at: "x",
  started_at: "x",
  completed_at: "x",
  stages: [],
  cost_by_tier_usd: {},
  cost_by_provider_usd: {},
  total_cost_usd: 0,
  cache_hits: 0,
  cache_misses: 0,
  render_path: "/x.mp4",
  failure_reason: null,
  correlation_id: "cid",
};

function renderPreview(): void {
  render(
    <MemoryRouter initialEntries={["/jobs/job-1/preview"]}>
      <Routes>
        <Route path="/jobs/:job_id/preview" element={<JobPreview />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("JobPreview", () => {
  it("renders the video element with the snapshot's render URL", async () => {
    mockFetch({
      job_id: "job-1",
      project_id: "p1",
      snapshot_id: "snap-1",
      state: "succeeded",
      submitted_at: "x",
      started_at: "x",
      completed_at: "x",
      stages: [],
      cost_by_tier_usd: {},
      cost_by_provider_usd: {},
      total_cost_usd: 0.42,
      cache_hits: 1,
      cache_misses: 2,
      render_path: "/some/render.mp4",
      failure_reason: null,
      correlation_id: "cid",
    });
    render(
      <MemoryRouter initialEntries={["/jobs/job-1/preview"]}>
        <Routes>
          <Route path="/jobs/:job_id/preview" element={<JobPreview />} />
        </Routes>
      </MemoryRouter>
    );
    const video = await screen.findByTestId("preview-video");
    expect(video).toHaveAttribute(
      "src",
      "/api/snapshots/snap-1/render.mp4"
    );
  });

  it("Approve & publish + Refine buttons are both enabled (M6 + M7 wired)", async () => {
    mockFetch({
      job_id: "job-1",
      project_id: "p1",
      snapshot_id: "snap-1",
      state: "succeeded",
      submitted_at: "x",
      started_at: "x",
      completed_at: "x",
      stages: [],
      cost_by_tier_usd: {},
      cost_by_provider_usd: {},
      total_cost_usd: 0,
      cache_hits: 0,
      cache_misses: 0,
      render_path: "/x.mp4",
      failure_reason: null,
      correlation_id: "cid",
    });
    render(
      <MemoryRouter initialEntries={["/jobs/job-1/preview"]}>
        <Routes>
          <Route path="/jobs/:job_id/preview" element={<JobPreview />} />
        </Routes>
      </MemoryRouter>
    );
    const approve = await screen.findByRole("button", { name: /Approve & publish/ });
    const refine = await screen.findByRole("button", { name: /Refine this result/ });
    expect(approve).not.toBeDisabled();
    expect(refine).not.toBeDisabled();
  });

  it("surfaces an error when the job is not yet succeeded", async () => {
    mockFetch({
      job_id: "job-1",
      project_id: "p1",
      snapshot_id: null,
      state: "running",
      submitted_at: "x",
      started_at: "x",
      completed_at: null,
      stages: [],
      cost_by_tier_usd: {},
      cost_by_provider_usd: {},
      total_cost_usd: 0,
      cache_hits: 0,
      cache_misses: 0,
      render_path: null,
      failure_reason: null,
      correlation_id: "cid",
    });
    render(
      <MemoryRouter initialEntries={["/jobs/job-1/preview"]}>
        <Routes>
          <Route path="/jobs/:job_id/preview" element={<JobPreview />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText(/Preview unavailable/)).toBeInTheDocument();
    });
  });

  it("says dry-run posts nothing and pre-fills title and description", async () => {
    mockFetch(SUCCEEDED_JOB);
    renderPreview();
    expect(
      await screen.findByText(/Dry-run is on: Approve checks the request/)
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Approve & publish/ }));
    expect(await screen.findByDisplayValue("Zion in Spring")).toBeInTheDocument();
    expect(screen.getByDisplayValue("A short reel of our Zion hikes.")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "private" })).toBeChecked();
  });

  it("offers only the visibilities each platform accepts", async () => {
    mockFetch(SUCCEEDED_JOB);
    renderPreview();
    await userEvent.click(await screen.findByRole("button", { name: /Approve & publish/ }));
    await userEvent.click(screen.getByRole("button", { name: /^Instagram/ }));
    expect(screen.getAllByRole("radio").map((r) => (r as HTMLInputElement).value)).toEqual([
      "public",
    ]);
    expect(screen.getByRole("radio", { name: "public" })).toBeChecked();
    await userEvent.click(screen.getByRole("button", { name: /^Facebook/ }));
    expect(screen.getAllByRole("radio").map((r) => (r as HTMLInputElement).value)).toEqual([
      "unlisted",
      "public",
    ]);
    expect(screen.getByText(/refuses until the credentials exist/)).toBeInTheDocument();
  });
});
