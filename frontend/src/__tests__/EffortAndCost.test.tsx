import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import EffortAndCost from "../routes/EffortAndCost";
import { useNewProjectStore } from "../stores/newProjectStore";

interface MockResponse {
  ok: boolean;
  status: number;
  body: unknown;
}

function mockFetchByUrl(map: Record<string, MockResponse>): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      // Strip leading origin if any.
      const path = url.replace(/^https?:\/\/[^/]+/, "");
      const r = map[path] ?? map[Object.keys(map).find((k) => path.startsWith(k)) ?? ""];
      if (!r) throw new Error(`No mock for fetch ${url}`);
      return {
        ok: r.ok,
        status: r.status,
        json: async () => r.body,
      };
    }) as unknown as typeof fetch
  );
}

function seedDraft(): void {
  useNewProjectStore.setState({
    draft: {
      name: "Trip",
      brief: "warm to cool",
      folder_path: "/tmp/photos",
      audio_path: "/tmp/song.mp3",
      target_duration_seconds: 30,
      scanned_media_paths: ["/tmp/photos/a.jpg", "/tmp/photos/b.jpg"],
      scanned_photo_count: 2,
      scanned_video_count: 0,
      scanned_total_bytes: 4096,
    },
  });
}

beforeEach(() => {
  useNewProjectStore.setState({ draft: null });
  vi.unstubAllGlobals();
});

describe("EffortAndCost", () => {
  it("redirects back to /projects/new when no draft is staged", async () => {
    render(
      <MemoryRouter initialEntries={["/projects/new/effort"]}>
        <Routes>
          <Route path="/projects/new/effort" element={<EffortAndCost />} />
          <Route path="/projects/new" element={<div>NEW_PROJECT</div>} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText("NEW_PROJECT")).toBeInTheDocument();
    });
  });

  it("renders 3 effort levels and the recommended badge", async () => {
    seedDraft();
    mockFetchByUrl({
      "/api/effort-levels": {
        ok: true,
        status: 200,
        body: {
          levels: [
            {
              id: "L1",
              label: "L1",
              photo_cap: 10,
              video_cap: 1,
              estimated_cost_usd_low: 0.5,
              estimated_cost_usd_high: 2,
              description: "L1 desc",
              fits_today_budget: true,
            },
            {
              id: "L2",
              label: "L2",
              photo_cap: 100,
              video_cap: 10,
              estimated_cost_usd_low: 2,
              estimated_cost_usd_high: 7,
              description: "L2 desc",
              fits_today_budget: true,
            },
            {
              id: "L3",
              label: "L3",
              photo_cap: 1000,
              video_cap: 50,
              estimated_cost_usd_low: 7,
              estimated_cost_usd_high: 22,
              description: "L3 desc",
              fits_today_budget: false,
            },
          ],
          today_total_spent_usd: 0,
          today_per_provider_spent_usd: {},
          cap_total_usd: 10,
          cap_per_provider_usd: {},
          recommended_level_id: "L2",
        },
      },
      "/api/cost-preview": {
        ok: true,
        status: 200,
        body: {
          estimated_cost_usd_low: 0.5,
          estimated_cost_usd_high: 1,
          cost_by_tier_usd: { S: 0.1, M: 0.4, L: 0.5, embedding: 0.0001 },
          today_remaining_usd: 8,
          fits_today_budget: true,
          blocking_reason: null,
        },
      },
    });

    render(
      <MemoryRouter initialEntries={["/projects/new/effort"]}>
        <Routes>
          <Route path="/projects/new/effort" element={<EffortAndCost />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/L1 desc/)).toBeInTheDocument();
      expect(screen.getByText(/L3 desc/)).toBeInTheDocument();
    });
    // Recommended badge appears on L2.
    const recommendedBadges = screen.getAllByText(/recommended/);
    expect(recommendedBadges).toHaveLength(1);
    // Cost preview rendered.
    expect(screen.getByText(/\$0\.50 – \$1\.00/)).toBeInTheDocument();
  });

  it("submits the job and routes to /jobs/:id", async () => {
    seedDraft();
    mockFetchByUrl({
      "/api/effort-levels": {
        ok: true,
        status: 200,
        body: {
          levels: [
            {
              id: "L1",
              label: "L1",
              photo_cap: 10,
              video_cap: 1,
              estimated_cost_usd_low: 0.5,
              estimated_cost_usd_high: 2,
              description: "L1",
              fits_today_budget: true,
            },
          ],
          today_total_spent_usd: 0,
          today_per_provider_spent_usd: {},
          cap_total_usd: 10,
          cap_per_provider_usd: {},
          recommended_level_id: "L1",
        },
      },
      "/api/cost-preview": {
        ok: true,
        status: 200,
        body: {
          estimated_cost_usd_low: 0.5,
          estimated_cost_usd_high: 1,
          cost_by_tier_usd: { S: 0.1 },
          today_remaining_usd: 8,
          fits_today_budget: true,
          blocking_reason: null,
        },
      },
      "/api/jobs/submit": {
        ok: true,
        status: 202,
        body: {
          job_id: "job-xyz",
          project_id: "project-abc",
          state: "queued",
          submitted_at: "2026-05-05T00:00:00Z",
          websocket_url: "/api/jobs/ws/job-xyz",
        },
      },
    });

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/projects/new/effort"]}>
        <Routes>
          <Route path="/projects/new/effort" element={<EffortAndCost />} />
          <Route path="/jobs/:job_id" element={<div>JOB_ROUTE</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Start Job/i })).not.toBeDisabled();
    });
    await user.click(screen.getByRole("button", { name: /Start Job/i }));
    await waitFor(() => {
      expect(screen.getByText("JOB_ROUTE")).toBeInTheDocument();
    });
    // Draft was reset so a back-nav would bounce to /projects/new.
    expect(useNewProjectStore.getState().draft).toBeNull();
  });

  it("disables Submit when budget doesn't fit", async () => {
    seedDraft();
    mockFetchByUrl({
      "/api/effort-levels": {
        ok: true,
        status: 200,
        body: {
          levels: [
            {
              id: "L1",
              label: "L1",
              photo_cap: 10,
              video_cap: 1,
              estimated_cost_usd_low: 0.5,
              estimated_cost_usd_high: 2,
              description: "L1",
              fits_today_budget: false,
            },
          ],
          today_total_spent_usd: 0,
          today_per_provider_spent_usd: {},
          cap_total_usd: null,
          cap_per_provider_usd: {},
          recommended_level_id: null,
        },
      },
      "/api/cost-preview": {
        ok: true,
        status: 200,
        body: {
          estimated_cost_usd_low: 0.5,
          estimated_cost_usd_high: 1,
          cost_by_tier_usd: { S: 0.1 },
          today_remaining_usd: null,
          fits_today_budget: false,
          blocking_reason: "no_total_cap_configured",
        },
      },
    });

    render(
      <MemoryRouter initialEntries={["/projects/new/effort"]}>
        <Routes>
          <Route path="/projects/new/effort" element={<EffortAndCost />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Spend cap isn't configured/)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /Start Job/i })).toBeDisabled();
  });
});
