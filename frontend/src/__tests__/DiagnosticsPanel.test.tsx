import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import DiagnosticsPanel from "../components/DiagnosticsPanel";

const DIAG = {
  schema_version: 1,
  project_id: "proj-1",
  snapshot_id: "snap-1",
  phases: [
    {
      phase: "stage_4_prefilter",
      title: "Pre-filter",
      description: "Quality + dedup",
      summary: { input_count: 3, kept: 1 },
      decisions: [
        {
          content_hash: "keep1",
          ref: "keep1",
          decision: "keep",
          caption: "the summit shot",
          thumb_url: "/api/media/keep1/thumb.jpg",
        },
        {
          content_hash: "drop1",
          ref: "drop1",
          decision: "drop",
          reason: "semantic_duplicate",
          thumb_url: "/api/media/drop1/thumb.jpg",
        },
      ],
    },
  ],
};

function mockFetch(routes: Record<string, { status: number; body: unknown }>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const key = Object.keys(routes).find((k) => url.includes(k));
      const route = key ? routes[key] : { status: 404, body: {} };
      return {
        ok: route.status >= 200 && route.status < 300,
        status: route.status,
        json: async () => route.body,
        // expose what was posted for assertions
        _init: init,
      };
    }) as unknown as typeof fetch
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("DiagnosticsPanel", () => {
  it("renders phases and decisions, and submits feedback", async () => {
    const postBodies: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/diagnostics")) {
          return { ok: true, status: 200, json: async () => DIAG };
        }
        if (url.includes("/api/feedback")) {
          postBodies.push(String(init?.body));
          return { ok: true, status: 201, json: async () => ({ id: 1 }) };
        }
        return { ok: false, status: 404, json: async () => ({}) };
      }) as unknown as typeof fetch
    );

    render(<DiagnosticsPanel snapshotId="snap-1" jobId="job-1" projectId="proj-1" />);

    // Phase header appears with its summary.
    await waitFor(() => expect(screen.getByText("Pre-filter")).toBeInTheDocument());
    expect(screen.getByText(/1\/3 kept/)).toBeInTheDocument();

    // Expand the phase → decision cards show.
    await userEvent.click(screen.getByText("Pre-filter"));
    expect(screen.getByText("the summit shot")).toBeInTheDocument();
    expect(screen.getByText("semantic_duplicate")).toBeInTheDocument();

    // Open the feedback popup on the dropped item.
    const buttons = screen.getAllByRole("button", { name: "Feedback" });
    await userEvent.click(buttons[1]);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/Was this the right call/)).toBeInTheDocument();

    // Mark incorrect (default) + comment + submit.
    await userEvent.type(
      within(dialog).getByPlaceholderText(/What should have happened/),
      "best of the burst, keep it"
    );
    await userEvent.click(within(dialog).getByRole("button", { name: /Submit feedback/ }));

    await waitFor(() => expect(screen.getByText(/feedback saved/i)).toBeInTheDocument());
    expect(postBodies).toHaveLength(1);
    const sent = JSON.parse(postBodies[0]);
    expect(sent.phase).toBe("stage_4_prefilter");
    expect(sent.verdict).toBe("incorrect");
    expect(sent.content_hash).toBe("drop1");
    expect(sent.decision_ref).toBe("drop:semantic_duplicate");
    expect(sent.comment).toBe("best of the burst, keep it");
  });

  it("shows a friendly message when diagnostics are missing (pre-feature snapshot)", async () => {
    mockFetch({ "/diagnostics": { status: 404, body: {} } });
    render(<DiagnosticsPanel snapshotId="old-snap" />);
    await waitFor(() =>
      expect(screen.getByText(/predates the feedback feature/)).toBeInTheDocument()
    );
  });
});
