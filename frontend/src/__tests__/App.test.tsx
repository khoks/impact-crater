import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import App from "../App";
import { useSetupStore } from "../stores/setupStore";

// fetch is jsdom-default-undefined; provide a stub per-test.
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
  // Reset Zustand store state between tests.
  useSetupStore.setState({ status: "unknown" });
  vi.unstubAllGlobals();
});

describe("App", () => {
  it("shows loading then routes to /setup when setup is incomplete", async () => {
    mockFetch({ setup_complete: false });
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Welcome to Impact Crater/i)).toBeInTheDocument();
    });
  });

  it("shows loading then routes to /dashboard when setup is complete", async () => {
    mockFetch({ setup_complete: true });
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/No projects yet/i)).toBeInTheDocument();
    });
  });
});
