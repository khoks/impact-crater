// Wrappers around the publish API per ADR-0013 (E-2.8 / M7).

export type Visibility = "private" | "unlisted" | "public";

export interface YouTubeStatusResponse {
  connected: boolean;
  user_handle: string | null;
}

export interface PublishRequest {
  title: string;
  description?: string;
  tags?: string[];
  visibility?: Visibility;
}

export interface PublishResponse {
  external_id: string;
  external_url: string;
  visibility: Visibility;
  audit_token: string;
}

export async function fetchYouTubeStatus(): Promise<YouTubeStatusResponse> {
  const r = await fetch("/api/connectors/youtube/status");
  if (!r.ok) {
    throw new Error(`GET /api/connectors/youtube/status → ${r.status}`);
  }
  return (await r.json()) as YouTubeStatusResponse;
}

export async function publishSnapshot(
  snapshotId: string,
  req: PublishRequest
): Promise<PublishResponse> {
  const r = await fetch(`/api/snapshots/${snapshotId}/publish`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!r.ok) {
    const detail = await safeDetail(r);
    // 401 = ConnectorAuthError. Surface a more actionable message.
    if (r.status === 401) {
      throw new Error(
        detail || "YouTube isn't connected. Bind a Google Cloud OAuth client per ADR-0013."
      );
    }
    throw new Error(detail || `Publish failed: ${r.status}`);
  }
  return (await r.json()) as PublishResponse;
}

async function safeDetail(r: Response): Promise<string> {
  try {
    const body = (await r.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (body.detail && typeof body.detail === "object") {
      const d = body.detail as { message?: string; suggested_action?: string };
      const parts = [d.message, d.suggested_action].filter(Boolean);
      if (parts.length > 0) return parts.join(" — ");
    }
    return JSON.stringify(body.detail ?? body);
  } catch {
    return "";
  }
}
