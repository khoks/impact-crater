import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

function okJson(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as unknown as Response;
}

describe("apiFetch", () => {
  it("attaches the token from the page's meta tag", async () => {
    const fn = vi.fn(async () => okJson({}));
    vi.stubGlobal("fetch", fn as unknown as typeof fetch);
    const { apiFetch } = await import("../api/client");

    await apiFetch("/api/settings/update", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: "{}",
    });

    expect(fn).toHaveBeenCalledTimes(1);
    const [url, init] = fn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/settings/update");
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer test-token");
    expect(headers.get("content-type")).toBe("application/json");
  });

  it("asks /api/session once when the page has no meta tag", async () => {
    const meta = document.querySelector('meta[name="impact-crater-api-token"]');
    meta?.remove();
    const fn = vi.fn(async (url: string, _init?: RequestInit) =>
      url === "/api/session" ? okJson({ token: "from-session" }) : okJson({})
    );
    vi.stubGlobal("fetch", fn as unknown as typeof fetch);
    const { apiFetch } = await import("../api/client");

    await apiFetch("/api/projects");
    await apiFetch("/api/jobs");

    const urls = fn.mock.calls.map((c) => c[0]);
    expect(urls).toEqual(["/api/session", "/api/projects", "/api/jobs"]);
    const init = fn.mock.calls[2][1] as unknown as RequestInit;
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer from-session");
    if (meta) document.head.appendChild(meta);
  });
});
