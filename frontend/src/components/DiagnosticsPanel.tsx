// A-023 feedback loop: per-phase diagnostics viewer + feedback popup.
//
// Loads /api/snapshots/:id/diagnostics and renders each pipeline phase as
// an expandable panel of decision cards (with media thumbnails). Clicking
// "Feedback" on any decision opens a popup where the user marks it
// correct / incorrect / should-be-different and adds a note; submitting
// POSTs to /api/feedback, which persists it (DB + feedback.jsonl) for a
// later Claude session to pick up.

import { useEffect, useMemo, useState } from "react";

import {
  capturePageScreenshot,
  fetchDiagnostics,
  submitFeedback,
  type DiagnosticDecision,
  type DiagnosticPhase,
  type Diagnostics,
  type Verdict,
} from "../api/diagnostics";

interface FeedbackTarget {
  phase: string;
  decision: DiagnosticDecision;
}

// Fetch-mode wrapper: loads a completed snapshot's diagnostics (Preview page).
export default function DiagnosticsPanel({
  snapshotId,
  jobId,
  projectId,
}: {
  snapshotId: string;
  jobId?: string;
  projectId?: string;
}) {
  const [diag, setDiag] = useState<Diagnostics | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchDiagnostics(snapshotId)
      .then((d) => {
        if (cancelled) return;
        if (d === null) setMissing(true);
        else setDiag(d);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [snapshotId]);

  if (missing) {
    return (
      <p className="mt-2 text-xs text-slate-500">
        No diagnostics for this snapshot — it predates the feedback feature.
        Re-run the job to inspect its per-phase decisions.
      </p>
    );
  }
  if (error) {
    return <p className="mt-2 text-xs text-red-600">Couldn't load diagnostics: {error}</p>;
  }
  if (!diag) {
    return <p className="mt-2 text-xs text-slate-500">Loading diagnostics…</p>;
  }

  return (
    <DiagnosticsView
      phases={diag.phases}
      snapshotId={snapshotId}
      jobId={jobId}
      projectId={projectId}
    />
  );
}

// Pure renderer — used both by the fetch wrapper (Preview) and by the live
// in-progress view (JobInProgress), which feeds phases in as they stream.
export function DiagnosticsView({
  phases,
  snapshotId,
  jobId,
  projectId,
}: {
  phases: DiagnosticPhase[];
  snapshotId?: string;
  jobId?: string;
  projectId?: string;
}) {
  const [openPhases, setOpenPhases] = useState<Set<string>>(new Set());
  const [target, setTarget] = useState<FeedbackTarget | null>(null);
  const [givenCount, setGivenCount] = useState(0);

  function togglePhase(phase: string) {
    setOpenPhases((prev) => {
      const next = new Set(prev);
      if (next.has(phase)) next.delete(phase);
      else next.add(phase);
      return next;
    });
  }

  if (phases.length === 0) {
    return (
      <p className="mt-2 text-xs text-slate-500">
        Waiting for the first phase to finish…
      </p>
    );
  }

  return (
    <div className="mt-3 space-y-3">
      {givenCount > 0 && (
        <p className="rounded bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
          {givenCount} piece{givenCount === 1 ? "" : "s"} of feedback saved. Ask
          Claude to “pick up the submitted feedback” in a future session.
        </p>
      )}
      {phases.map((phase) => (
        <PhaseSection
          key={phase.phase}
          phase={phase}
          open={openPhases.has(phase.phase)}
          onToggle={() => togglePhase(phase.phase)}
          onFeedback={(decision) => setTarget({ phase: phase.phase, decision })}
        />
      ))}

      {target && (
        <FeedbackModal
          target={target}
          snapshotId={snapshotId}
          jobId={jobId}
          projectId={projectId}
          onClose={() => setTarget(null)}
          onSaved={() => {
            setGivenCount((c) => c + 1);
            setTarget(null);
          }}
        />
      )}
    </div>
  );
}

function PhaseSection({
  phase,
  open,
  onToggle,
  onFeedback,
}: {
  phase: DiagnosticPhase;
  open: boolean;
  onToggle: () => void;
  onFeedback: (d: DiagnosticDecision) => void;
}) {
  const counts = useMemo(() => summarize(phase), [phase]);
  return (
    <section className="rounded border border-slate-200 bg-white">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <span className="min-w-0">
          <span className="text-sm font-semibold text-slate-900">{phase.title}</span>
          <span className="ml-2 text-xs text-slate-500">{counts}</span>
        </span>
        <span className="shrink-0 text-slate-400">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="border-t border-slate-100 px-4 py-3">
          <p className="mb-3 text-xs text-slate-500">{phase.description}</p>
          {phase.phase === "stage_5_judge" && typeof phase.summary.arc_reasoning === "string" && (
            <details className="mb-3 text-xs text-slate-600">
              <summary className="cursor-pointer font-medium text-slate-700">
                Judge reasoning
              </summary>
              <p className="mt-1 whitespace-pre-wrap rounded bg-slate-50 p-2">
                {phase.summary.arc_reasoning as string}
              </p>
            </details>
          )}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
            {phase.decisions.map((d, i) => (
              <DecisionCard key={`${d.ref ?? d.person_id ?? i}`} decision={d} onFeedback={() => onFeedback(d)} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function DecisionCard({
  decision,
  onFeedback,
}: {
  decision: DiagnosticDecision;
  onFeedback: () => void;
}) {
  const [imgOk, setImgOk] = useState(true);
  const label = decisionLabel(decision);
  const tone = decisionTone(decision);
  return (
    <div className="overflow-hidden rounded border border-slate-200">
      <div className="relative aspect-square bg-slate-100">
        {decision.thumb_url && imgOk ? (
          <img
            src={decision.thumb_url}
            alt={decision.caption ?? decision.ref ?? "media"}
            className="h-full w-full object-cover"
            onError={() => setImgOk(false)}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-[10px] text-slate-400">
            {decision.kind === "video_scene" || decision.scene_index != null ? "video scene" : "no thumb"}
          </div>
        )}
        <span className={`absolute left-1 top-1 rounded px-1.5 py-0.5 text-[10px] font-medium ${tone}`}>
          {label}
        </span>
      </div>
      <div className="p-1.5">
        {decision.reason && (
          <p className="truncate text-[10px] text-slate-500" title={decision.reason}>
            {decision.reason}
          </p>
        )}
        {decision.caption && (
          <p className="truncate text-[10px] text-slate-600" title={decision.caption}>
            {decision.caption}
          </p>
        )}
        <button
          type="button"
          onClick={onFeedback}
          className="mt-1 w-full rounded border border-slate-200 py-0.5 text-[10px] font-medium text-slate-600 hover:border-slate-400 hover:text-slate-900"
        >
          Feedback
        </button>
      </div>
    </div>
  );
}

function FeedbackModal({
  target,
  snapshotId,
  jobId,
  projectId,
  onClose,
  onSaved,
}: {
  target: FeedbackTarget;
  snapshotId?: string;
  jobId?: string;
  projectId?: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [verdict, setVerdict] = useState<Verdict>("incorrect");
  const [comment, setComment] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { phase, decision } = target;

  async function onSubmit() {
    setSaving(true);
    setError(null);
    try {
      // Capture the whole page (best-effort) so the saved feedback records
      // exactly what the user was looking at. The modal itself is excluded
      // from the capture (tagged data-ic-skip-capture).
      const screenshot = await capturePageScreenshot();
      await submitFeedback({
        phase,
        verdict,
        snapshot_id: snapshotId,
        job_id: jobId,
        project_id: projectId,
        content_hash: decision.content_hash,
        decision_ref: decisionRef(decision),
        comment: comment.trim() || undefined,
        context: decision as unknown as Record<string, unknown>,
        screenshot_data_url: screenshot,
      });
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      data-ic-skip-capture="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-md rounded-lg bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-sm font-semibold text-slate-900">Feedback on this decision</h3>
        <div className="mt-2 flex items-start gap-3">
          {decision.thumb_url && (
            <img src={decision.thumb_url} alt="" className="h-16 w-16 shrink-0 rounded object-cover" onError={(e) => ((e.target as HTMLImageElement).style.display = "none")} />
          )}
          <div className="min-w-0 text-xs text-slate-600">
            <p>
              <span className="font-medium">{phaseTitle(phase)}</span> · {decisionLabel(decision)}
            </p>
            {decision.reason && <p className="text-slate-500">reason: {decision.reason}</p>}
            {decision.role && <p className="text-slate-500">role: {decision.role}</p>}
            {decision.caption && <p className="truncate text-slate-500">{decision.caption}</p>}
          </div>
        </div>

        <div className="mt-4">
          <p className="text-xs font-medium text-slate-700">Was this the right call?</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {(
              [
                ["correct", "✓ Correct"],
                ["incorrect", "✗ Incorrect"],
                ["different", "↻ Should differ"],
              ] as [Verdict, string][]
            ).map(([v, label]) => (
              <button
                key={v}
                type="button"
                onClick={() => setVerdict(v)}
                className={
                  "rounded border px-3 py-1 text-xs font-medium " +
                  (verdict === v
                    ? "border-slate-900 bg-slate-900 text-white"
                    : "border-slate-300 text-slate-700 hover:border-slate-500")
                }
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={3}
          placeholder="What should have happened, and why? (e.g. 'best of the burst — keep this one, drop the others')"
          className="mt-3 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        />

        {error && <p className="mt-2 rounded bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>}

        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onSubmit}
            disabled={saving}
            className="rounded bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:bg-slate-400"
          >
            {saving ? "Saving…" : "Submit feedback"}
          </button>
        </div>
      </div>
    </div>
  );
}

// -- helpers -------------------------------------------------------------

function summarize(phase: DiagnosticPhase): string {
  const s = phase.summary;
  if (phase.phase === "stage_4_prefilter") return `${s.kept ?? "?"}/${s.input_count ?? "?"} kept`;
  if (phase.phase === "stage_5_judge") return `${s.selected ?? "?"} selected · conf ${fmtNum(s.confidence)}`;
  if (phase.phase === "stage_6_plan") return `${s.clips ?? "?"} clips`;
  if (phase.phase === "cast") return `${s.group ?? 0} group · ${s.crowd ?? 0} crowd`;
  return `${phase.decisions.length} items`;
}

function decisionLabel(d: DiagnosticDecision): string {
  if (d.decision === "keep") return "kept";
  if (d.decision === "drop") return "dropped";
  if (d.decision === "select") return d.role ? `#${d.placement_position} ${d.role}` : "selected";
  if (d.decision === "clip") return `clip #${d.position ?? ""}`;
  if (d.decision === "group") return "group";
  if (d.decision === "crowd") return "crowd";
  return d.decision ?? "";
}

function decisionTone(d: DiagnosticDecision): string {
  if (d.decision === "drop") return "bg-rose-100 text-rose-800";
  if (d.decision === "keep" || d.decision === "select" || d.decision === "clip" || d.decision === "group")
    return "bg-emerald-100 text-emerald-800";
  if (d.decision === "crowd") return "bg-slate-200 text-slate-700";
  return "bg-slate-200 text-slate-700";
}

function decisionRef(d: DiagnosticDecision): string | undefined {
  if (d.person_id) return d.person_id;
  if (d.decision === "drop" && d.reason) return `drop:${d.reason}`;
  if (d.decision === "select" && d.role) return `select:${d.role}`;
  if (d.decision) return d.decision;
  return undefined;
}

function phaseTitle(phase: string): string {
  const map: Record<string, string> = {
    stage_4_prefilter: "Pre-filter",
    stage_5_judge: "Narrative judge",
    stage_6_plan: "Plan",
    cast: "Trip cast",
  };
  return map[phase] ?? phase;
}

function fmtNum(v: unknown): string {
  return typeof v === "number" ? v.toFixed(2) : "?";
}
