import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import FeedbackTracker from "../routes/FeedbackTracker";
import WorkplanTracker from "../routes/WorkplanTracker";

function mockRoutes(routes: Record<string, unknown>, captures?: { patches: Array<{ url: string; body: unknown }> }) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === "PATCH") {
        captures?.patches.push({ url, body: init.body ? JSON.parse(String(init.body)) : null });
        // echo back a plausible patched feedback item
        return { ok: true, status: 200, json: async () => ({ id: 1, verdict: "incorrect", phase: "stage_4_prefilter", status: "addressed", priority: "P0", has_screenshot: false, decision_ref: "drop:x", comment: "c", created_at: "t", job_id: null, project_id: null, snapshot_id: null, content_hash: null }) };
      }
      const key = Object.keys(routes).find((k) => url.includes(k));
      return { ok: true, status: 200, json: async () => (key ? routes[key] : []) };
    }) as unknown as typeof fetch
  );
}

beforeEach(() => vi.unstubAllGlobals());

describe("FeedbackTracker", () => {
  it("lists items and patches priority", async () => {
    const captures = { patches: [] as Array<{ url: string; body: unknown }> };
    mockRoutes(
      {
        "/api/feedback": [
          {
            id: 1, verdict: "incorrect", phase: "stage_4_prefilter", decision_ref: "drop:semantic_duplicate",
            comment: "keep this", status: "new", priority: "P2", has_screenshot: true,
            job_id: "j", project_id: "p", snapshot_id: "s", content_hash: "h", created_at: "2026-06-14",
          },
        ],
      },
      captures
    );
    render(<MemoryRouter><FeedbackTracker /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/stage_4_prefilter · drop:semantic_duplicate/)).toBeInTheDocument());
    // Two pill selects (priority + status); change the priority one.
    const selects = screen.getAllByRole("combobox");
    await userEvent.selectOptions(selects[0], "P0");
    await waitFor(() => expect(captures.patches.length).toBe(1));
    expect(captures.patches[0].url).toContain("/api/feedback/1");
    expect(captures.patches[0].body).toEqual({ priority: "P0" });
  });
});

describe("WorkplanTracker", () => {
  const PLAN = {
    available: true,
    counts_by_status: { done: 1, "in-progress": 1 },
    counts_by_phase: { mvp: 2 },
    items: [
      { id: "I-2", title: "MVP north star", type: "initiative", status: "in-progress", phase: "mvp", priority: "P0", markdown_priority: "P0", priority_overridden: false, parent: null, updated: null, tags: [], override_note: null },
      { id: "S-2.9.8", title: "Feedback loop", type: "story", status: "done", phase: "mvp", priority: "P1", markdown_priority: "P1", priority_overridden: false, parent: "I-2", updated: null, tags: [], override_note: null },
    ],
  };

  it("renders the hierarchy and patches a priority override", async () => {
    const captures = { patches: [] as Array<{ url: string; body: unknown }> };
    mockRoutes({ "/api/workplan": PLAN }, captures);
    render(<MemoryRouter><WorkplanTracker /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText("MVP north star")).toBeInTheDocument());
    expect(screen.getByText("Feedback loop")).toBeInTheDocument();
    expect(screen.getByText("I-2")).toBeInTheDocument();

    const selects = screen.getAllByRole("combobox");
    await userEvent.selectOptions(selects[1], "P0"); // the story's priority
    await waitFor(() => expect(captures.patches.length).toBe(1));
    expect(captures.patches[0].url).toContain("/api/workplan/S-2.9.8");
    expect(captures.patches[0].body).toEqual({ priority: "P0" });
  });

  it("shows a notice when project tracker is unavailable", async () => {
    mockRoutes({ "/api/workplan": { available: false, items: [], counts_by_status: {}, counts_by_phase: {} } });
    render(<MemoryRouter><WorkplanTracker /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/isn't available in this install/)).toBeInTheDocument());
  });
});
