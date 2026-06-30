// In-job progress view — opens a WS to /api/jobs/ws/:job_id and renders the
// live "what the AI is doing" timeline, a current-activity banner, live spend,
// per-phase decisions, and a cancel button. On terminal `succeeded` → routes to
// /jobs/:job_id/preview; on `failed` → renders the failure detail.
//
// Design intent (S-2.9.13): the user dumps media + a brief and is done — but
// while the AI works we proudly SHOW the work. The phase-by-phase timeline
// conveys how much the app is doing on their behalf (and why it takes a little
// time). It's engaging by default and collapsible for anyone who just wants the
// headline. We compute display values from the snapshot rather than duplicating
// state so renders stay cheap under the hundreds-per-minute WS event stream.

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

// Human, outcome-first phase names. The user never operates these — they just
// watch them happen. The blurbs celebrate the work without leaking raw model
// names or pipeline jargon as identity.
const STAGE_LABELS: Record<string, string> = {
  stage_1_ingest: "Reading your media",
  stage_2_bulk_ops: "Looking at every shot",
  stage_3_metadata: "Understanding each moment",
  stage_4_prefilter: "Picking the keepers",
  stage_5_judge: "Composing your story",
  stage_6_plan: "Designing the edit",
  stage_7_render: "Making your video",
};

const STAGE_BLURBS: Record<string, string> = {
  stage_1_ingest:
    "Fingerprinting every photo and video, reading capture times and GPS, and splitting videos into scenes.",
  stage_2_bulk_ops:
    "Captioning, quality-scoring, and fingerprinting each shot — every single one.",
  stage_3_metadata:
    "Reading each moment in depth: who's in it, the mood, the action, the scenery, the kind of shot.",
  stage_4_prefilter:
    "Dropping near-duplicates and weak frames, keeping the best of each moment.",
  stage_5_judge:
    "A high-reasoning AI composes your whole story in one pass — which shots, in what order, building an arc.",
  stage_6_plan:
    "Turning the story into a precise per-clip edit (and, for music videos, snapping the cuts to the beat).",
  stage_7_render:
    "Assembling the clips, scoring the audio, and finalizing a video you can share anywhere.",
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

// The internal modules each stage runs — surfaced (S-2.11.3) so the live view
// shows the real depth of work, not just one line per stage. Kept jargon-light.
const STAGE_SUBMODULES: Record<string, string[]> = {
  stage_1_ingest: [
    "fingerprint every file",
    "read capture time (EXIF → filename → date)",
    "extract GPS",
    "detect video scenes",
    "make thumbnails",
  ],
  stage_2_bulk_ops: [
    "one-line caption",
    "quality score",
    "narrative-relevance score",
    "visual embedding",
  ],
  stage_3_metadata: [
    "who's in it + expressions",
    "mood & lighting",
    "shot type & framing",
    "scenery & location",
    "specialness score",
  ],
  stage_4_prefilter: [
    "drop unsafe frames",
    "drop too-short video (<2s)",
    "quality floor (+ specialness rescue)",
    "collapse near-duplicates",
    "best-of-burst dedup",
    "cluster by place & time",
    "cap per viewpoint",
    "rank & budget across days",
  ],
  stage_5_judge: [
    "read every candidate",
    "match the brief + music mood",
    "select & order the story",
    "balance people / landscapes / video",
    "cover every place, cap per viewpoint",
  ],
  stage_6_plan: [
    "resolve each clip",
    "snappy 2–3s durations",
    "cap per viewpoint",
    "aspect-ratio handling",
    "beat-snap (music videos)",
  ],
  stage_7_render: [
    "pre-render each clip at 1080p",
    "concatenate the timeline",
    "two-pass loudness normalize",
    "mux the music",
    "finalize the MP4",
  ],
};

// Friendly cost-by-tier names (cost transparency is a feature — kept — but
// without the raw model IDs as identity; the by-provider split still names
// Anthropic / Google).
const TIER_LABELS: Record<string, string> = {
  S: "Quick analysis",
  M: "Detailed analysis",
  L: "Story composition",
  embedding: "Visual fingerprints",
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
  const [showDetails, setShowDetails] = useState(true);
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

  // Stage-2 expected calls = 4 ops/asset (caption + 2 scores + embed). The
  // router counts each as one cache event, so 4× is the right denominator
  // for the user-facing progress bar.
  const stage2Expected = useMemo(() => {
    if (!snapshot) return 0;
    // Videos split into scenes, so the raw input-file count under-counts the
    // "shots" the AI actually analyzes. The backend reports the true
    // post-scene-split count in the Stage-2 detail ("N shots …"); prefer it
    // and fall back to the file count until that detail arrives.
    const s2 = snapshot.stages.find((s) => s.stage === "stage_2_bulk_ops");
    const m = s2?.detail?.match(/([\d,]+)\s*shots/);
    const shots = m ? parseInt(m[1].replace(/,/g, ""), 10) : 0;
    const base = shots > 0 ? shots : snapshot.media_count;
    return base > 0 ? base * 4 : 0;
  }, [snapshot]);

  async function onCancel() {
    if (!job_id || !snapshot) return;
    if (
      !confirm(
        `Cancel this job? You'll keep the cached AI results (next run resumes from where this stops), but the partial progress this job has made will be lost.`
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
          The AI cache is preserved on disk; re-running this job will resume
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

  const headerTitle = snapshot.project_name?.trim() || "Creating your video";
  const elapsedS = snapshot.started_at
    ? Math.max(0, Math.floor((now - new Date(snapshot.started_at).getTime()) / 1000))
    : 0;
  const sinceUpdateS = Math.max(0, Math.floor((now - lastUpdate) / 1000));
  const totalCalls = snapshot.cache_hits + snapshot.cache_misses;
  const cacheRate = totalCalls > 0 ? snapshot.cache_hits / totalCalls : 0;

  // Derive the current activity + overall progress for the banner.
  const ordered = STAGE_ORDER.map((name) => ({
    name,
    row: snapshot.stages.find((s) => s.stage === name),
  }));
  const completedCount = ordered.filter((s) => s.row?.state === "completed").length;
  const runningEntry = ordered.find((s) => s.row?.state === "running");
  const finished = completedCount >= STAGE_ORDER.length;
  const currentName = runningEntry?.name;
  const currentLabel = currentName
    ? STAGE_LABELS[currentName]
    : finished
      ? "Finishing up"
      : "Getting started";
  const currentBlurb = currentName
    ? STAGE_BLURBS[currentName]
    : finished
      ? "Wrapping up your finished video."
      : "Warming up and getting ready to read your media.";
  const currentStep = currentName
    ? STAGE_ORDER.indexOf(currentName) + 1
    : Math.min(completedCount + 1, STAGE_ORDER.length);
  const overallPct = Math.round((completedCount / STAGE_ORDER.length) * 100);

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <header className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-2xl font-semibold text-slate-900">
            {headerTitle}
          </h1>
          <p className="mt-1 text-xs text-slate-500">
            {snapshot.media_count > 0 && (
              <>
                {snapshot.media_count} photos &amp; videos ·{" "}
                {snapshot.target_duration_seconds}s target
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

      {/* Current-activity banner — the engaging "the AI is on it" hero. */}
      <section className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-emerald-50 via-white to-sky-50 p-6">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-emerald-700">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
          </span>
          Working on it · step {currentStep} of {STAGE_ORDER.length}
        </div>
        <h2 className="mt-2 text-2xl font-semibold text-slate-900">
          {currentLabel}
          {!finished && <Ellipsis />}
        </h2>
        <p className="mt-1 max-w-2xl text-sm text-slate-600">{currentBlurb}</p>
        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/80 ring-1 ring-inset ring-slate-200">
          <div
            className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-sky-500 transition-[width] duration-500"
            style={{ width: `${overallPct}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-slate-500">
          Elapsed {formatDuration(elapsedS)} ·{" "}
          <LiveDot ageSeconds={sinceUpdateS} /> updated {sinceUpdateS}s ago
        </p>
      </section>

      <div className="mt-6 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">
          What the AI is doing for you
        </h3>
        <button
          type="button"
          onClick={() => setShowDetails((v) => !v)}
          className="rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
        >
          {showDetails ? "Hide details" : "Show details"}
        </button>
      </div>

      <section className="mt-3 grid gap-4 lg:grid-cols-[2fr,1fr]">
        <ol className="rounded-xl border border-slate-200 bg-white p-5">
          {ordered.map((s, i) => (
            <TimelineStage
              key={s.name}
              label={STAGE_LABELS[s.name] ?? s.name}
              blurb={STAGE_BLURBS[s.name] ?? ""}
              stage={s.name}
              row={s.row}
              index={i}
              isLast={i === ordered.length - 1}
              showDetails={showDetails}
              stage2Expected={stage2Expected}
              cacheHits={snapshot.cache_hits}
              cacheMisses={snapshot.cache_misses}
              now={now}
            />
          ))}
        </ol>

        <aside className="space-y-3">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-700">Live spend</h2>
            <p className="mt-1 text-2xl font-semibold text-slate-900">
              ${snapshot.total_cost_usd.toFixed(2)}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              {totalCalls > 0 ? (
                <>
                  {snapshot.cache_hits} reused ·{" "}
                  {(cacheRate * 100).toFixed(0)}% from cache (saves you money)
                </>
              ) : (
                "Tracking cost live as the AI works."
              )}
            </p>
            {showDetails && Object.keys(snapshot.cost_by_tier_usd).length > 0 && (
              <>
                <h3 className="mt-3 text-xs font-medium text-slate-600">
                  By kind of work
                </h3>
                <dl className="mt-1 space-y-1 text-xs text-slate-600">
                  {Object.entries(snapshot.cost_by_tier_usd).map(([tier, cost]) => (
                    <div key={tier} className="flex justify-between gap-2">
                      <dt className="truncate">{TIER_LABELS[tier] ?? tier}</dt>
                      <dd className="font-mono">${cost.toFixed(4)}</dd>
                    </div>
                  ))}
                </dl>
              </>
            )}
            {showDetails &&
              Object.keys(snapshot.cost_by_provider_usd).length > 0 && (
                <>
                  <h3 className="mt-3 text-xs font-medium text-slate-600">
                    By provider
                  </h3>
                  <dl className="mt-1 space-y-1 text-xs text-slate-600">
                    {Object.entries(snapshot.cost_by_provider_usd).map(
                      ([prov, cost]) => (
                        <div key={prov} className="flex justify-between gap-2">
                          <dt>{PROVIDER_LABELS[prov] ?? prov}</dt>
                          <dd className="font-mono">${cost.toFixed(4)}</dd>
                        </div>
                      )
                    )}
                  </dl>
                </>
              )}
          </div>
          <p className="px-1 text-xs text-slate-400">
            Capped by the daily budget you set in Settings — the AI stops before
            it goes over.
          </p>
        </aside>
      </section>

      {Object.keys(livePhases).length > 0 && (
        <section className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4">
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

// -- Timeline stage ------------------------------------------------------

function TimelineStage({
  label,
  blurb,
  stage,
  row,
  index,
  isLast,
  showDetails,
  stage2Expected,
  cacheHits,
  cacheMisses,
  now,
}: {
  label: string;
  blurb: string;
  stage: string;
  row: StageProgress | undefined;
  index: number;
  isLast: boolean;
  showDetails: boolean;
  stage2Expected: number;
  cacheHits: number;
  cacheMisses: number;
  now: number;
}) {
  const state = row?.state ?? "pending";
  const detail = row?.detail ?? "";

  // Per-stage progress for the running stage. Stage 2 is computable; others
  // show their detail string.
  let progressText: string | null = null;
  let progressPct: number | null = null;
  if (state === "running" && stage === "stage_2_bulk_ops" && stage2Expected > 0) {
    const done = cacheHits + cacheMisses;
    const shown = Math.min(done, stage2Expected);
    progressPct = Math.min(100, Math.round((done / stage2Expected) * 100));
    progressText = `${shown.toLocaleString()}/${stage2Expected.toLocaleString()} shots analyzed · ${progressPct}%`;
  }

  // Elapsed for running / total for completed.
  let timing = "";
  if (state === "running" && row?.started_at) {
    const elapsed = Math.max(
      0,
      Math.floor((now - new Date(row.started_at).getTime()) / 1000)
    );
    timing = formatDuration(elapsed);
  } else if (state === "completed" && row?.started_at && row?.completed_at) {
    const dur = Math.max(
      0,
      Math.floor(
        (new Date(row.completed_at).getTime() - new Date(row.started_at).getTime()) / 1000
      )
    );
    timing = formatDuration(dur);
  }

  const labelColor =
    state === "completed"
      ? "text-slate-800"
      : state === "running"
        ? "text-slate-900 font-semibold"
        : state === "failed"
          ? "text-red-700 font-semibold"
          : "text-slate-400";

  return (
    <li className="flex items-stretch gap-4">
      {/* Node + connector */}
      <div className="flex flex-col items-center">
        <StageNode state={state} index={index} />
        {!isLast && (
          <div
            className={
              "w-0.5 flex-1 " +
              (state === "completed" ? "bg-emerald-300" : "bg-slate-200")
            }
          />
        )}
      </div>

      <div className={"flex-1 " + (isLast ? "pb-0" : "pb-6")}>
        <div className="flex items-baseline justify-between gap-3">
          <span className={"text-sm " + labelColor}>{label}</span>
          {timing && (
            <span className="shrink-0 font-mono text-xs text-slate-400">
              {timing}
            </span>
          )}
        </div>

        {showDetails && (
          <p className="mt-0.5 text-xs leading-relaxed text-slate-500">{blurb}</p>
        )}

        {showDetails &&
          STAGE_SUBMODULES[stage] &&
          (state === "running" || state === "completed") && (
            <ul className="mt-1.5 flex flex-wrap gap-1">
              {STAGE_SUBMODULES[stage].map((m) => (
                <li
                  key={m}
                  className={
                    "rounded px-1.5 py-0.5 text-[10px] " +
                    (state === "running"
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-slate-100 text-slate-500")
                  }
                >
                  {state === "completed" ? "✓ " : ""}
                  {m}
                </li>
              ))}
            </ul>
          )}

        {state === "completed" && detail && (
          <p className="mt-1 text-xs text-slate-500">{detail}</p>
        )}

        {state === "running" && (progressText || detail) && (
          <p className="mt-1 text-xs font-medium text-emerald-700">
            {progressText ?? detail}
          </p>
        )}

        {progressPct !== null && state === "running" && (
          <div className="mt-1.5 h-1 overflow-hidden rounded bg-slate-100">
            <div
              className="h-full rounded bg-gradient-to-r from-emerald-500 to-sky-500 transition-[width] duration-300"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        )}
      </div>
    </li>
  );
}

function StageNode({ state, index }: { state: string; index: number }) {
  if (state === "completed") {
    return (
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-sm font-semibold text-white">
        ✓
      </span>
    );
  }
  if (state === "failed") {
    return (
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-500 text-sm font-semibold text-white">
        ✗
      </span>
    );
  }
  if (state === "running") {
    return (
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-sky-500 text-white ring-4 ring-emerald-100">
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
      </span>
    );
  }
  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 border-slate-200 bg-white text-xs font-medium text-slate-400">
      {index + 1}
    </span>
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

function Ellipsis() {
  return (
    <span className="ml-0.5 inline-flex" aria-hidden>
      <span className="animate-bounce [animation-delay:-0.3s]">.</span>
      <span className="animate-bounce [animation-delay:-0.15s]">.</span>
      <span className="animate-bounce">.</span>
    </span>
  );
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
