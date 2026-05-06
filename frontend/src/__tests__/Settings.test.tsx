import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import Settings from "../routes/Settings";

interface MockResponse {
  ok: boolean;
  status: number;
  body?: unknown;
}

function mockFetchSequence(responses: MockResponse[]): ReturnType<typeof vi.fn> {
  let i = 0;
  const fn = vi.fn(async (_url: string, _init?: RequestInit) => {
    const r = responses[Math.min(i, responses.length - 1)];
    i++;
    return {
      ok: r.ok,
      status: r.status,
      json: async () => r.body ?? {},
    };
  });
  vi.stubGlobal("fetch", fn as unknown as typeof fetch);
  return fn;
}

const SNAPSHOT_KEYS_SET = {
  has_anthropic_key: true,
  has_google_key: true,
  spend_cap_total_usd: 50.0,
  spend_cap_anthropic_usd: 30.0,
  spend_cap_google_usd: null,
  today_total_spent_usd: 1.5,
  today_per_provider_spent_usd: { anthropic: 1.5 },
};

const SNAPSHOT_KEYS_UNSET = {
  has_anthropic_key: false,
  has_google_key: false,
  spend_cap_total_usd: null,
  spend_cap_anthropic_usd: null,
  spend_cap_google_usd: null,
  today_total_spent_usd: 0,
  today_per_provider_spent_usd: {},
};

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("Settings", () => {
  it("loads the snapshot and shows 'set' badges when keys are present", async () => {
    mockFetchSequence([{ ok: true, status: 200, body: SNAPSHOT_KEYS_SET }]);
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <Routes>
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => {
      const setBadges = screen.getAllByText(/^set$/);
      // Both keys are configured.
      expect(setBadges.length).toBe(2);
    });
    // Total cap pre-fills.
    const totalCapInput = screen.getByPlaceholderText(/^50\.00$/);
    expect(totalCapInput).toHaveValue(50);
  });

  it("renders empty state and helpful placeholders when no keys are set", async () => {
    mockFetchSequence([{ ok: true, status: 200, body: SNAPSHOT_KEYS_UNSET }]);
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <Routes>
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(
        screen.getByPlaceholderText(/sk-ant-/)
      ).toBeInTheDocument();
    });
    expect(screen.queryByText(/^set$/)).not.toBeInTheDocument();
  });

  it("submits only changed cap fields + clears typed key after save", async () => {
    const fn = mockFetchSequence([
      { ok: true, status: 200, body: SNAPSHOT_KEYS_SET },
      { ok: true, status: 200, body: { ok: true } },
      { ok: true, status: 200, body: { ...SNAPSHOT_KEYS_SET, spend_cap_total_usd: 75 } },
    ]);
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <Routes>
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByDisplayValue("50")).toBeInTheDocument();
    });

    // Rotate the Anthropic key and bump the total cap.
    const keyInputs = screen.getAllByPlaceholderText(/leave empty to keep/i);
    expect(keyInputs).toHaveLength(2);
    const anthropicInput = keyInputs[0]; // declared first in JSX
    await user.type(anthropicInput, "sk-ant-rotated");
    const totalCap = screen.getByDisplayValue("50");
    await user.clear(totalCap);
    await user.type(totalCap, "75");

    await user.click(screen.getByRole("button", { name: /Save changes/i }));

    await waitFor(() => {
      expect(fn).toHaveBeenCalledWith(
        "/api/settings/update",
        expect.objectContaining({ method: "POST" })
      );
    });
    const postCall = fn.mock.calls.find(
      (c) => (c[0] as string) === "/api/settings/update"
    );
    expect(postCall).toBeDefined();
    const body = JSON.parse((postCall![1] as RequestInit).body as string);
    expect(body.anthropic_api_key).toBe("sk-ant-rotated");
    expect(body.spend_cap_total_usd).toBe(75);
    expect(body.google_api_key).toBeNull();
  });

  it("surfaces a server error when /update fails", async () => {
    mockFetchSequence([
      { ok: true, status: 200, body: SNAPSHOT_KEYS_SET },
      { ok: false, status: 422, body: { detail: "out of range" } },
    ]);
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <Routes>
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByDisplayValue("50")).toBeInTheDocument();
    });
    const totalCap = screen.getByDisplayValue("50");
    await user.clear(totalCap);
    await user.type(totalCap, "0.5");
    await user.click(screen.getByRole("button", { name: /Save changes/i }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/out of range/);
    });
  });
});
