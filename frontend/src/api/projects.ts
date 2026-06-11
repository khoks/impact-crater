// Fetch wrappers around /api/projects (persistent) and /api/jobs (session).

import type { JobSnapshot } from "./jobs";

export interface SnapshotSummary {
  id: string;
  created_at: string;
  render_status: "pending" | "in_progress" | "success" | "failure" | "cancelled";
  has_render: boolean;
}

export interface ProjectSummary {
  id: string;
  name: string;
  brief: string;
  created_at: string;
  updated_at: string;
  snapshots: SnapshotSummary[];
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const r = await fetch("/api/projects");
  if (!r.ok) {
    throw new Error(`GET /api/projects → ${r.status}`);
  }
  const data: unknown = await r.json();
  return Array.isArray(data) ? (data as ProjectSummary[]) : [];
}

export async function listJobs(): Promise<JobSnapshot[]> {
  const r = await fetch("/api/jobs");
  if (!r.ok) {
    throw new Error(`GET /api/jobs → ${r.status}`);
  }
  const data: unknown = await r.json();
  return Array.isArray(data) ? (data as JobSnapshot[]) : [];
}
