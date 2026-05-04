// Thin fetch wrappers around /api/setup/*. The full surface (test-key,
// complete) lands in S-2.1.5; M0 only exercises /status.

export interface SetupStatus {
  setup_complete: boolean;
}

export async function fetchSetupStatus(): Promise<SetupStatus> {
  const r = await fetch("/api/setup/status");
  if (!r.ok) {
    throw new Error(`GET /api/setup/status → ${r.status}`);
  }
  return (await r.json()) as SetupStatus;
}
