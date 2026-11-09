// GET /api/audit — every publish attempt across projects, newest first (S-3.3.9).

import { apiFetch } from "./client";

export type RenderCheck = "match" | "changed" | "missing" | "unrecorded";

export interface AuditRow {
  id: number;
  published_at: string;
  project_id: string;
  project_name: string;
  snapshot_id: string;
  platform: string;
  dry_run: boolean;
  visibility: string;
  external_id: string;
  external_url: string;
  response_code: number | null;
  approval_token: string;
  render_content_hash: string;
  render_check: RenderCheck;
}

export interface AuditPage {
  items: AuditRow[];
  total: number;
  limit: number;
  offset: number;
}

export async function fetchAuditPage(limit: number, offset: number): Promise<AuditPage> {
  const r = await apiFetch(`/api/audit?limit=${limit}&offset=${offset}`);
  if (!r.ok) {
    throw new Error(`GET /api/audit → ${r.status}`);
  }
  return (await r.json()) as AuditPage;
}
