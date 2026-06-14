// Wrappers for the developer tracker pages (A-024):
//   feedback tracker  → /api/feedback (list / detail / patch)
//   workplan tracker  → /api/workplan (tree / patch override / overrides)

export type Verdict = "correct" | "incorrect" | "different";
export type FeedbackStatus = "new" | "triaged" | "addressed" | "dismissed";
export type Priority = "P0" | "P1" | "P2" | "P3";

export interface FeedbackItem {
  id: number;
  created_at: string;
  job_id: string | null;
  project_id: string | null;
  snapshot_id: string | null;
  phase: string;
  decision_ref: string | null;
  content_hash: string | null;
  verdict: Verdict;
  comment: string | null;
  status: FeedbackStatus;
  priority: Priority;
  has_screenshot: boolean;
}

export interface FeedbackDetail extends FeedbackItem {
  context: Record<string, unknown> | null;
  screenshot_url: string | null;
  diagnostics_url: string | null;
}

export async function listFeedback(statusFilter?: string): Promise<FeedbackItem[]> {
  const qs = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : "";
  const r = await fetch(`/api/feedback${qs}`);
  if (!r.ok) throw new Error(`GET /api/feedback → ${r.status}`);
  const data: unknown = await r.json();
  return Array.isArray(data) ? (data as FeedbackItem[]) : [];
}

export async function getFeedbackDetail(id: number): Promise<FeedbackDetail> {
  const r = await fetch(`/api/feedback/${id}`);
  if (!r.ok) throw new Error(`GET /api/feedback/${id} → ${r.status}`);
  return (await r.json()) as FeedbackDetail;
}

export async function patchFeedback(
  id: number,
  patch: { status?: FeedbackStatus; priority?: Priority }
): Promise<FeedbackItem> {
  const r = await fetch(`/api/feedback/${id}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(`PATCH /api/feedback/${id} → ${r.status}`);
  return (await r.json()) as FeedbackItem;
}

// ---- Workplan ----------------------------------------------------------

export interface WorkItem {
  id: string;
  title: string;
  type: "initiative" | "epic" | "story" | "task";
  status: string;
  phase: string;
  priority: Priority;
  markdown_priority: Priority;
  priority_overridden: boolean;
  parent: string | null;
  updated: string | null;
  tags: string[];
  override_note: string | null;
}

export interface Workplan {
  items: WorkItem[];
  available: boolean;
  counts_by_status: Record<string, number>;
  counts_by_phase: Record<string, number>;
}

export async function fetchWorkplan(): Promise<Workplan> {
  const r = await fetch("/api/workplan");
  if (!r.ok) throw new Error(`GET /api/workplan → ${r.status}`);
  return (await r.json()) as Workplan;
}

export async function patchWorkplanItem(
  itemId: string,
  patch: { priority?: Priority; note?: string }
): Promise<void> {
  const r = await fetch(`/api/workplan/${encodeURIComponent(itemId)}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(`PATCH /api/workplan/${itemId} → ${r.status}`);
}
