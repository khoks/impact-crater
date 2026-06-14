// In-job progress view — opens a WS to /api/jobs/ws/:job_id and renders
// stage-by-stage progress, project header, live spend split, and a
// cancel button. On terminal `succeeded` → routes to /jobs/:job_id/preview;
// on `failed` → renders the failure detail.
//
// Design note: the WS pushes per-event updates which can be hundreds per
// minute during Stage 2. We compute display values from the snapshot
// (rather than maintaining duplicate state) so React renders are cheap
// and a "last updated 2s ago" badge gives the user a liveness signal.

import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  cancelJob,
  getJob,
  type JobProgressEvent,
  type JobSnapshot,
  type StageProgress,
} from "../api/jobs";
import { DiagnosticsView } from "../components/DiagnosticsPanel";
import type { DiagnosticPhase } from "../api/diagnostics";

const STAGE_LABELS: Record<string, string> = {
  stage_1_ingest: "Ingest",
  stage_2_bulk_ops: "Bulk ops",
  stage_3_metadata: "Rich metadata",
  stage_4_prefilter: "Pre-filter",
  stage_5_judge: "Narrative judge",
  stage_6_plan: "Plan compile",
  stage_7_render: "Render",
};

const STAGE_HINTS: Record<string, string> = {
  stage_1_ingest: "Hash + EXIF + scene-detect every photo and video",
  stage_2_bulk_ops: "4 LLM ops per asset: caption + 2 quality scores + embedding",
  stage_3_metadata: "Rich metadata extraction (people, location, mood, objects)",
  stage_4_prefilter: "Deterministic dedup + quality floor + cluster sampling",
  stage_5_judge: "Tier-L Opus picks the narrative arc — single big call",
  stage_6_plan: "Compile the arc into a render plan; orchestrator second-guess",
  stage_7_render: "ffmpeg: pre-render every clip, concat, mux audio, finalize",
};

const STAGE_ORDER = [
  "stage_1_ingest",
  "stage_2_bulk_ops",
  "stage_3_metadata",
  "stage_4_prefilter",
  "stage_5_judge",
  "stage_6_plan",
  "stage_7_render",
];

const TIER_LABELS: Record<string, string> = {
  S: "Tier-S — Google Flash captions + scores",
  M: "Tier-M — Anthropic Sonnet metadata",
  L: "Tier-L — Anthropic Opus narrative judge",
  embedding: "Embeddings — Gemini text-embedding",
};

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Anthropic",
  google: "Google",
};

export default function JobInProgress() {
  const { job_id } = useParams<{ job_id: string }>();
  const navigate = useNavigate();
  const [snapshot, setSnapshot] = useState<JobSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<number>(Date.now());
  const [now, setNow] = useState<number>(Date.now());
  const [briefOpen, setBriefOpen] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  // Live per-phase diagnostics streamed as each phase completes (A-023).
  const [livePhases, setLivePhases] = useState<Record<string, DiagnosticPhase>>({});
  const wsRef = useRef<WebSocket | null>(null);

  // Tick the wall clock every second so elapsed-time / "updated Xs ago"
  // refresh smoothly without depending on WS messages.
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!job_id) return;
    let cancelled = false;

    getJob(job_id)
      .then((s) => {
        if (!cancelled) {
          setSnapshot(s);
          setLastUpdate(Date.now());
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${window.location.host}/api/jobs/ws/${job_id}`);
    wsRef.current = ws;

    ws.onmessage = (msg) => {
      let event: JobProgressEvent;
      try {
        event = JSON.parse(msg.data) as JobProgressEvent;
      } catch {
        return;
      }
      if (event.type === "diagnostics") {
        const doc = event.payload.doc as unknown as DiagnosticPhase;
        if (doc?.phase) {
          setLivePhases((prev) => ({ ...prev, [doc.phase]: doc }));
        }
        setLastUpdate(Date.now());
        return;
      }
      setSnapshot((prev) => applyEvent(prev, event));
      setLastUpdate(Date.now());
      if (event.type === "state" && event.payload.state === "succeeded") {
        // Live diagnostics streamed during the run; the preview page shows
        // the same decisions (persisted) + feedback, so navigate straight there.
        navigate(`/jobs/${job_id}/preview`, { replace: true });
      }
    };

    ws.onerror = () => {
      if (!cancelled) setError("WebSocket connection error");
    };

    return () => {
      cancelled = true;
      ws.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job_id]);

  // Stage-2 expected calls = 4 ops/asset (caption + 2 scores + embed) +
  // a 5th implicit caption-for-embedding via Gemini Flash. The router
  // counts each as one cache event, so 4× is the right denominator
  // for the user-facing progress bar.
  const stage2Expected = useMemo(() => {
    if (!snapshot || snapshot.media_count <= 0) return 0;
    return snapshot.media_count * 4;
  }, [snapshot]);

  async function onCancel() {
    if (!job_id || !snapshot) return;
    if (
      !confirm(
        `Cancel this job? You'll keep the cached LLM results (next run will resume from where this stops), but the partial progress this job has made will be lost.`
      )
    ) {
      return;
    }
    setCancelling(true);
    setCancelError(null);
    try {
      await cancelJob(job_id);
    } catch (err) {
      setCancelError(err instanceof Error ? err.message : String(err));
    } finally {
      setCancelling(false);
    }
  }

  if (!job_id) {
    return <p className="px-6 py-12 text-slate-500">No job_id in URL.</p>;
  }

  if (error && !snapshot) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-12">
        <h1 className="text-2xl font-semibold text-slate-900">Job error</h1>
        <p className="mt-3 text-red-600">{error}</p>
        <Link to="/dashboard" className="mt-6 inline-block text-sm text-slate-600 hover:text-slate-900">
          ← Back to dashboard
        </Link>
      </main>
    );
  }

  if (!snapshot) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-12">
        <p className="text-slate-500">Loading job…</p>
      </main>
    );
  }

  if (snapshot.state === "failed" || snapshot.state === "cancelled") {
    return (
      <main className="mx-auto max-w-3xl px-6 py-12">
        <h1 className="text-2xl font-semibold text-slate-900">
          Job {snapshot.state}
        </h1>
        <p className="mt-3 rounded bg-red-50 px-4 py-3 text-sm text-red-700">
          {snapshot.failure_reason ?? "(no reason recorded)"}
        </p>
        <p className="mt-3 text-xs text-slate-500">
          Spent ${snapshot.total_cost_usd.toFixed(4)} · cache{" "}
          {snapshot.cache_hits}/{snapshot.cache_hits + snapshot.cache_misses} hits.
          The LLM cache is preserved on disk; re-running this job will resume
          from where it stopped.
        </p>
        <Link
          to="/dashboard"
          className="mt-6 inline-block text-sm text-slate-600 hover:text-slate-900"
        >
          ← Back to dashboard
        </Link>
      </main>
    );
  }

  const headerTitle = snapshot.project_name?.trim() || "Job in progress";
  const elapsedS = snapshot.started_at
    ? Math.max(0, Math.floor((now - new Date(snapshot.started_at).getTime()) / 1000))
    : 0;
  const sinceUpdateS = Math.max(0, Math.floor((now - lastUpdate) / 1000));
  const totalCalls = snapshot.cache_hits + snapshot.cache_misses;
  const cacheRate =
    totalCalls > 0 ? snapshot.cache_hits / totalCalls : 0;

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <header className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-2xl font-semibold text-slate-900">
            {headerTitle}
          </h1>
          <p className="mt-1 text-xs text-slate-500">
            <span className="font-mono">{snapshot.project_id}</span>
            {snapshot.media_count > 0 && (
              <>
                {" · "}
                {snapshot.media_count} media · {snapshot.target_duration_seconds}s
                target
              </>
            )}
          </p>
          {snapshot.brief && (
            <button
              type="button"
              onClick={() => setBriefOpen((v) => !v)}
              className="mt-1 text-xs text-slate-500 underline-offset-2 hover:text-slate-900 hover:underline"
            >
              {briefOpen ? "Hide brief" : "Show brief"}
            </button>
          )}
          {briefOpen && snapshot.brief && (
            <p className="mt-2 max-w-2xl whitespace-pre-wrap rounded border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700">
              {snapshot.brief}
            </p>
          )}
        </div>
        <div className="flex flex-col items-end gap-2">
          <span className={statePillClass(snapshot.state)}>{snapshot.state}</span>
          <button
            type="button"
            onClick={onCancel}
            disabled={cancelling}
            className="rounded border border-red-300 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {cancelling ? "Cancelling…" : "Cancel job"}
          </button>
        </div>
      </header>

      {cancelError && (
        <p role="alert" className="mt-2 rounded bg-red-50 px-3 py-2 text-xs text-red-700">
          {cancelError}
        </p>
      )}

      <p className="mt-2 text-xs text-slate-400">
        Elapsed {formatDuration(elapsedS)} ·{" "}
        <LiveDot ageSeconds={sinceUpdateS} /> updated {sinceUpdateS}s ago
      </p>

      <section className="mt-8 grid gap-4 lg:grid-cols-[2fr,1fr]">
        <ol className="space-y-3 rounded border border-slate-200 bg-white p-4">
          {STAGE_ORDER.map((stageName) => {
            const row = snapshot.stages.find((s) => s.stage === stageName);
            return (
              <StageRow
                key={stageName}
                label={STAGE_LABELS[stageName] ?? stageName}
                hint={STAGE_HINTS[stageName] ?? ""}
                stage={stageName}
                row={row}
                stage2Expected={stage2Expected}
                cacheHits={snapshot.cache_hits}
                cacheMisses={snapshot.cache_misses}
                now={now}
              />
            );
          })}
        </ol>

        <aside className="space-y-3">
          <div className="rounded border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-700">Live spend</h2>
            <p className="mt-1 text-2xl font-semibold">
              ${snapshot.total_cost_usd.toFixed(2)}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {totalCalls > 0 && (
                <>
                  {snapshot.cache_hits} hit{snapshot.cache_hits === 1 ? "" : "s"} ·{" "}
                  {snapshot.cache_misses} miss
                  {snapshot.cache_misses === 1 ? "" : "es"} ·{" "}
                  {(cacheRate * 100).toFixed(0)}% cached
                </>
              )}
            </p>
            {Object.keys(snapshot.cost_by_tier_usd).length > 0 && (
              <>
                <h3 className="mt-3 text-xs font-medium text-slate-600">By tier</h3>
                <dl className="mt-1 space-y-1 text-xs text-slate-600">
                  {Object.entries(snapshot.cost_by_tier_usd).map(([tier, cost]) => (
                    <div key={tier} className="flex justify-between gap-2">
                      <dt className="truncate" title={TIER_LABELS[tier] ?? tier}>
                        {TIER_LABELS[tier] ?? tier}
                      </dt>
                      <dd className="font-mono">${cost.toFixed(4)}</dd>
                    </div>
                  ))}
                </dl>
              </>
            )}
            {Object.keys(snapshot.cost_by_provider_usd).length > 0 && (
              <>
                <h3 className="mt-3 text-xs font-medium text-slate-600">By provider</h3>
                <dl className="mt-1 space-y-1 text-xs text-slate-600">
                  {Object.entries(snapshot.cost_by_provider_usd).map(([prov, cost]) => (
                    <div key={prov} className="flex justify-between gap-2">
                      <dt>{PROVIDER_LABELS[prov] ?? prov}</dt>
                      <dd className="font-mono">${cost.toFixed(4)}</dd>
                    </div>
                  ))}
                </dl>
              </>
            )}
          </div>
        </aside>
      </section>

      {Object.keys(livePhases).length > 0 && (
        <section className="mt-6 rounded border border-slate-200 bg-slate-50 p-4">
          <h2 className="text-sm font-semibold text-slate-700">
            Decisions so far
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Each phase's decisions appear here as it finishes — open one to see
            what was kept/dropped and why, and click “Feedback” on anything that
            looks wrong. Your input is saved for Claude to act on later.
          </p>
          <DiagnosticsView
            phases={LIVE_PHASE_ORDER.flatMap((p) =>
              livePhases[p] ? [livePhases[p]] : []
            )}
            jobId={job_id}
            projectId={snapshot.project_id}
            snapshotId={snapshot.snapshot_id ?? undefined}
          />
        </section>
      )}
    </main>
  );
}

const LIVE_PHASE_ORDER = [
  "stage_4_prefilter",
  "cast",
  "stage_5_judge",
  "stage_6_plan",
];

// -- Stage row -----------------------------------------------------------

function StageRow({
  label,
  hint,
  stage,
  row,
  stage2Expected,
  cacheHits,
  cacheMisses,
  now,
}: {
  label: string;
  hint: string;
  stage: string;
  row: StageProgress | undefined;
  stage2Expected: number;
  cacheHits: number;
  cacheMisses: number;
  now: number;
}) {
  const state = row?.state ?? "pending";
  const detail = row?.detail ?? "";

  const icon =
    state === "completed" ? "✓" : state === "failed" ? "✗" : state === "running" ? "…" : "·";
  const iconColor =
    state === "completed"
      ? "text-emerald-600"
      : state === "failed"
        ? "text-red-600"
        : state === "running"
          ? "text-amber-600"
          : "text-slate-300";

  // Per-stage progress for the running stage. Stage 2 is computable;
  // others show their detail string.
  let progressText: string | null = null;
  let progressPct: number | null = null;
  if (state === "running" && stage === "stage_2_bulk_ops" && stage2Expected > 0) {
    const done = cacheHits + cacheMisses;
    progressPct = Math.min(100, Math.round((done / stage2Expected) * 100));
    progressText = `${done.toLocaleString()}/${stage2Expected.toLocaleString()} ops · ${progressPct}%`;
  }

  // Elapsed for running / total for completed.
  let timing = "";
  if (state === "running" && row?.started_at) {
    const elapsed = Math.max(0, Math.floor((now - new Date(row.started_at).getTime()) / 1000));
    timing = `${formatDuration(elapsed)}`;
  } else if (state === "completed" && row?.started_at && row?.completed_at) {
    const dur = Math.max(
      0,
      Math.floor(
        (new Date(row.completed_at).getTime() - new Date(row.started_at).getTime()) / 1000
      )
    );
    timing = `${formatDuration(dur)}`;
  }

  return (
    <li className="flex flex-col gap-1">
      <div className="flex items-baseline gap-3 text-sm">
        <span className={`w-4 text-center font-mono ${iconColor}`}>{icon}</span>
        <span className="flex-1 text-slate-800" title={hint}>
          {label}
        </span>
        {detail && state !== "running" && (
          <span className="text-xs text-slate-500">{detail}</span>
        )}
        {timing && (
          <span className="text-xs font-mono text-slate-400">{timing}</span>
        )}
      </div>
      {state === "running" && (progressText || detail) && (
        <div className="ml-7 flex items-center gap-2">
          <span className="text-xs text-slate-500">
            {progressText ?? detail}
          </span>
        </div>
      )}
      {progressPct !== null && state === "running" && (
        <div className="ml-7 h-1 overflow-hidden rounded bg-slate-100">
          <div
            className="h-full bg-amber-400 transition-[width] duration-300"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      )}
    </li>
  );
}

// -- Helpers -------------------------------------------------------------

function statePillClass(state: string): string {
  const base = "rounded px-2 py-1 text-xs font-mono";
  switch (state) {
    case "running":
      return `${base} bg-amber-100 text-amber-800`;
    case "succeeded":
      return `${base} bg-emerald-100 text-emerald-800`;
    case "failed":
      return `${base} bg-red-100 text-red-800`;
    case "cancelled":
      return `${base} bg-slate-200 text-slate-700`;
    default:
      return `${base} bg-slate-100 text-slate-600`;
  }
}

function LiveDot({ ageSeconds }: { ageSeconds: number }) {
  const fresh = ageSeconds <= 5;
  return (
    <span
      className={
        "inline-block h-2 w-2 rounded-full align-middle " +
        (fresh ? "bg-emerald-400 animate-pulse" : "bg-slate-300")
      }
      aria-hidden
    />
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return `${m}m ${s.toString().padStart(2, "0")}s`;
  const h = Math.floor(m / 60);
  const mm = m % 60;
  return `${h}h ${mm.toString().padStart(2, "0")}m`;
}

function applyEvent(prev: JobSnapshot | null, event: JobProgressEvent): JobSnapshot | null {
  if (prev === null) return prev;
  switch (event.type) {
    case "state":
      return {
        ...prev,
        state: event.payload.state,
        snapshot_id: event.payload.snapshot_id,
        failure_reason: event.payload.failure_reason,
        render_path: event.payload.render_path,
      };
    case "stage": {
      const stages = prev.stages.map((s) =>
        s.stage === event.payload.stage
          ? {
              ...s,
              state: event.payload.state,
              detail: event.payload.detail,
              started_at: event.payload.started_at,
              completed_at: event.payload.completed_at,
            }
          : s
      );
      return { ...prev, stages };
    }
    case "llm_call":
      return {
        ...prev,
        total_cost_usd: event.payload.total_cost_usd,
        cost_by_tier_usd: event.payload.cost_by_tier_usd,
        cost_by_provider_usd: event.payload.cost_by_provider_usd,
        cache_hits: prev.cache_hits + (event.payload.cache_hit ? 1 : 0),
        cache_misses: prev.cache_misses + (event.payload.cache_hit ? 0 : 1),
      };
    case "render":
    case "log":
    case "diagnostics":
      return prev;
  }
}
