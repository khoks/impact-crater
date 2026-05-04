import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import Setup from "../routes/Setup";

interface FetchExpectation {
  url: string;
  status?: number;
  body: unknown;
}

function mockFetchSequence(expectations: FetchExpectation[]): void {
  let i = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      const expected = expectations[i++];
      expect(expected, `unexpected fetch #${i} → ${url}`).toBeDefined();
      expect(url).toContain(expected.url);
      const status = expected.status ?? 200;
      return {
        ok: status >= 200 && status < 300,
        status,
        json: async () => expected.body,
      };
    }) as unknown as typeof fetch
  );
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("Setup wizard", () => {
  it("starts on Welcome (step 1 of 6) with Back disabled", () => {
    mockFetchSequence([]);
    render(
      <MemoryRouter>
        <Setup />
      </MemoryRouter>
    );
    expect(screen.getByText(/Step 1 of 6/i)).toBeInTheDocument();
    expect(screen.getByText(/Welcome/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /back/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /next/i })).toBeEnabled();
  });

  it("advances to step 2 (Anthropic key) and shows Test button", async () => {
    const user = userEvent.setup();
    mockFetchSequence([]);
    render(
      <MemoryRouter>
        <Setup />
      </MemoryRouter>
    );
    await user.click(screen.getByRole("button", { name: /next/i }));
    expect(screen.getByText(/Step 2 of 6/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/anthropic api key/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /test/i })).toBeInTheDocument();
  });

  it("Next is disabled on Anthropic step until key is entered", async () => {
    const user = userEvent.setup();
    mockFetchSequence([]);
    render(
      <MemoryRouter>
        <Setup />
      </MemoryRouter>
    );
    await user.click(screen.getByRole("button", { name: /next/i }));
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
    await user.type(screen.getByLabelText(/anthropic api key/i), "sk-ant-x");
    expect(screen.getByRole("button", { name: /next/i })).toBeEnabled();
  });

  it("Test button calls /api/setup/test-key and shows the response", async () => {
    const user = userEvent.setup();
    mockFetchSequence([
      {
        url: "/api/setup/test-key",
        body: { success: true, message: "Anthropic key accepted." },
      },
    ]);
    render(
      <MemoryRouter>
        <Setup />
      </MemoryRouter>
    );
    await user.click(screen.getByRole("button", { name: /next/i }));
    await user.type(screen.getByLabelText(/anthropic api key/i), "sk-ant-x");
    await user.click(screen.getByRole("button", { name: /test/i }));
    expect(await screen.findByText(/Anthropic key accepted/i)).toBeInTheDocument();
  });
});
