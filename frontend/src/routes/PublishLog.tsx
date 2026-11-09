// Publish log (S-3.3.9) — every publish attempt the app has made, dry-runs and
// live posts, across all projects, newest first, with whether the video file
// on disk is still the one each attempt approved. Reads GET /api/audit.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { fetchAuditPage, type AuditPage, type RenderCheck } from "../api/audit";

const PAGE_SIZE = 25;

const RENDER_CHECK: Record<RenderCheck, { label: string; tone: string; title: string }> = {
  match: {
    label: "file matches",
    tone: "text-emerald-700",
    title: "The video on disk is the exact file this attempt approved.",
  },
  changed: {
    label: "file changed since",
    tone: "text-rose-700",
    title: "The video on disk is no longer the file this attempt approved.",
  },
  missing: {
    label: "file missing",
    tone: "text-amber-700",
    title: "The approved video is no longer on disk.",
  },
  unrecorded: {
    label: "not recorded",
    tone: "text-slate-400",
    title: "This attempt predates recording which file was approved.",
  },
};

function formatTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
}

export default function PublishLog() {
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<AuditPage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchAuditPage(PAGE_SIZE, offset)
      .then((p) => {
        if (!cancelled) setPage(p);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [offset]);

  return (
    <main className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Publish log</h1>
        <Link to="/dashboard" className="text-sm text-slate-600 hover:text-slate-900">
          ← Dashboard
        </Link>
      </header>
      <p className="mt-1 text-xs text-slate-500">
        Every publish attempt, newest first. A dry-run checks the request and records it
        here but posts nothing; a live row is a real post.
      </p>

      {error && (
        <p role="alert" className="mt-4 rounded bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </p>
      )}
      {page && page.total === 0 && (
        <p className="mt-8 text-sm text-slate-600">Nothing has been published yet.</p>
      )}

      {page && page.items.length > 0 && (
        <ul className="mt-6 space-y-3">
          {page.items.map((row) => {
            const check = RENDER_CHECK[row.render_check];
            return (
              <li
                key={row.id}
                className="rounded border border-slate-200 bg-white px-4 py-3 text-sm"
                data-testid={`audit-row-${row.id}`}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={
                      "rounded-full px-2.5 py-0.5 text-xs font-medium " +
                      (row.dry_run
                        ? "bg-amber-100 text-amber-800"
                        : "bg-emerald-600 text-white")
                    }
                  >
                    {row.dry_run ? "Dry-run" : "Live"}
                  </span>
                  <span className="font-medium text-slate-900">{row.platform}</span>
                  {row.visibility && (
                    <span className="text-xs text-slate-500">· {row.visibility}</span>
                  )}
                  <span className="ml-auto text-xs text-slate-400">
                    {formatTime(row.published_at)}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-600">
                  {row.project_name} ·{" "}
                  <Link
                    to={`/snapshots/${row.snapshot_id}/inspect?project=${row.project_id}`}
                    className="font-mono underline hover:text-slate-900"
                  >
                    {row.snapshot_id}
                  </Link>
                </p>
                <p className="mt-1 break-all text-xs text-slate-600">
                  {row.dry_run ? (
                    <>Would publish to {row.external_url}</>
                  ) : (
                    <a
                      href={row.external_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-emerald-700 underline"
                    >
                      {row.external_url}
                    </a>
                  )}
                </p>
                <p className="mt-1 flex flex-wrap gap-x-3 text-[11px] text-slate-500">
                  <span>response {row.response_code ?? "—"}</span>
                  <span>
                    approval <span className="font-mono">{row.approval_token}</span>
                  </span>
                  <span>
                    render{" "}
                    <span className="font-mono" title={row.render_content_hash}>
                      {row.render_content_hash ? row.render_content_hash.slice(0, 12) : "—"}
                    </span>{" "}
                    <span className={check.tone} title={check.title}>
                      ({check.label})
                    </span>
                  </span>
                </p>
              </li>
            );
          })}
        </ul>
      )}

      {page && page.total > PAGE_SIZE && (
        <nav className="mt-6 flex items-center justify-between text-sm">
          <button
            type="button"
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            disabled={offset === 0}
            className="rounded border border-slate-300 px-3 py-1.5 text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
          >
            ← Newer
          </button>
          <span className="text-xs text-slate-500">
            {offset + 1}–{Math.min(offset + PAGE_SIZE, page.total)} of {page.total}
          </span>
          <button
            type="button"
            onClick={() => setOffset(offset + PAGE_SIZE)}
            disabled={offset + PAGE_SIZE >= page.total}
            className="rounded border border-slate-300 px-3 py-1.5 text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Older →
          </button>
        </nav>
      )}
    </main>
  );
}
