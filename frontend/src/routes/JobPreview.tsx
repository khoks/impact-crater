// Preview view — HTML5 video of the rendered MP4 served from
// /api/snapshots/:snapshot_id/render.mp4, the job's cost line, and the shared
// Refine / Approve & publish actions (SnapshotActions, also on SnapshotInspect).

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import DiagnosticsPanel from "../components/DiagnosticsPanel";
import SnapshotActions from "../components/SnapshotActions";
import { getJob, type JobSnapshot } from "../api/jobs";

export default function JobPreview() {
  const { job_id } = useParams<{ job_id: string }>();
  const [snapshot, setSnapshot] = useState<JobSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [diagOpen, setDiagOpen] = useState(false);

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

      <SnapshotActions
        snapshotId={snapshot.snapshot_id}
        projectId={snapshot.project_id}
        fallbackTitle={snapshot.project_name || "Story Video"}
        leading={
          <button
            type="button"
            onClick={() => setDiagOpen((v) => !v)}
            className="mr-auto rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            {diagOpen ? "Hide diagnostics" : "Inspect & give feedback"}
          </button>
        }
      />

      {diagOpen && (
        <section className="mt-6 rounded border border-slate-200 bg-slate-50 p-4">
          <h2 className="text-sm font-semibold text-slate-700">
            Per-phase decisions
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Open any phase to see exactly what was decided — what media was
            kept or dropped and why, how the arc was ordered, the final clips.
            Click “Feedback” on anything that looks wrong; your input is saved
            for Claude to act on later.
          </p>
          <DiagnosticsPanel
            snapshotId={snapshot.snapshot_id}
            jobId={job_id}
            projectId={snapshot.project_id}
          />
        </section>
      )}
    </main>
  );
}
