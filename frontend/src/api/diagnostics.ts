// Wrappers around the A-023 feedback-loop endpoints:
//   GET  /api/snapshots/:id/diagnostics
//   POST /api/feedback

export interface DiagnosticDecision {
  content_hash?: string;
  scene_index?: number | null;
  ref?: string;
  decision?: string;
  reason?: string | null;
  caption?: string | null;
  quality_score?: number | null;
  narrative_relevance?: number | null;
  role?: string;
  placement_position?: number;
  position?: number;
  intended_duration_ms?: number;
  notes?: string;
  kind?: string;
  aspect_ratio_action?: string;
  person_id?: string;
  appearance_count?: number;
  distinct_days?: number;
  distinct_locations?: number;
  recurrence_breadth?: number;
  thumb_url?: string | null;
  extra?: Record<string, unknown>;
}

export interface DiagnosticPhase {
  phase: string;
  title: string;
  description: string;
  summary: Record<string, unknown>;
  decisions: DiagnosticDecision[];
}

export interface Diagnostics {
  schema_version: number;
  project_id: string;
  snapshot_id: string;
  phases: DiagnosticPhase[];
}

export async function fetchDiagnostics(snapshotId: string): Promise<Diagnostics | null> {
  const r = await fetch(`/api/snapshots/${snapshotId}/diagnostics`);
  if (r.status === 404) return null; // pre-feature snapshot
  if (!r.ok) throw new Error(`GET diagnostics → ${r.status}`);
  return (await r.json()) as Diagnostics;
}

export type Verdict = "correct" | "incorrect" | "different";

export interface FeedbackPayload {
  phase: string;
  verdict: Verdict;
  job_id?: string;
  project_id?: string;
  snapshot_id?: string;
  decision_ref?: string;
  content_hash?: string;
  comment?: string;
  context?: Record<string, unknown>;
  screenshot_data_url?: string;
}

// Capture the whole page as a PNG data URL (best-effort). Excludes any node
// tagged data-ic-skip-capture (the feedback modal itself). Returns undefined
// if capture fails — feedback submission must never depend on it.
export async function capturePageScreenshot(): Promise<string | undefined> {
  try {
    const { toPng } = await import("html-to-image");
    return await toPng(document.body, {
      cacheBust: true,
      pixelRatio: 1,
      filter: (node) =>
        !(node instanceof HTMLElement && node.dataset.icSkipCapture === "true"),
    });
  } catch {
    return undefined;
  }
}

export interface JobDiagnosticEvent {
  phase: string;
  doc: DiagnosticPhase;
}

export async function submitFeedback(p: FeedbackPayload): Promise<{ id: number }> {
  const r = await fetch("/api/feedback", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(p),
  });
  if (r.status !== 201) {
    let detail = `Feedback failed: ${r.status}`;
    try {
      const body = (await r.json()) as { detail?: unknown };
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return (await r.json()) as { id: number };
}
