// Fetch wrappers around /api/setup/*.

export interface SetupStatus {
  setup_complete: boolean;
}

export type Provider = "anthropic" | "google";

export interface TestKeyResult {
  success: boolean;
  message: string;
}

export interface CompletePayload {
  anthropic_api_key: string;
  google_api_key: string;
  spend_cap_total_usd: number;
  spend_cap_anthropic_usd: number | null;
  spend_cap_google_usd: number | null;
  impact_crater_home_override: string | null;
}

export async function fetchSetupStatus(): Promise<SetupStatus> {
  const r = await fetch("/api/setup/status");
  if (!r.ok) {
    throw new Error(`GET /api/setup/status → ${r.status}`);
  }
  return (await r.json()) as SetupStatus;
}

export async function testKey(provider: Provider, key: string): Promise<TestKeyResult> {
  const r = await fetch("/api/setup/test-key", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ provider, key }),
  });
  if (!r.ok) {
    return { success: false, message: `Server returned ${r.status}` };
  }
  return (await r.json()) as TestKeyResult;
}

export async function completeSetup(payload: CompletePayload): Promise<void> {
  const r = await fetch("/api/setup/complete", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    let detail = `${r.status}`;
    try {
      const body = (await r.json()) as { detail?: string };
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(`Setup completion failed: ${detail}`);
  }
}
