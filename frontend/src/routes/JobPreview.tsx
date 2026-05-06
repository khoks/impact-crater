// Preview view — HTML5 video of the rendered MP4 served from
// /api/snapshots/:snapshot_id/render.mp4. M6: Refine button is now
// functional (sync N-009 thinking step + result panel). Approve still
// disabled until M7 publish lands.

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getJob, postRefine, type JobSnapshot, type RefineResponse } from "../api/jobs";

export default function JobPreview() {
  const { job_id } = useParams<{ job_id: string }>();
  const [snapshot, setSnapshot] = useState<JobSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Refine modal state.
  const [refineOpen, setRefineOpen] = useState(false);
  const [refineMessage, setRefineMessage] = useState("");
  const [refineResult, setRefineResult] = useState<RefineResponse | null>(null);
  const [refining, setRefining] = useState(false);
  const [refineError, setRefineError] = useState<string | null>(null);

  useEffect(() => {
    if (!job_id) return;
    let cancelled = false;
    getJob(job_id)
      .then((s) => {
        if (cancelled) return;
        if (s.state !== "succeeded") {
          setError(`Job is in state '${s.state}'; preview only available after success`);
          return;
        }
        setSnapshot(s);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [job_id]);

  if (error) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-12">
        <h1 className="text-2xl font-semibold text-slate-900">Preview unavailable</h1>
        <p className="mt-3 text-red-600">{error}</p>
        <Link to="/dashboard" className="mt-6 inline-block text-sm text-slate-600 hover:text-slate-900">
          ← Back to dashboard
        </Link>
      </main>
    );
  }

  if (!snapshot || !snapshot.snapshot_id) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-12">
        <p className="text-slate-500">Loading preview…</p>
      </main>
    );
  }

  const videoSrc = `/api/snapshots/${snapshot.snapshot_id}/render.mp4`;

  async function onRefine() {
    if (!snapshot?.snapshot_id || !refineMessage.trim()) return;
    setRefining(true);
    setRefineError(null);
    setRefineResult(null);
    try {
      const result = await postRefine(snapshot.snapshot_id, refineMessage.trim());
      setRefineResult(result);
    } catch (err) {
      setRefineError(err instanceof Error ? err.message : String(err));
    } finally {
      setRefining(false);
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Preview</h1>
        <Link to="/dashboard" className="text-sm text-slate-600 hover:text-slate-900">
          ← Dashboard
        </Link>
      </header>

      <div className="mt-6 overflow-hidden rounded-lg border border-slate-300 bg-black">
        <video
          src={videoSrc}
          controls
          className="block aspect-video w-full"
          data-testid="preview-video"
        >
          Your browser doesn't support inline video playback.
        </video>
      </div>

      <p className="mt-3 text-xs text-slate-500">
        Rendered from snapshot{" "}
        <span className="font-mono">{snapshot.snapshot_id}</span> · total cost
        $
        {snapshot.total_cost_usd.toFixed(2)} · cache {snapshot.cache_hits}/
        {snapshot.cache_hits + snapshot.cache_misses} hits
      </p>

      <div className="mt-8 flex items-center justify-end gap-3">
        <button
          type="button"
          onClick={() => {
            setRefineOpen((v) => !v);
            setRefineResult(null);
            setRefineError(null);
          }}
          className="rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          {refineOpen ? "Cancel refine" : "Refine this result"}
        </button>
        <button
          type="button"
          disabled
          title="Publish lands at M7 (E-2.8)"
          className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white opacity-60 disabled:cursor-not-allowed"
        >
          Approve
        </button>
      </div>
      <p className="mt-2 text-right text-xs text-slate-400">
        Approve = publish to YouTube — that flow ships at M7.
      </p>

      {refineOpen && (
        <section className="mt-6 rounded border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-700">Refine</h2>
          <p className="mt-1 text-xs text-slate-500">
            Type what you'd change ("more landscape, less faces"; "punchier
            opener"; etc). The orchestrator will decide whether to re-run the
            judgment with an addendum or explain why your refinement isn't
            possible with the current candidate set.
          </p>
          <textarea
            value={refineMessage}
            onChange={(e) => setRefineMessage(e.target.value)}
            rows={3}
            className="mt-2 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
            placeholder="What would you change about this video?"
          />
          <div className="mt-2 flex justify-end">
            <button
              type="button"
              onClick={onRefine}
              disabled={refining || !refineMessage.trim()}
              className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {refining ? "Thinking…" : "Submit refinement"}
            </button>
          </div>
          {refineError && (
            <p role="alert" className="mt-3 rounded bg-red-50 px-3 py-2 text-xs text-red-700">
              {refineError}
            </p>
          )}
          {refineResult && (
            <div className="mt-3 rounded bg-slate-50 p-3 text-xs">
              <p className="font-semibold text-slate-700">
                Strategy: <span className="font-mono">{refineResult.strategy}</span>
              </p>
              <p className="mt-1 text-slate-600">{refineResult.rationale}</p>
              {refineResult.explanation && (
                <p className="mt-2 text-slate-700">{refineResult.explanation}</p>
              )}
              {refineResult.brief_addendum && (
                <p className="mt-2 text-slate-700">
                  Brief addendum: <em>{refineResult.brief_addendum}</em>
                </p>
              )}
              {refineResult.new_arc_judgment && (
                <p className="mt-2 text-emerald-700">
                  New arc generated. Re-rendering with the updated plan ships at v1.
                </p>
              )}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
