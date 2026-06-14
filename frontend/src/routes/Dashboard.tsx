// Dashboard — landing page after the first-time-setup wizard.
//
// Three surfaces (S-2.9.2):
//   - "Jobs this session" — the in-memory registry (running/queued first);
//     links into the live JobInProgress page. Lost on server restart.
//   - "Projects" — persistent rows from SQLite with their snapshots;
//     finished renders play inline via /api/snapshots/{id}/render.mp4.
//   - "New Project" primary action → /projects/new

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import type { JobSnapshot } from "../api/jobs";
import { listJobs, listProjects, type ProjectSummary } from "../api/projects";

const JOB_STATE_STYLES: Record<JobSnapshot["state"], string> = {
  running: "bg-sky-100 text-sky-800",
  queued: "bg-slate-200 text-slate-700",
  succeeded: "bg-emerald-100 text-emerald-800",
  failed: "bg-rose-100 text-rose-800",
  cancelled: "bg-amber-100 text-amber-800",
};

const RENDER_STATUS_STYLES: Record<string, string> = {
  success: "bg-emerald-100 text-emerald-800",
  failure: "bg-rose-100 text-rose-800",
  in_progress: "bg-sky-100 text-sky-800",
  pending: "bg-slate-200 text-slate-700",
  cancelled: "bg-amber-100 text-amber-800",
};

function formatTimestamp(iso: string): string {
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Dashboard() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [jobs, setJobs] = useState<JobSnapshot[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [playingSnapshot, setPlayingSnapshot] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([listProjects(), listJobs()]).then(
      ([projectsResult, jobsResult]) => {
        if (cancelled) return;
        if (projectsResult.status === "fulfilled") {
          setProjects(projectsResult.value);
        }
        if (jobsResult.status === "fulfilled") {
          setJobs(jobsResult.value);
        }
        setLoaded(true);
      }
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const hasAnything = projects.length > 0 || jobs.length > 0;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <header className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold text-slate-900">Impact Crater</h1>
        <nav className="flex items-center gap-4 text-sm font-medium text-slate-600">
          <Link to="/workplan" className="hover:text-slate-900">
            Workplan
          </Link>
          <Link to="/feedback" className="hover:text-slate-900">
            Feedback
          </Link>
          <Link to="/people" className="hover:text-slate-900">
            People
          </Link>
          <Link to="/settings" className="hover:text-slate-900">
            Settings
          </Link>
        </nav>
      </header>

      <section className="mt-8 rounded-xl border border-slate-200 bg-gradient-to-br from-white to-slate-50 p-6">
        <h2 className="text-xl font-semibold text-slate-900">
          Turn your photos and videos into a video worth sharing — in one click.
        </h2>
        <p className="mt-2 max-w-2xl text-sm text-slate-600">
          Drop in your media, describe the video you want in your own words and
          where you'll post it, and hit Create. The AI does the rest — and shows
          you a preview before anything is published.
        </p>
        <Link
          to="/projects/new"
          className="mt-4 inline-block rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700"
        >
          Create a video
        </Link>
      </section>

      {loaded && !hasAnything && (
        <section className="mt-10">
          <p className="text-slate-600">No projects yet.</p>
        </section>
      )}

      {jobs.length > 0 && (
        <section className="mt-10">
          <h2 className="text-lg font-semibold text-slate-900">
            Jobs this session
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Live progress for jobs submitted since the server started.
          </p>
          <ul className="mt-3 space-y-2">
            {jobs.map((job) => (
              <li key={job.job_id}>
                <Link
                  to={`/jobs/${job.job_id}`}
                  className="flex items-center justify-between gap-3 rounded border border-slate-200 bg-white px-4 py-3 hover:border-slate-300 hover:bg-slate-50"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-slate-900">
                      {job.project_name || job.project_id}
                    </span>
                    <span className="block truncate text-xs text-slate-500">
                      {job.brief || "(no brief)"}
                    </span>
                  </span>
                  <span
                    className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${JOB_STATE_STYLES[job.state]}`}
                    title={job.failure_reason ?? undefined}
                  >
                    {job.state}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {projects.length > 0 && (
        <section className="mt-10">
          <h2 className="text-lg font-semibold text-slate-900">Projects</h2>
          <ul className="mt-3 space-y-3">
            {projects.map((project) => (
              <li
                key={project.id}
                className="rounded border border-slate-200 bg-white px-4 py-3"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="truncate text-sm font-medium text-slate-900">
                    {project.name}
                  </span>
                  <span className="shrink-0 text-xs text-slate-400">
                    {formatTimestamp(project.created_at)}
                  </span>
                </div>
                {project.brief && (
                  <p className="mt-1 line-clamp-2 text-xs text-slate-500">
                    {project.brief}
                  </p>
                )}
                {project.snapshots.length === 0 ? (
                  <p className="mt-2 text-xs text-slate-400">
                    No renders yet.
                  </p>
                ) : (
                  <ul className="mt-2 space-y-1.5">
                    {project.snapshots.map((snap) => (
                      <li key={snap.id} className="text-sm">
                        <div className="flex items-center gap-3">
                          <span
                            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${RENDER_STATUS_STYLES[snap.render_status] ?? "bg-slate-200 text-slate-700"}`}
                          >
                            {snap.render_status}
                          </span>
                          <span className="text-xs text-slate-400">
                            {formatTimestamp(snap.created_at)}
                          </span>
                          {snap.has_render && (
                            <button
                              type="button"
                              onClick={() =>
                                setPlayingSnapshot(
                                  playingSnapshot === snap.id ? null : snap.id
                                )
                              }
                              className="text-xs font-medium text-emerald-700 hover:text-emerald-900"
                            >
                              {playingSnapshot === snap.id ? "Hide" : "▶ Watch"}
                            </button>
                          )}
                        </div>
                        {playingSnapshot === snap.id && (
                          <video
                            controls
                            autoPlay
                            className="mt-2 w-full rounded border border-slate-200 bg-black"
                            src={`/api/snapshots/${snap.id}/render.mp4`}
                          />
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
