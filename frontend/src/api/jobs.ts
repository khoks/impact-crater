// Wrappers around /api/jobs/*.

export interface SubmitJobRequest {
  media_paths: string[];
  brief: string;
  target_duration: number;
  audio_path: string;
  mode?: "standard" | "music_video";
  section_to_media_nl?: string | null;
  project_id?: string;
}

export interface SubmitJobResponse {
  job_id: string;
  project_id: string;
  state: string;
  submitted_at: string;
  websocket_url: string;
}

export interface StageProgress {
  stage: string;
  state: "pending" | "running" | "completed" | "failed";
  started_at: string | null;
  completed_at: string | null;
  detail: string;
}

export interface JobSnapshot {
  job_id: string;
  project_id: string;
  snapshot_id: string | null;
  state: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  submitted_at: string;
  started_at: string | null;
  completed_at: string | null;
  stages: StageProgress[];
  cost_by_tier_usd: Record<string, number>;
  cost_by_provider_usd: Record<string, number>;
  total_cost_usd: number;
  cache_hits: number;
  cache_misses: number;
  render_path: string | null;
  failure_reason: string | null;
  correlation_id: string;
}

export type JobProgressEvent =
  | {
      type: "state";
      job_id: string;
      timestamp: string;
      payload: {
        state: JobSnapshot["state"];
        snapshot_id: string | null;
        failure_reason: string | null;
        render_path: string | null;
      };
    }
  | {
      type: "stage";
      job_id: string;
      timestamp: string;
      payload: {
        stage: string;
        state: StageProgress["state"];
        detail: string;
        started_at: string | null;
        completed_at: string | null;
      };
    }
  | {
      type: "llm_call";
      job_id: string;
      timestamp: string;
      payload: {
        operation: string;
        provider: string;
        tier: string;
        cost_usd: number;
        cache_hit: boolean;
        total_cost_usd: number;
        cost_by_tier_usd: Record<string, number>;
        cost_by_provider_usd: Record<string, number>;
      };
    }
  | {
      type: "render";
      job_id: string;
      timestamp: string;
      payload: { status: string; duration_ms: number; output_bytes: number };
    }
  | {
      type: "log";
      job_id: string;
      timestamp: string;
      payload: { message: string };
    };


export async function submitJob(req: SubmitJobRequest): Promise<SubmitJobResponse> {
  const r = await fetch("/api/jobs/submit", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
  });
  if (r.status !== 202) {
    const detail = await safeDetail(r);
    throw new Error(detail || `Submit failed: ${r.status}`);
  }
  return (await r.json()) as SubmitJobResponse;
}

export async function getJob(jobId: string): Promise<JobSnapshot> {
  const r = await fetch(`/api/jobs/${jobId}`);
  if (!r.ok) {
    throw new Error(`GET /api/jobs/${jobId} → ${r.status}`);
  }
  return (await r.json()) as JobSnapshot;
}

export interface CostPreviewRequest {
  media_count: number;
  target_duration_seconds: number;
  level_id?: string | null;
}

export interface CostPreviewResponse {
  estimated_cost_usd_low: number;
  estimated_cost_usd_high: number;
  cost_by_tier_usd: Record<string, number>;
  today_remaining_usd: number | null;
  fits_today_budget: boolean;
  blocking_reason: string | null;
}

export async function fetchCostPreview(
  req: CostPreviewRequest
): Promise<CostPreviewResponse> {
  const r = await fetch("/api/cost-preview", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!r.ok) {
    throw new Error(`POST /api/cost-preview → ${r.status}`);
  }
  return (await r.json()) as CostPreviewResponse;
}

export interface EffortLevel {
  id: string;
  label: string;
  photo_cap: number;
  video_cap: number;
  estimated_cost_usd_low: number;
  estimated_cost_usd_high: number;
  description: string;
  fits_today_budget: boolean;
}

export interface EffortLevelsResponse {
  levels: EffortLevel[];
  today_total_spent_usd: number;
  today_per_provider_spent_usd: Record<string, number>;
  cap_total_usd: number | null;
  cap_per_provider_usd: Record<string, number>;
  recommended_level_id: string | null;
}

export async function fetchEffortLevels(): Promise<EffortLevelsResponse> {
  const r = await fetch("/api/effort-levels");
  if (!r.ok) {
    throw new Error(`GET /api/effort-levels → ${r.status}`);
  }
  return (await r.json()) as EffortLevelsResponse;
}

async function safeDetail(r: Response): Promise<string> {
  try {
    const body = (await r.json()) as { detail?: unknown };
    return typeof body.detail === "string"
      ? body.detail
      : JSON.stringify(body.detail ?? body);
  } catch {
    return "";
  }
}


// ---- Refine (M6) ----

export interface RefineResponse {
  strategy: string;
  rationale: string;
  explanation: string | null;
  brief_addendum: string | null;
  new_arc_judgment: Record<string, unknown> | null;
  turns_used: number;
}

export async function postRefine(
  snapshotId: string,
  message: string
): Promise<RefineResponse> {
  const r = await fetch(`/api/snapshots/${snapshotId}/refine`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ refinement_message: message }),
  });
  if (!r.ok) {
    const detail = await safeDetail(r);
    throw new Error(detail || `Refine failed: ${r.status}`);
  }
  return (await r.json()) as RefineResponse;
}
