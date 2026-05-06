// In-job progress view — opens a WS to /api/jobs/ws/:job_id and renders
// stage-by-stage progress + live cost rollup. On terminal `succeeded` →
// routes to /jobs/:job_id/preview; on `failed` → renders the failure
// detail with a "Back to Dashboard" link.

import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { getJob, type JobProgressEvent, type JobSnapshot } from "../api/jobs";

const STAGE_LABELS: Record<string, string> = {
  stage_1_ingest: "Stage 1 · Ingest",
  stage_2_bulk_ops: "Stage 2 · Bulk ops",
  stage_3_metadata: "Stage 3 · Rich metadata",
  stage_4_prefilter: "Stage 4 · Pre-filter",
  stage_5_judge: "Stage 5 · Narrative judge",
  stage_6_plan: "Stage 6 · Plan compile",
  stage_7_render: "Stage 7 · Render",
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

export default function JobInProgress() {
  const { job_id } = useParams<{ job_id: string }>();
  const navigate = useNavigate();
  const [snapshot, setSnapshot] = useState<JobSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!job_id) return;
    let cancelled = false;

    // Initial snapshot via the polling endpoint so we have stage rows
    // even before the first WS event arrives.
    getJob(job_id)
      .then((s) => {
        if (!cancelled) setSnapshot(s);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });

    // Open the WS. Resolve protocol from the page origin.
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
      setSnapshot((prev) => applyEvent(prev, event));
      if (event.type === "state") {
        if (event.payload.state === "succeeded") {
          navigate(`/jobs/${job_id}/preview`, { replace: true });
        }
      }
    };

    ws.onerror = () => {
      if (!cancelled) setError("WebSocket connection error");
    };

    return () => {
      cancelled = true;
      ws.close();
    };
    // job_id never changes within a route mount; navigate is stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job_id]);

  if (!job_id) {
    return <Navigate />;
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

  if (snapshot.state === "failed") {
    return (
      <main className="mx-auto max-w-3xl px-6 py-12">
        <h1 className="text-2xl font-semibold text-slate-900">Job failed</h1>
        <p className="mt-3 rounded bg-red-50 px-4 py-3 text-sm text-red-700">
          {snapshot.failure_reason ?? "(no reason recorded)"}
        </p>
        <Link to="/dashboard" className="mt-6 inline-block text-sm text-slate-600 hover:text-slate-900">
          ← Back to dashboard
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Job in progress</h1>
        <span className="rounded bg-slate-100 px-2 py-1 text-xs font-mono text-slate-600">
          {snapshot.state}
        </span>
      </header>
      <p className="mt-2 text-sm text-slate-500">
        Project <span className="font-mono">{snapshot.project_id}</span>
      </p>

      <section className="mt-8 grid gap-4 lg:grid-cols-[2fr,1fr]">
        <ol className="space-y-2 rounded border border-slate-200 bg-white p-4">
          {STAGE_ORDER.map((stageName) => {
            const row = snapshot.stages.find((s) => s.stage === stageName);
            return (
              <StageRow
                key={stageName}
                label={STAGE_LABELS[stageName] ?? stageName}
                state={row?.state ?? "pending"}
                detail={row?.detail ?? ""}
              />
            );
          })}
        </ol>

        <aside className="rounded border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-700">Live spend</h2>
          <p className="mt-1 text-2xl font-semibold">
            ${snapshot.total_cost_usd.toFixed(2)}
          </p>
          <dl className="mt-3 space-y-1 text-xs text-slate-600">
            {Object.entries(snapshot.cost_by_tier_usd).map(([tier, cost]) => (
              <div key={tier} className="flex justify-between">
                <dt className="font-mono">{tier}</dt>
                <dd>${cost.toFixed(4)}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-xs text-slate-400">
            cache hits {snapshot.cache_hits} · misses {snapshot.cache_misses}
          </p>
        </aside>
      </section>
    </main>
  );
}

function StageRow({
  label,
  state,
  detail,
}: {
  label: string;
  state: "pending" | "running" | "completed" | "failed";
  detail: string;
}) {
  const icon =
    state === "completed"
      ? "✓"
      : state === "failed"
        ? "✗"
        : state === "running"
          ? "…"
          : "·";
  const color =
    state === "completed"
      ? "text-emerald-600"
      : state === "failed"
        ? "text-red-600"
        : state === "running"
          ? "text-amber-600"
          : "text-slate-300";
  return (
    <li className="flex items-baseline gap-3 text-sm">
      <span className={`w-4 text-center font-mono ${color}`}>{icon}</span>
      <span className="flex-1 text-slate-700">{label}</span>
      {detail && <span className="text-xs text-slate-500">{detail}</span>}
    </li>
  );
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
      return prev;
  }
}

// react-router renders <Navigate> from this module rather than re-importing.
function Navigate() {
  return <p className="px-6 py-12 text-slate-500">No job_id in URL.</p>;
}
