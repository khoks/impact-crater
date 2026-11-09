// SnapshotInspect — the canonical preview of a PERSISTED render (S-3.5.5),
// keyed on snapshot_id rather than the in-memory job, so it works after a
// restart and for refined children: watch, refine, approve & publish, see the
// refine chain and the publish history, and give per-phase feedback.

import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { fetchSnapshot, type SnapshotDetail } from "../api/snapshots";
import DiagnosticsPanel from "../components/DiagnosticsPanel";
import PublishBadges from "../components/PublishBadges";
import SnapshotActions from "../components/SnapshotActions";

export default function SnapshotInspect() {
  const { snapshot_id } = useParams<{ snapshot_id: string }>();
  const [search] = useSearchParams();

  if (!snapshot_id) {
    return <p className="px-6 py-12 text-slate-500">No snapshot in the URL.</p>;
  }
  // Keyed so moving along the refine chain starts each snapshot fresh.
  return (
    <InspectSnapshot
      key={snapshot_id}
      snapshotId={snapshot_id}
      projectHint={search.get("project") ?? undefined}
    />
  );
}

function InspectSnapshot({
  snapshotId,
  projectHint,
}: {
  snapshotId: string;
  projectHint?: string;
}) {
  const [detail, setDetail] = useState<SnapshotDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [videoOk, setVideoOk] = useState(true);

  function load() {
    fetchSnapshot(snapshotId)
      .then(setDetail)
      .catch((err) => setLoadError(err instanceof Error ? err.message : String(err)));
  }

  useEffect(load, [snapshotId]);

  const projectId = detail?.project_id ?? projectHint;
  const videoSrc = `/api/snapshots/${snapshotId}/render.mp4`;

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">
          {detail?.project_name ?? "Saved video"}
        </h1>
        <Link to="/dashboard" className="text-sm text-slate-600 hover:text-slate-900">
          ← Dashboard
        </Link>
      </header>
      <p className="mt-1 text-xs text-slate-500">
        Snapshot <span className="font-mono">{snapshotId}</span> — loaded from the
        saved render and diagnostics, so it works after a restart too.
      </p>
      {loadError && (
        <p role="alert" className="mt-3 rounded bg-red-50 px-3 py-2 text-xs text-red-700">
          {loadError}
        </p>
      )}

      {detail && (
        <section className="mt-4 space-y-1 text-xs text-slate-600" data-testid="refine-chain">
          {detail.parent_snapshot_id && (
            <p>
              Refined from{" "}
              <Link
                to={`/snapshots/${detail.parent_snapshot_id}/inspect?project=${detail.project_id}`}
                className="font-mono text-slate-800 underline"
              >
                {detail.parent_snapshot_id}
              </Link>
              {detail.refinement_message && <>: “{detail.refinement_message}”</>}
              {detail.refinement_interpretation && (
                <span className="text-slate-400"> — {detail.refinement_interpretation}</span>
              )}
            </p>
          )}
          {detail.children.length > 0 && (
            <p>
              Refined versions:{" "}
              {detail.children.map((child, i) => (
                <span key={child}>
                  {i > 0 && ", "}
                  <Link
                    to={`/snapshots/${child}/inspect?project=${detail.project_id}`}
                    className="font-mono text-slate-800 underline"
                  >
                    {child}
                  </Link>
                </span>
              ))}
            </p>
          )}
          {detail.publishes.length > 0 && (
            <p className="flex flex-wrap items-center gap-2">
              <PublishBadges publishes={detail.publishes} />
            </p>
          )}
        </section>
      )}

      {videoOk && (
        <div className="mt-6 overflow-hidden rounded-lg border border-slate-300 bg-black">
          <video
            src={videoSrc}
            controls
            className="block aspect-video w-full"
            data-testid="inspect-video"
            onError={() => setVideoOk(false)}
          />
        </div>
      )}

      {detail?.has_render && projectId && (
        <SnapshotActions snapshotId={snapshotId} projectId={projectId} onPublished={load} />
      )}
      {detail && !detail.has_render && (
        <p className="mt-6 text-xs text-slate-500">
          This snapshot has no finished render on disk, so it can't be refined or published.
        </p>
      )}

      <section className="mt-8 rounded border border-slate-200 bg-slate-50 p-4">
        <h2 className="text-sm font-semibold text-slate-700">Per-phase decisions</h2>
        <p className="mt-1 text-xs text-slate-500">
          Open any phase to see exactly what was decided — kept/dropped media and
          why, the trip cast, the narrative selection, and the final clips. Click
          “Feedback” on anything to mark it correct / incorrect / should-be-different
          and add a note. Your input is saved for Claude to pick up in a later session.
        </p>
        <DiagnosticsPanel snapshotId={snapshotId} projectId={projectId} />
      </section>
    </main>
  );
}
