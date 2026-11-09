import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import SnapshotInspect from "../routes/SnapshotInspect";

const CHILD = {
  id: "child-1",
  project_id: "p1",
  project_name: "Zion trip",
  parent_snapshot_id: "root-1",
  children: [],
  created_at: "2026-06-11 02:00:00",
  render_status: "success",
  has_render: true,
  refinement_message: "shorter middle part",
  refinement_interpretation: "tighten the middle third",
  publishes: [],
};

const DRY_RUN_STATUS = {
  platforms: [
    { platform: "youtube", connected: false },
    { platform: "instagram", connected: false },
    { platform: "facebook", connected: false },
  ],
  dry_run: true,
};

function mockFetch(detail: unknown) {
  const published = [
    {
      platform: "youtube",
      dry_run: true,
      external_url: "https://dry.example/1",
      published_at: "2026-06-12T00:00:00+00:00",
    },
  ];
  let didPublish = false;
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body });
    if (url === "/api/snapshots/child-1") {
      return ok(didPublish ? { ...(detail as object), publishes: published } : detail);
    }
    if (url === "/api/snapshots/child-1/publish-defaults") {
      return ok({ title: "Zion in Spring", description: "Our hikes." });
    }
    if (url === "/api/connectors/status") return ok(DRY_RUN_STATUS);
    if (url === "/api/snapshots/child-1/publish" && init?.method === "POST") {
      didPublish = true;
      return ok({
        external_id: "dry",
        external_url: "https://dry.example/1",
        visibility: "private",
        audit_token: "tok-1",
        platform: "youtube",
        dry_run: true,
      });
    }
    return { ok: false, status: 404, json: async () => ({}) };
  });
  vi.stubGlobal("fetch", fn as unknown as typeof fetch);
  return fn;
}

function renderInspect() {
  render(
    <MemoryRouter initialEntries={["/snapshots/child-1/inspect"]}>
      <Routes>
        <Route path="/snapshots/:snapshot_id/inspect" element={<SnapshotInspect />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("SnapshotInspect", () => {
  it("shows where a refined snapshot came from and offers refine and publish", async () => {
    mockFetch(CHILD);
    renderInspect();

    expect(await screen.findByRole("heading", { name: "Zion trip" })).toBeInTheDocument();
    const parent = screen.getByRole("link", { name: "root-1" });
    expect(parent.getAttribute("href")).toBe("/snapshots/root-1/inspect?project=p1");
    expect(screen.getByTestId("refine-chain")).toHaveTextContent("“shorter middle part”");
    expect(screen.getByRole("button", { name: "Refine this result" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Approve & publish" })).toBeEnabled();
    expect(screen.getByTestId("inspect-video").getAttribute("src")).toBe(
      "/api/snapshots/child-1/render.mp4"
    );
  });

  it("publishes this snapshot and then shows it as a dry-run, not a post", async () => {
    const fn = mockFetch(CHILD);
    renderInspect();

    await userEvent.click(await screen.findByRole("button", { name: "Approve & publish" }));
    await waitFor(() => {
      expect(screen.getByDisplayValue("Zion in Spring")).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("button", { name: "Publish to YouTube" }));

    expect(await screen.findByText("Dry-run validated.")).toBeInTheDocument();
    const post = fn.mock.calls.find((c) => c[0] === "/api/snapshots/child-1/publish");
    expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({
      title: "Zion in Spring",
      visibility: "private",
      platform: "youtube",
    });
    expect(await screen.findByText("Dry-run · youtube")).toBeInTheDocument();
    expect(screen.queryByText(/Published ·/)).not.toBeInTheDocument();
  });

  it("does not offer actions for a snapshot without a render", async () => {
    mockFetch({ ...CHILD, has_render: false, parent_snapshot_id: null });
    renderInspect();

    expect(await screen.findByText(/no finished render on disk/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve & publish" })).not.toBeInTheDocument();
  });
});
