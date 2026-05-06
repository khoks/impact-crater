// Preview view — HTML5 video of the rendered MP4 served from
// /api/snapshots/:snapshot_id/render.mp4. Approve and Refine buttons
// are present but disabled with M7 / M6 tooltips per the epic scope.

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getJob, type JobSnapshot } from "../api/jobs";

export default function JobPreview() {
  const { job_id } = useParams<{ job_id: string }>();
  const [snapshot, setSnapshot] = useState<JobSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

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

      <div className="mt-8 flex items-center justify-end gap-3">
        <button
          type="button"
          disabled
          title="Refine lands at M6 (E-2.7)"
          className="rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-500 disabled:cursor-not-allowed"
        >
          Refine this result
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
    </main>
  );
}
