import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import Dashboard, { refineChain } from "../routes/Dashboard";

function mockFetchRoutes(routes: Record<string, unknown>): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      const key = Object.keys(routes).find((k) => url.includes(k));
      if (!key) {
        return { ok: false, status: 404, json: async () => ({}) };
      }
      return { ok: true, status: 200, json: async () => routes[key] };
    }) as unknown as typeof fetch
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

const PROJECTS = [
  {
    id: "project-abc123",
    name: "Zion trip",
    brief: "Canyon Overlook hike story",
    created_at: "2026-06-11 00:26:53",
    updated_at: "2026-06-11 00:26:53",
    snapshots: [
      {
        id: "snap-1",
        created_at: "2026-06-11 00:30:00",
        parent_snapshot_id: null,
        render_status: "success",
        has_render: true,
        publishes: [],
      },
      {
        id: "snap-2",
        created_at: "2026-06-11 00:28:00",
        parent_snapshot_id: null,
        render_status: "failure",
        has_render: false,
        publishes: [],
      },
    ],
  },
];

const JOBS = [
  {
    job_id: "job-1",
    project_id: "project-abc123",
    snapshot_id: null,
    state: "running",
    submitted_at: "2026-06-11T00:26:52Z",
    started_at: null,
    completed_at: null,
    stages: [],
    cost_by_tier_usd: {},
    cost_by_provider_usd: {},
    total_cost_usd: 0,
    cache_hits: 0,
    cache_misses: 0,
    render_path: null,
    failure_reason: null,
    correlation_id: "",
    project_name: "Zion trip",
    brief: "Canyon Overlook hike story",
    media_count: 34,
    target_duration_seconds: 60,
  },
];

describe("Dashboard", () => {
  it("shows the empty state when there are no projects or jobs", async () => {
    mockFetchRoutes({ "/api/projects": [], "/api/jobs": [] });
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText(/No projects yet/i)).toBeInTheDocument();
    });
  });

  it("lists projects with snapshots and a watch control", async () => {
    mockFetchRoutes({ "/api/projects": PROJECTS, "/api/jobs": [] });
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText("Zion trip")).toBeInTheDocument();
    });
    expect(screen.getByText(/Canyon Overlook hike story/)).toBeInTheDocument();
    expect(screen.getByText("success")).toBeInTheDocument();
    expect(screen.getByText("failure")).toBeInTheDocument();
    expect(screen.queryByText(/No projects yet/i)).not.toBeInTheDocument();

    // Only the successful snapshot with a file gets a Watch control;
    // clicking it mounts the inline <video> pointed at the render URL.
    const watch = screen.getByRole("button", { name: /watch/i });
    await userEvent.click(watch);
    const video = document.querySelector("video");
    expect(video).not.toBeNull();
    expect(video!.getAttribute("src")).toBe("/api/snapshots/snap-1/render.mp4");
  });

  it("lists session jobs with state and links to the job page", async () => {
    mockFetchRoutes({ "/api/projects": [], "/api/jobs": JOBS });
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText(/Jobs this session/i)).toBeInTheDocument();
    });
    expect(screen.getByText("running")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Zion trip/i });
    expect(link.getAttribute("href")).toBe("/jobs/job-1");
  });

  it("nests refined snapshots under their parent and marks dry-runs apart from posts", async () => {
    const snap = (id: string, parent: string | null, created: string, publishes: unknown[] = []) => ({
      id,
      parent_snapshot_id: parent,
      created_at: created,
      render_status: "success",
      has_render: false,
      publishes,
    });
    mockFetchRoutes({
      "/api/projects": [
        {
          ...PROJECTS[0],
          snapshots: [
            snap("child-b", "root", "2026-06-11 03:00:00", [
              {
                platform: "youtube",
                dry_run: false,
                external_url: "https://youtu.be/xyz",
                published_at: "2026-06-12T00:00:00+00:00",
              },
            ]),
            snap("other", null, "2026-06-11 02:30:00"),
            snap("child-a", "root", "2026-06-11 02:00:00", [
              {
                platform: "youtube",
                dry_run: true,
                external_url: "https://dry.example/1",
                published_at: "2026-06-11T05:00:00+00:00",
              },
            ]),
            snap("root", null, "2026-06-11 01:00:00"),
          ],
        },
      ],
      "/api/jobs": [],
    });
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByTestId("snapshot-row-root")).toBeInTheDocument();
    });
    const order = Array.from(document.querySelectorAll("[data-testid^='snapshot-row-']")).map(
      (el) => el.getAttribute("data-testid")
    );
    expect(order).toEqual([
      "snapshot-row-other",
      "snapshot-row-root",
      "snapshot-row-child-b",
      "snapshot-row-child-a",
    ]);
    expect(screen.getAllByText("↳ refined")).toHaveLength(2);
    const live = screen.getByRole("link", { name: /Published · youtube/ });
    expect(live.getAttribute("href")).toBe("https://youtu.be/xyz");
    expect(screen.getByText("Dry-run · youtube")).toBeInTheDocument();
  });

  it("shows a child whose parent is missing as a root", () => {
    const rows = refineChain([
      {
        id: "orphan",
        parent_snapshot_id: "gone",
        created_at: "x",
        render_status: "success",
        has_render: true,
        publishes: [],
      },
    ]);
    expect(rows).toEqual([expect.objectContaining({ depth: 0 })]);
  });
});
