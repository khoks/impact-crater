import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import PublishLog from "../routes/PublishLog";

function row(id: number, overrides: Record<string, unknown> = {}) {
  return {
    id,
    published_at: "2026-11-03T10:00:00+00:00",
    project_id: "p1",
    project_name: "Zion trip",
    snapshot_id: `snap-${id}`,
    platform: "youtube",
    dry_run: true,
    visibility: "private",
    external_id: "x",
    external_url: `https://dry-run.local/youtube/${id}`,
    response_code: 200,
    approval_token: `tok-${id}`,
    render_content_hash: "a".repeat(64),
    render_check: "match",
    ...overrides,
  };
}

function mockAudit(pages: Record<number, unknown>) {
  const fn = vi.fn(async (url: string) => {
    const offset = Number(new URL(url, "http://x").searchParams.get("offset"));
    return { ok: true, status: 200, json: async () => pages[offset] };
  });
  vi.stubGlobal("fetch", fn as unknown as typeof fetch);
  return fn;
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("PublishLog", () => {
  it("marks dry-runs apart from live posts and flags a changed file", async () => {
    mockAudit({
      0: {
        items: [
          row(2, {
            dry_run: false,
            external_url: "https://youtu.be/abc",
            render_check: "changed",
          }),
          row(1),
        ],
        total: 2,
        limit: 25,
        offset: 0,
      },
    });
    render(
      <MemoryRouter>
        <PublishLog />
      </MemoryRouter>
    );

    const live = await screen.findByTestId("audit-row-2");
    expect(within(live).getByText("Live")).toBeInTheDocument();
    expect(within(live).getByRole("link", { name: "https://youtu.be/abc" })).toHaveAttribute(
      "href",
      "https://youtu.be/abc"
    );
    expect(within(live).getByText("(file changed since)")).toBeInTheDocument();
    expect(within(live).getByRole("link", { name: "snap-2" })).toHaveAttribute(
      "href",
      "/snapshots/snap-2/inspect?project=p1"
    );

    const dry = screen.getByTestId("audit-row-1");
    expect(within(dry).getByText("Dry-run")).toBeInTheDocument();
    expect(within(dry).getByText(/Would publish to/)).toBeInTheDocument();
    expect(within(dry).queryByRole("link", { name: /dry-run\.local/ })).toBeNull();
    expect(within(dry).getByText("(file matches)")).toBeInTheDocument();
    expect(within(dry).getByText("aaaaaaaaaaaa")).toBeInTheDocument();
  });

  it("pages to older attempts", async () => {
    const fn = mockAudit({
      0: { items: [row(30)], total: 30, limit: 25, offset: 0 },
      25: { items: [row(5, { render_check: "unrecorded", render_content_hash: "" })], total: 30, limit: 25, offset: 25 },
    });
    render(
      <MemoryRouter>
        <PublishLog />
      </MemoryRouter>
    );

    await screen.findByTestId("audit-row-30");
    expect(screen.getByRole("button", { name: "← Newer" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Older →" }));

    expect(await screen.findByTestId("audit-row-5")).toBeInTheDocument();
    expect(screen.getByText("(not recorded)")).toBeInTheDocument();
    expect(screen.getByText("26–30 of 30")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Older →" })).toBeDisabled();
    expect(fn.mock.calls.map((c) => c[0])).toContain("/api/audit?limit=25&offset=25");
  });

  it("says so when nothing has been published", async () => {
    mockAudit({ 0: { items: [], total: 0, limit: 25, offset: 0 } });
    render(
      <MemoryRouter>
        <PublishLog />
      </MemoryRouter>
    );
    expect(await screen.findByText("Nothing has been published yet.")).toBeInTheDocument();
  });
});
