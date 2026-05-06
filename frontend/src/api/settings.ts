// Wrappers around /api/settings/*.

export interface SettingsSnapshot {
  has_anthropic_key: boolean;
  has_google_key: boolean;
  spend_cap_total_usd: number | null;
  spend_cap_anthropic_usd: number | null;
  spend_cap_google_usd: number | null;
  today_total_spent_usd: number;
  today_per_provider_spent_usd: Record<string, number>;
}

export interface SettingsUpdate {
  anthropic_api_key?: string | null;
  google_api_key?: string | null;
  spend_cap_total_usd?: number | null;
  spend_cap_anthropic_usd?: number | null;
  spend_cap_google_usd?: number | null;
}

export async function fetchSettingsSnapshot(): Promise<SettingsSnapshot> {
  const r = await fetch("/api/settings/snapshot");
  if (!r.ok) {
    throw new Error(`GET /api/settings/snapshot → ${r.status}`);
  }
  return (await r.json()) as SettingsSnapshot;
}

export async function updateSettings(update: SettingsUpdate): Promise<void> {
  const r = await fetch("/api/settings/update", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(update),
  });
  if (!r.ok) {
    let detail = `${r.status}`;
    try {
      const body = (await r.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(`Settings update failed: ${detail}`);
  }
}
