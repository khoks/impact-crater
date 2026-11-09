// SnapshotActions — Refine and Approve & publish for one snapshot (S-3.5.5).
// Shared by JobPreview (a just-finished job) and SnapshotInspect (any saved
// snapshot, parent or refined child), so both pages publish and refine the
// same way. Loads the connector status and the publish defaults itself.

import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { postRefine, type RefineResponse } from "../api/jobs";
import {
  ALL_PLATFORMS,
  DRY_RUN_CHECKS,
  PLATFORM_LABELS,
  PLATFORM_VISIBILITIES,
  fetchAllConnectorsStatus,
  fetchPublishDefaults,
  publishSnapshot,
  setupGuideUrl,
  type AllConnectorsStatus,
  type Platform,
  type PublishResponse,
  type Visibility,
} from "../api/publish";

interface Props {
  snapshotId: string;
  projectId: string;
  fallbackTitle?: string;
  // Rendered at the left of the action row (JobPreview's diagnostics toggle).
  leading?: ReactNode;
  onPublished?: (result: PublishResponse) => void;
}

export default function SnapshotActions({
  snapshotId,
  projectId,
  fallbackTitle = "Story Video",
  leading,
  onPublished,
}: Props) {
  const [refineOpen, setRefineOpen] = useState(false);
  const [refineMessage, setRefineMessage] = useState("");
  const [refineResult, setRefineResult] = useState<RefineResponse | null>(null);
  const [refining, setRefining] = useState(false);
  const [refineError, setRefineError] = useState<string | null>(null);

  const [publishOpen, setPublishOpen] = useState(false);
  const [connectorsStatus, setConnectorsStatus] = useState<AllConnectorsStatus | null>(null);
  const [publishPlatform, setPublishPlatform] = useState<Platform>("youtube");
  const [publishTitle, setPublishTitle] = useState(fallbackTitle);
  const [publishDescription, setPublishDescription] = useState("");
  const [publishVisibility, setPublishVisibility] = useState<Visibility>("private");
  const [publishing, setPublishing] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [publishResult, setPublishResult] = useState<PublishResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    // Title card text, project name or the brief's first sentence; the brief as
    // the description. The user edits both before publishing.
    fetchPublishDefaults(snapshotId)
      .then((d) => {
        if (cancelled || typeof d.title !== "string") return;
        setPublishTitle(d.title);
        setPublishDescription(d.description);
      })
      .catch(() => {
        /* keep the fallback title */
      });
    // Failure is non-fatal: the modal still opens, just without the
    // per-platform connected badges.
    fetchAllConnectorsStatus()
      .then((s) => {
        if (!cancelled) setConnectorsStatus(s);
      })
      .catch(() => {
        if (!cancelled) {
          setConnectorsStatus({
            platforms: ALL_PLATFORMS.map((p) => ({ platform: p, connected: false })),
            dry_run: true,
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [snapshotId]);

  async function onRefine() {
    if (!refineMessage.trim()) return;
    setRefining(true);
    setRefineError(null);
    setRefineResult(null);
    try {
      setRefineResult(await postRefine(snapshotId, refineMessage.trim()));
    } catch (err) {
      setRefineError(err instanceof Error ? err.message : String(err));
    } finally {
      setRefining(false);
    }
  }

  async function onPublish() {
    if (!publishTitle.trim()) return;
    setPublishing(true);
    setPublishError(null);
    setPublishResult(null);
    try {
      const result = await publishSnapshot(snapshotId, {
        title: publishTitle.trim(),
        description: publishDescription.trim(),
        visibility: publishVisibility,
        platform: publishPlatform,
      });
      setPublishResult(result);
      onPublished?.(result);
    } catch (err) {
      setPublishError(err instanceof Error ? err.message : String(err));
    } finally {
      setPublishing(false);
    }
  }

  return (
    <>
      <div className="mt-8 flex items-center justify-end gap-3">
        {leading}
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
          onClick={() => {
            setPublishOpen((v) => !v);
            setPublishResult(null);
            setPublishError(null);
          }}
          className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
        >
          {publishOpen ? "Cancel" : "Approve & publish"}
        </button>
      </div>
      <p className="mt-2 text-right text-xs text-slate-400">
        {approveCaption(connectorsStatus)}
      </p>

      {refineOpen && (
        <section className="mt-6 rounded border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-700">Refine</h2>
          <p className="mt-1 text-xs text-slate-500">
            Type what you'd change ("more landscape, less faces"; "punchier
            opener"; etc). Impact Crater will decide whether to re-compose the
            story with your note folded in, or explain why it isn't possible
            with the current shots. The refined video is saved as a new version;
            this one stays as it is.
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
              <p className="text-slate-700">{refineResult.interpretation}</p>
              {refineResult.reserve_destinations.length > 0 && (
                <p className="mt-1 text-slate-600">
                  Guaranteeing coverage of:{" "}
                  <span className="font-medium">{refineResult.reserve_destinations.join(", ")}</span>
                </p>
              )}
              {refineResult.brief_addendum && (
                <p className="mt-1 text-slate-600">
                  Story steer: <em>{refineResult.brief_addendum}</em>
                </p>
              )}
              {refineResult.explanation && (
                <p className="mt-2 text-amber-700">{refineResult.explanation}</p>
              )}
              {refineResult.rendered && refineResult.new_snapshot_id ? (
                <Link
                  to={`/snapshots/${refineResult.new_snapshot_id}/inspect?project=${projectId}`}
                  className="mt-2 inline-block font-medium text-emerald-700 hover:underline"
                >
                  ✓ Re-rendered — view the updated video →
                </Link>
              ) : refineResult.explanation ? null : (
                <p className="mt-2 text-slate-500">
                  Interpreted, but nothing to re-render (no source media available for this snapshot).
                </p>
              )}
            </div>
          )}
        </section>
      )}

      {publishOpen && (
        <section className="mt-6 rounded border border-slate-200 bg-white p-4">
          <div className="flex items-baseline justify-between">
            <h2 className="text-sm font-semibold text-slate-700">
              Publish to {PLATFORM_LABELS[publishPlatform]}
            </h2>
            {connectorsStatus?.dry_run && (
              <span
                className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-800"
                title="Dry-run is on: nothing is posted. Switch it off in Settings → Publishing."
              >
                DRY-RUN
              </span>
            )}
          </div>

          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            {ALL_PLATFORMS.map((p) => {
              const status = connectorsStatus?.platforms.find((s) => s.platform === p);
              const isSelected = publishPlatform === p;
              return (
                <button
                  key={p}
                  type="button"
                  onClick={() => {
                    setPublishPlatform(p);
                    if (!PLATFORM_VISIBILITIES[p].includes(publishVisibility)) {
                      setPublishVisibility(PLATFORM_VISIBILITIES[p][0]);
                    }
                    setPublishResult(null);
                    setPublishError(null);
                  }}
                  className={
                    "rounded border px-3 py-1 transition " +
                    (isSelected
                      ? "border-slate-900 bg-slate-900 text-white"
                      : "border-slate-300 bg-white hover:border-slate-500")
                  }
                >
                  {PLATFORM_LABELS[p]}
                  {status && (
                    <span
                      className={
                        "ml-2 inline-block h-1.5 w-1.5 rounded-full align-middle " +
                        (status.connected ? "bg-emerald-400" : "bg-slate-300")
                      }
                      aria-hidden
                      title={status.connected ? "credentials set" : "credentials not set"}
                    />
                  )}
                </button>
              );
            })}
          </div>

          {connectorsStatus !== null && (() => {
            const status = connectorsStatus.platforms.find(
              (s) => s.platform === publishPlatform
            );
            const label = PLATFORM_LABELS[publishPlatform];
            const guide = (
              <a
                href={setupGuideUrl(publishPlatform)}
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                {label} setup guide
              </a>
            );
            if (connectorsStatus.dry_run) {
              return (
                <p className="mt-3 rounded bg-amber-50 px-3 py-2 text-xs text-amber-800">
                  {DRY_RUN_CHECKS[publishPlatform]}{" "}
                  {status?.connected
                    ? `${label} credentials are set.`
                    : <>{label} credentials are not set; see the {guide}.</>}
                </p>
              );
            }
            if (status?.connected) {
              return (
                <p className="mt-3 rounded bg-red-50 px-3 py-2 text-xs text-red-800">
                  Dry-run is off: this publish posts to {label} for real.
                </p>
              );
            }
            return (
              <p className="mt-3 rounded bg-amber-50 px-3 py-2 text-xs text-amber-800">
                Dry-run is off, but {label} credentials are not set, so the publish will
                fail. See the {guide}.
              </p>
            );
          })()}

          {publishResult ? (
            <div
              className={
                "mt-3 rounded p-3 text-xs " +
                (publishResult.dry_run
                  ? "bg-amber-50 text-amber-900"
                  : "bg-emerald-50 text-emerald-900")
              }
            >
              <p className="font-semibold">
                {publishResult.dry_run ? "Dry-run validated." : "Published."}
              </p>
              <p className="mt-1">
                Platform: <span className="font-mono">{publishResult.platform}</span>
              </p>
              <p className="mt-1">
                {publishResult.dry_run ? "Would publish to: " : "External URL: "}
                <a
                  href={publishResult.external_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline"
                >
                  {publishResult.external_url}
                </a>
              </p>
              <p className="mt-1">
                Visibility: <span className="font-mono">{publishResult.visibility}</span>
              </p>
              <p className="mt-1">
                Audit token:{" "}
                <span className="font-mono">{publishResult.audit_token}</span>
              </p>
            </div>
          ) : (
            <>
              <div className="mt-3">
                <label className="block text-xs font-medium text-slate-700">Title</label>
                <input
                  type="text"
                  value={publishTitle}
                  onChange={(e) => setPublishTitle(e.target.value)}
                  maxLength={200}
                  className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
                />
              </div>
              <div className="mt-3">
                <label className="block text-xs font-medium text-slate-700">
                  Description (optional)
                </label>
                <textarea
                  value={publishDescription}
                  onChange={(e) => setPublishDescription(e.target.value)}
                  rows={3}
                  className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
                  placeholder={
                    publishPlatform === "instagram"
                      ? "Becomes part of the Instagram caption (with title)."
                      : "What's the video about?"
                  }
                />
              </div>
              <div className="mt-3">
                <label className="block text-xs font-medium text-slate-700">Visibility</label>
                <div className="mt-1 flex gap-4 text-xs">
                  {PLATFORM_VISIBILITIES[publishPlatform].map((v) => (
                    <label key={v} className="flex items-center gap-1">
                      <input
                        type="radio"
                        name="visibility"
                        value={v}
                        checked={publishVisibility === v}
                        onChange={() => setPublishVisibility(v)}
                      />
                      <span>
                        {publishPlatform === "facebook" && v === "unlisted" ? "draft" : v}
                      </span>
                    </label>
                  ))}
                </div>
                {publishPlatform === "instagram" && (
                  <p className="mt-1 text-[11px] text-slate-500">
                    Instagram Reels are always public.
                  </p>
                )}
                {publishPlatform === "facebook" && publishVisibility === "unlisted" && (
                  <p className="mt-1 text-[11px] text-slate-500">
                    Saved as a draft in your Page's drafts, not shown to anyone.
                  </p>
                )}
              </div>
              <div className="mt-3 flex justify-end">
                <button
                  type="button"
                  onClick={onPublish}
                  disabled={publishing || !publishTitle.trim()}
                  className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-400"
                >
                  {publishing
                    ? "Publishing…"
                    : `Publish to ${PLATFORM_LABELS[publishPlatform]}`}
                </button>
              </div>
            </>
          )}

          {publishError && (
            <p role="alert" className="mt-3 rounded bg-red-50 px-3 py-2 text-xs text-red-700">
              {publishError}
            </p>
          )}
        </section>
      )}
    </>
  );
}

function approveCaption(status: AllConnectorsStatus | null): string {
  if (status === null || status.dry_run) {
    return "Dry-run is on: Approve checks the request and records it in the audit log. Nothing is posted.";
  }
  const connected = status.platforms.filter((p) => p.connected).map((p) => PLATFORM_LABELS[p.platform]);
  if (connected.length === 0) {
    return "Dry-run is off, but no platform is connected yet, so nothing can be posted.";
  }
  return `Dry-run is off: Approve posts this video to the platform you pick (connected: ${connected.join(", ")}).`;
}
