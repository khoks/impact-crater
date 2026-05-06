import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import JobPreview from "../routes/JobPreview";

function mockFetch(body: unknown, status = 200): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    })) as unknown as typeof fetch
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

  it("Approve disabled (M7); Refine button enabled (M6)", async () => {
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
    const approve = await screen.findByRole("button", { name: /Approve/ });
    const refine = await screen.findByRole("button", { name: /Refine this result/ });
    expect(approve).toBeDisabled();
    expect(refine).not.toBeDisabled();
    expect(approve).toHaveAttribute("title", expect.stringMatching(/M7/));
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
});
