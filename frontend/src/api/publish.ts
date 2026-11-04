// Wrappers around the publish API. M7 shipped YouTube only (ADR-0013);
// v1 adds Instagram + Facebook via the multi-platform connector framework.

import { apiFetch } from "./client";

export type Visibility = "private" | "unlisted" | "public";
export type Platform = "youtube" | "instagram" | "facebook";

export const ALL_PLATFORMS: Platform[] = ["youtube", "instagram", "facebook"];

export const PLATFORM_LABELS: Record<Platform, string> = {
  youtube: "YouTube",
  instagram: "Instagram",
  facebook: "Facebook",
};

// What each connector accepts (S-3.3.8), so the panel only offers what will work.
// Facebook's "unlisted" saves the video as a Page draft; first entry = default.
export const PLATFORM_VISIBILITIES: Record<Platform, Visibility[]> = {
  youtube: ["private", "unlisted", "public"],
  instagram: ["public"],
  facebook: ["unlisted", "public"],
};

// What a dry-run actually checks on each platform.
export const DRY_RUN_CHECKS: Record<Platform, string> = {
  youtube:
    "A dry-run checks the title, description and visibility and records the attempt in the audit log. It needs no YouTube credentials and uploads nothing.",
  instagram:
    "A dry-run checks the request and that your Instagram credentials are set, then records the attempt. It refuses until the credentials exist and posts nothing.",
  facebook:
    "A dry-run checks the request and that your Facebook Page credentials are set, then records the attempt. It refuses until the credentials exist and posts nothing.",
};

const DOCS_BASE = "https://github.com/khoks/impact-crater/blob/master/docs/connectors";

export function setupGuideUrl(platform: Platform): string {
  return `${DOCS_BASE}/${platform}-setup.md`;
}

export interface PublishDefaults {
  title: string;
  description: string;
}

export async function fetchPublishDefaults(snapshotId: string): Promise<PublishDefaults> {
  const r = await apiFetch(`/api/snapshots/${snapshotId}/publish-defaults`);
  if (!r.ok) {
    throw new Error(`GET /api/snapshots/${snapshotId}/publish-defaults → ${r.status}`);
  }
  return (await r.json()) as PublishDefaults;
}

export interface YouTubeStatusResponse {
  connected: boolean;
  user_handle: string | null;
}

export interface ConnectorStatus {
  platform: Platform;
  connected: boolean;
}

export interface AllConnectorsStatus {
  platforms: ConnectorStatus[];
  dry_run: boolean;
}

export interface PublishRequest {
  title: string;
  description?: string;
  tags?: string[];
  visibility?: Visibility;
  platform?: Platform;
}

export interface PublishResponse {
  external_id: string;
  external_url: string;
  visibility: Visibility;
  audit_token: string;
  platform: Platform;
  dry_run: boolean;
}

export async function fetchYouTubeStatus(): Promise<YouTubeStatusResponse> {
  const r = await apiFetch("/api/connectors/youtube/status");
  if (!r.ok) {
    throw new Error(`GET /api/connectors/youtube/status → ${r.status}`);
  }
  return (await r.json()) as YouTubeStatusResponse;
}

export async function fetchAllConnectorsStatus(): Promise<AllConnectorsStatus> {
  const r = await apiFetch("/api/connectors/status");
  if (!r.ok) {
    throw new Error(`GET /api/connectors/status → ${r.status}`);
  }
  return (await r.json()) as AllConnectorsStatus;
}

export async function publishSnapshot(
  snapshotId: string,
  req: PublishRequest
): Promise<PublishResponse> {
  const r = await apiFetch(`/api/snapshots/${snapshotId}/publish`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!r.ok) {
    const detail = await safeDetail(r);
    // 401 = ConnectorAuthError. Surface a more actionable message.
    if (r.status === 401) {
      throw new Error(
        detail || "This platform isn't connected. Set its credentials as described in its setup guide."
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
