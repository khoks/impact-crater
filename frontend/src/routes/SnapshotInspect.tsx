// SnapshotInspect — review a PERSISTED render and give per-phase feedback,
// keyed on snapshot_id (NOT the in-memory job). This is how you inspect and
// give feedback on a finished job after a server/computer restart: the live
// /jobs/:id view is gone (jobs are in-memory), but the render + per-phase
// diagnostics are persisted on disk/DB and fetched by snapshot_id.

import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import DiagnosticsPanel from "../components/DiagnosticsPanel";

export default function SnapshotInspect() {
  const { snapshot_id } = useParams<{ snapshot_id: string }>();
  const [search] = useSearchParams();
  const projectId = search.get("project") ?? undefined;
  const [videoOk, setVideoOk] = useState(true);

  if (!snapshot_id) {
    return <p className="px-6 py-12 text-slate-500">No snapshot in the URL.</p>;
  }

  const videoSrc = `/api/snapshots/${snapshot_id}/render.mp4`;

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">
          Inspect &amp; give feedback
        </h1>
        <Link to="/dashboard" className="text-sm text-slate-600 hover:text-slate-900">
          ← Dashboard
        </Link>
      </header>
      <p className="mt-1 text-xs text-slate-500">
        Snapshot <span className="font-mono">{snapshot_id}</span> — loaded from the
        saved render and diagnostics. This works even after a restart; it doesn't
        need the original (in-memory) job.
      </p>

      {videoOk && (
        <div className="mt-6 overflow-hidden rounded-lg border border-slate-300 bg-black">
          <video
            src={videoSrc}
            controls
            className="block aspect-video w-full"
            onError={() => setVideoOk(false)}
          />
        </div>
      )}

      <section className="mt-8 rounded border border-slate-200 bg-slate-50 p-4">
        <h2 className="text-sm font-semibold text-slate-700">Per-phase decisions</h2>
        <p className="mt-1 text-xs text-slate-500">
          Open any phase to see exactly what was decided — kept/dropped media and
          why, the trip cast, the narrative selection, and the final clips. Click
          “Feedback” on anything to mark it correct / incorrect / should-be-different
          and add a note. Your input is saved for Claude to pick up in a later session.
        </p>
        <DiagnosticsPanel snapshotId={snapshot_id} projectId={projectId} />
      </section>
    </main>
  );
}
