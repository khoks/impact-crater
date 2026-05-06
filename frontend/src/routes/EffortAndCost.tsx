// Effort-level picker + cost preview + Submit. Lands the user on
// /jobs/:job_id once the backend accepts the submission.

import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  fetchCostPreview,
  fetchEffortLevels,
  submitJob,
  type CostPreviewResponse,
  type EffortLevel,
  type EffortLevelsResponse,
} from "../api/jobs";
import { useNewProjectStore } from "../stores/newProjectStore";

export default function EffortAndCost() {
  const navigate = useNavigate();
  const draft = useNewProjectStore((s) => s.draft);
  const reset = useNewProjectStore((s) => s.reset);

  const [levels, setLevels] = useState<EffortLevelsResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [preview, setPreview] = useState<CostPreviewResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Bounce back to the form if the user landed here without a draft.
  useEffect(() => {
    if (draft === null) {
      navigate("/projects/new", { replace: true });
    }
  }, [draft, navigate]);

  useEffect(() => {
    if (draft === null) return;
    let cancelled = false;
    Promise.all([
      fetchEffortLevels(),
      fetchCostPreview({
        media_count: draft.scanned_media_paths.length,
        target_duration_seconds: draft.target_duration_seconds,
      }),
    ])
      .then(([lvls, p]) => {
        if (cancelled) return;
        setLevels(lvls);
        setPreview(p);
        setSelectedId(lvls.recommended_level_id ?? lvls.levels[0]?.id ?? null);
      })
      .catch((err) => {
        if (cancelled) return;
        setLoadError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [draft]);

  if (draft === null) return null;

  async function onSubmit() {
    if (draft === null) return;
    setSubmitError(null);
    setSubmitting(true);
    try {
      const result = await submitJob({
        media_paths: draft.scanned_media_paths,
        brief: draft.brief,
        target_duration: draft.target_duration_seconds,
        audio_path: draft.audio_path,
      });
      reset();
      navigate(`/jobs/${result.job_id}`, { replace: true });
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  const mediaCount = draft.scanned_media_paths.length;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">
          Effort & cost preview
        </h1>
        <Link
          to="/projects/new"
          className="text-sm text-slate-500 hover:text-slate-900"
        >
          Back
        </Link>
      </header>

      <p className="mt-2 text-sm text-slate-600">
        {mediaCount} media item{mediaCount === 1 ? "" : "s"} ·{" "}
        {draft.target_duration_seconds}s target ·{" "}
        <span className="font-mono text-xs">{draft.folder_path}</span>
      </p>

      {loadError && (
        <p role="alert" className="mt-4 rounded bg-red-50 px-4 py-2 text-sm text-red-700">
          {loadError}
        </p>
      )}

      {levels && (
        <section className="mt-6 grid gap-3 sm:grid-cols-3">
          {levels.levels.map((lvl) => (
            <LevelCard
              key={lvl.id}
              level={lvl}
              selected={lvl.id === selectedId}
              recommended={lvl.id === levels.recommended_level_id}
              onSelect={() => setSelectedId(lvl.id)}
              mediaCount={mediaCount}
            />
          ))}
        </section>
      )}

      {preview && (
        <section className="mt-6 rounded border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-700">
            Estimated cost for this job
          </h2>
          <p className="mt-1 text-2xl font-semibold">
            ${preview.estimated_cost_usd_low.toFixed(2)} – $
            {preview.estimated_cost_usd_high.toFixed(2)}
          </p>
          <dl className="mt-3 grid gap-1 text-xs text-slate-600 sm:grid-cols-2">
            {Object.entries(preview.cost_by_tier_usd).map(([tier, cost]) => (
              <div key={tier} className="flex justify-between gap-2">
                <dt className="font-mono">{tier}</dt>
                <dd>${cost.toFixed(4)}</dd>
              </div>
            ))}
          </dl>
          {preview.today_remaining_usd !== null && (
            <p className="mt-3 text-xs text-slate-500">
              Today's remaining budget: $
              {preview.today_remaining_usd.toFixed(2)}
            </p>
          )}
          {!preview.fits_today_budget && (
            <p className="mt-3 rounded bg-amber-50 px-3 py-2 text-xs text-amber-800">
              {preview.blocking_reason === "no_total_cap_configured"
                ? "Spend cap isn't configured. Set one in Settings before starting a job."
                : "Estimated high-end exceeds today's remaining budget."}
            </p>
          )}
        </section>
      )}

      {selectedId && levels && (
        <UpgradeHint level={levels.levels.find((l) => l.id === selectedId)!} mediaCount={mediaCount} />
      )}

      {submitError && (
        <p role="alert" className="mt-4 rounded bg-red-50 px-4 py-2 text-sm text-red-700">
          {submitError}
        </p>
      )}

      <div className="mt-6 flex items-center justify-end gap-3">
        <Link
          to="/projects/new"
          className="text-sm font-medium text-slate-600 hover:text-slate-900"
        >
          Edit details
        </Link>
        <button
          type="button"
          onClick={onSubmit}
          disabled={
            submitting ||
            !selectedId ||
            (preview !== null && !preview.fits_today_budget)
          }
          className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          {submitting ? "Submitting…" : "Start Job"}
        </button>
      </div>
    </main>
  );
}

function LevelCard({
  level,
  selected,
  recommended,
  onSelect,
  mediaCount,
}: {
  level: EffortLevel;
  selected: boolean;
  recommended: boolean;
  onSelect: () => void;
  mediaCount: number;
}) {
  const overCap = mediaCount > level.photo_cap + level.video_cap;
  return (
    <button
      type="button"
      onClick={onSelect}
      className={
        "rounded border p-4 text-left transition " +
        (selected
          ? "border-slate-900 bg-slate-900 text-white"
          : "border-slate-200 bg-white hover:border-slate-400")
      }
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">{level.label}</h3>
        {recommended && (
          <span
            className={
              "rounded px-1.5 py-0.5 text-[10px] font-medium " +
              (selected ? "bg-emerald-300 text-emerald-900" : "bg-emerald-100 text-emerald-700")
            }
          >
            recommended
          </span>
        )}
      </div>
      <p
        className={
          "mt-2 text-xs " + (selected ? "text-slate-200" : "text-slate-600")
        }
      >
        {level.description}
      </p>
      <dl className="mt-3 space-y-1 text-xs">
        <Row label="Photo cap" value={String(level.photo_cap)} dark={selected} />
        <Row label="Video cap" value={String(level.video_cap)} dark={selected} />
        <Row
          label="Cost"
          value={`$${level.estimated_cost_usd_low.toFixed(2)}–$${level.estimated_cost_usd_high.toFixed(2)}`}
          dark={selected}
        />
      </dl>
      <p
        className={
          "mt-2 text-[11px] " +
          (level.fits_today_budget
            ? selected
              ? "text-emerald-300"
              : "text-emerald-700"
            : selected
              ? "text-amber-300"
              : "text-amber-700")
        }
      >
        {level.fits_today_budget ? "fits today's budget" : "exceeds today's budget"}
      </p>
      {overCap && (
        <p
          className={
            "mt-1 text-[11px] " +
            (selected ? "text-amber-300" : "text-amber-700")
          }
        >
          your media count exceeds this level's cap
        </p>
      )}
    </button>
  );
}

function Row({
  label,
  value,
  dark,
}: {
  label: string;
  value: string;
  dark: boolean;
}) {
  return (
    <div className="flex justify-between">
      <dt className={dark ? "text-slate-300" : "text-slate-500"}>{label}</dt>
      <dd className="font-mono">{value}</dd>
    </div>
  );
}

function UpgradeHint({
  level,
  mediaCount,
}: {
  level: EffortLevel;
  mediaCount: number;
}) {
  if (mediaCount <= level.photo_cap + level.video_cap) return null;
  return (
    <p className="mt-4 rounded bg-amber-50 px-3 py-2 text-xs text-amber-800">
      You picked {mediaCount} media items but {level.label} caps at{" "}
      {level.photo_cap + level.video_cap}. Either pick a higher level (raise
      your spend cap in Settings if needed) or use a smaller folder.
    </p>
  );
}
