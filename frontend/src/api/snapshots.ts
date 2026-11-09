// GET /api/snapshots/{id} — one snapshot's place in the refine chain and its
// publish history (S-3.5.5).

import { apiFetch } from "./client";

export interface SnapshotPublish {
  platform: string;
  dry_run: boolean;
  external_url: string;
  published_at: string;
}

export interface SnapshotDetail {
  id: string;
  project_id: string;
  project_name: string;
  parent_snapshot_id: string | null;
  children: string[];
  created_at: string;
  render_status: string;
  has_render: boolean;
  refinement_message: string | null;
  refinement_interpretation: string | null;
  publishes: SnapshotPublish[];
}

export async function fetchSnapshot(snapshotId: string): Promise<SnapshotDetail> {
  const r = await apiFetch(`/api/snapshots/${snapshotId}`);
  if (!r.ok) {
    throw new Error(`GET /api/snapshots/${snapshotId} → ${r.status}`);
  }
  return (await r.json()) as SnapshotDetail;
}
