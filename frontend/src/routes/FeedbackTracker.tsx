// A-024 — developer feedback/enhancement tracker. Lists every piece of
// feedback submitted from the app with full detail: the decision it's about,
// the phase's media + decisions, the page screenshot, job/snapshot context,
// and editable status + priority.

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  getFeedbackDetail,
  listFeedback,
  patchFeedback,
  type FeedbackDetail,
  type FeedbackItem,
  type FeedbackStatus,
  type Priority,
} from "../api/trackers";

const STATUSES: FeedbackStatus[] = ["new", "triaged", "addressed", "dismissed"];
const PRIORITIES: Priority[] = ["P0", "P1", "P2", "P3"];

const STATUS_TONE: Record<string, string> = {
  new: "bg-sky-100 text-sky-800",
  triaged: "bg-amber-100 text-amber-800",
  addressed: "bg-emerald-100 text-emerald-800",
  dismissed: "bg-slate-200 text-slate-600",
};
const VERDICT_TONE: Record<string, string> = {
  correct: "bg-emerald-100 text-emerald-800",
  incorrect: "bg-rose-100 text-rose-800",
  different: "bg-amber-100 text-amber-800",
};

export default function FeedbackTracker() {
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [filter, setFilter] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);

  function reload() {
    listFeedback(filter || undefined)
      .then((d) => {
        setItems(d);
        setLoaded(true);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }

  useEffect(reload, [filter]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const it of items) c[it.status] = (c[it.status] ?? 0) + 1;
    return c;
  }, [items]);

  async function onPatch(id: number, patch: { status?: FeedbackStatus; priority?: Priority }) {
    const updated = await patchFeedback(id, patch);
    setItems((prev) => prev.map((it) => (it.id === id ? updated : it)));
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Feedback & enhancements</h1>
        <Link to="/dashboard" className="text-sm text-slate-600 hover:text-slate-900">
          ← Dashboard
        </Link>
      </header>
      <p className="mt-1 text-xs text-slate-500">
        Everything submitted from the in-app diagnostics. Set priority/status here; Claude
        picks these up with <code className="rounded bg-slate-100 px-1">scripts/feedback.py</code>.
      </p>

      <div className="mt-4 flex items-center gap-2 text-xs">
        <span className="text-slate-500">Filter:</span>
        {["", ...STATUSES].map((s) => (
          <button
            key={s || "all"}
            type="button"
            onClick={() => setFilter(s)}
            className={
              "rounded border px-2 py-0.5 " +
              (filter === s ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 text-slate-700")
            }
          >
            {s || "all"} {s && counts[s] ? `(${counts[s]})` : ""}
          </button>
        ))}
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      {loaded && items.length === 0 && (
        <p className="mt-6 text-slate-500">No feedback yet. Submit some from a job's “Inspect & give feedback”.</p>
      )}

      <ul className="mt-4 space-y-2">
        {items.map((it) => (
          <li key={it.id} className="rounded border border-slate-200 bg-white">
            <div className="flex items-center gap-3 px-4 py-3">
              <button
                type="button"
                onClick={() => setOpenId(openId === it.id ? null : it.id)}
                className="min-w-0 flex-1 text-left"
              >
                <span className="flex items-center gap-2">
                  <span className="font-mono text-xs text-slate-400">#{it.id}</span>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${VERDICT_TONE[it.verdict]}`}>
                    {it.verdict}
                  </span>
                  <span className="truncate text-sm text-slate-800">
                    {it.phase} · {it.decision_ref ?? "—"}
                  </span>
                  {it.has_screenshot && <span title="has screenshot">📷</span>}
                </span>
                {it.comment && (
                  <span className="mt-0.5 block truncate text-xs text-slate-500">{it.comment}</span>
                )}
              </button>
              <PillSelect
                value={it.priority}
                options={PRIORITIES}
                onChange={(v) => onPatch(it.id, { priority: v as Priority })}
              />
              <PillSelect
                value={it.status}
                options={STATUSES}
                tone={STATUS_TONE[it.status]}
                onChange={(v) => onPatch(it.id, { status: v as FeedbackStatus })}
              />
            </div>
            {openId === it.id && <FeedbackDetailView id={it.id} />}
          </li>
        ))}
      </ul>
    </main>
  );
}

function PillSelect({
  value,
  options,
  tone,
  onChange,
}: {
  value: string;
  options: string[];
  tone?: string;
  onChange: (v: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onClick={(e) => e.stopPropagation()}
      className={`shrink-0 rounded border border-slate-300 px-1.5 py-0.5 text-xs ${tone ?? ""}`}
    >
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

function FeedbackDetailView({ id }: { id: number }) {
  const [detail, setDetail] = useState<FeedbackDetail | null>(null);
  const [phaseDecisions, setPhaseDecisions] = useState<Record<string, unknown>[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getFeedbackDetail(id)
      .then((d) => {
        if (cancelled) return;
        setDetail(d);
        // Pull the phase's full decision set (the media + decisions for the
        // step) from the snapshot diagnostics, when available.
        if (d.diagnostics_url) {
          fetch(d.diagnostics_url)
            .then((r) => (r.ok ? r.json() : null))
            .then((diag) => {
              if (cancelled || !diag) return;
              const phase = (diag.phases as { phase: string; decisions: Record<string, unknown>[] }[]).find(
                (p) => p.phase === d.phase
              );
              setPhaseDecisions(phase?.decisions ?? null);
            })
            .catch(() => undefined);
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <p className="px-4 pb-3 text-xs text-red-600">{error}</p>;
  if (!detail) return <p className="px-4 pb-3 text-xs text-slate-400">Loading…</p>;

  const ctx = detail.context ?? {};
  const ctxThumb = typeof ctx.thumb_url === "string" ? ctx.thumb_url : null;

  return (
    <div className="border-t border-slate-100 px-4 py-3 text-xs">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-3">
        <Meta label="Job" value={detail.job_id} mono />
        <Meta label="Project" value={detail.project_id} mono />
        <Meta label="Snapshot" value={detail.snapshot_id} mono />
        <Meta label="Phase" value={detail.phase} />
        <Meta label="Decision" value={detail.decision_ref} />
        <Meta label="Submitted" value={detail.created_at} />
      </dl>

      <div className="mt-3">
        <p className="font-medium text-slate-700">Comment</p>
        <p className="mt-0.5 whitespace-pre-wrap text-slate-600">{detail.comment || "(none)"}</p>
      </div>

      <div className="mt-3 grid gap-4 md:grid-cols-2">
        <div>
          <p className="font-medium text-slate-700">The decision</p>
          <div className="mt-1 flex gap-2">
            {ctxThumb && (
              <img src={ctxThumb} alt="" className="h-20 w-20 rounded object-cover" />
            )}
            <pre className="max-h-40 flex-1 overflow-auto rounded bg-slate-50 p-2 text-[10px] text-slate-600">
              {JSON.stringify(detail.context, null, 1)}
            </pre>
          </div>
        </div>
        {detail.screenshot_url && (
          <div>
            <p className="font-medium text-slate-700">Page at submit time</p>
            <a href={detail.screenshot_url} target="_blank" rel="noopener noreferrer">
              <img
                src={detail.screenshot_url}
                alt="page screenshot"
                className="mt-1 w-full rounded border border-slate-200"
              />
            </a>
          </div>
        )}
      </div>

      {phaseDecisions && phaseDecisions.length > 0 && (
        <div className="mt-3">
          <p className="font-medium text-slate-700">
            All decisions in this phase ({phaseDecisions.length})
          </p>
          <div className="mt-1 flex flex-wrap gap-1">
            {phaseDecisions.map((d, i) => {
              const thumb = typeof d.thumb_url === "string" ? d.thumb_url : null;
              const isTarget = d.content_hash === detail.content_hash;
              const dropped = d.decision === "drop";
              return (
                <div
                  key={i}
                  title={`${d.decision ?? ""} ${d.reason ?? d.role ?? ""}`}
                  className={
                    "h-12 w-12 overflow-hidden rounded border-2 " +
                    (isTarget ? "border-amber-500" : dropped ? "border-rose-200" : "border-emerald-200")
                  }
                >
                  {thumb ? (
                    <img src={thumb} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-[8px] text-slate-400">
                      {String(d.decision ?? "")}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {detail.diagnostics_url && (
            <p className="mt-1 text-slate-400">
              Amber-bordered = the shot this feedback is about. Green = kept/selected, red = dropped.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function Meta({ label, value, mono }: { label: string; value: string | null; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-slate-400">{label}</dt>
      <dd className={"truncate text-slate-700 " + (mono ? "font-mono" : "")}>{value || "—"}</dd>
    </div>
  );
}
