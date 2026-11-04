// Every /api call goes through apiFetch so it carries the install's API token
// (S-3.11.3). The backend serves the page with the token in a meta tag; under
// the Vite dev server the page asks the loopback-only /api/session instead.

export const TOKEN_META_NAME = "impact-crater-api-token";

let tokenPromise: Promise<string> | null = null;

export function apiToken(): Promise<string> {
  if (tokenPromise === null) {
    const meta = document.querySelector<HTMLMetaElement>(`meta[name="${TOKEN_META_NAME}"]`);
    tokenPromise = meta?.content ? Promise.resolve(meta.content) : fetchSessionToken();
  }
  return tokenPromise;
}

async function fetchSessionToken(): Promise<string> {
  const r = await fetch("/api/session");
  if (!r.ok) {
    tokenPromise = null;
    throw new Error(`GET /api/session → ${r.status}`);
  }
  return ((await r.json()) as { token: string }).token;
}

export async function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const token = await apiToken();
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return fetch(input, { ...init, headers });
}
