// A-024 — developer workplan tracker. Renders the in-repo work hierarchy
// (Initiative → Epic → Story → Task) maintained since project start, grouped
// by phase (MVP / v1 / v2 / v3), with status badges and editable priority.
//
// Status is read-only (the project/ markdown is the source of truth, written
// only by the work-tracker skill via PRs). Priority edits are stored as
// overrides and reconciled into the markdown by a later Claude session.

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  fetchWorkplan,
  patchWorkplanItem,
  type Priority,
  type WorkItem,
  type Workplan,
} from "../api/trackers";

const PRIORITIES: Priority[] = ["P0", "P1", "P2", "P3"];

const PHASE_ORDER = ["scaffolding", "mvp", "v1", "v2", "v3", "unknown"];
const PHASE_LABEL: Record<string, string> = {
  scaffolding: "Scaffolding",
  mvp: "MVP",
  v1: "v1",
  v2: "v2",
  v3: "v3",
  unknown: "Unphased",
};

const STATUS_TONE: Record<string, string> = {
  done: "bg-emerald-100 text-emerald-800",
  "in-progress": "bg-sky-100 text-sky-800",
  review: "bg-amber-100 text-amber-800",
  ready: "bg-indigo-100 text-indigo-800",
  todo: "bg-slate-200 text-slate-600",
  blocked: "bg-rose-100 text-rose-800",
  canceled: "bg-slate-200 text-slate-400 line-through",
};

const TYPE_INDENT: Record<string, string> = {
  initiative: "",
  epic: "ml-4",
  story: "ml-10",
  task: "ml-16",
};

export default function WorkplanTracker() {
  const [plan, setPlan] = useState<Workplan | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchWorkplan()
      .then(setPlan)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  // Hierarchical order: each item followed by its descendants (by parent).
  const ordered = useMemo(() => (plan ? orderHierarchically(plan.items) : []), [plan]);

  async function onPriority(id: string, priority: Priority) {
    await patchWorkplanItem(id, { priority });
    setPlan((prev) =>
      prev
        ? {
            ...prev,
            items: prev.items.map((it) =>
              it.id === id ? { ...it, priority, priority_overridden: true } : it
            ),
          }
        : prev
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Workplan</h1>
        <Link to="/dashboard" className="text-sm text-slate-600 hover:text-slate-900">
          ← Dashboard
        </Link>
      </header>
      <p className="mt-1 text-xs text-slate-500">
        The MVP → v1 → v2 → v3 plan (Initiative → Epic → Story → Task). Status is read-only
        (Claude maintains it); change priority here and it's reconciled into the tracker on the
        next work-tracker pass.
      </p>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
      {plan && !plan.available && (
        <p className="mt-6 rounded bg-amber-50 px-3 py-2 text-sm text-amber-800">
          The <code>project/</code> tracker isn't available in this install (it ships with the
          source repo, not the packaged app).
        </p>
      )}

      {plan?.available && (
        <>
          <section className="mt-4 flex flex-wrap gap-4 rounded border border-slate-200 bg-white p-3 text-xs">
            <Rollup title="By status" counts={plan.counts_by_status} tones={STATUS_TONE} />
            <Rollup title="By phase" counts={plan.counts_by_phase} labels={PHASE_LABEL} />
          </section>

          <ul className="mt-4 space-y-1">
            {ordered.map((it) => (
              <li
                key={it.id}
                className={`flex items-center gap-2 rounded border border-slate-100 bg-white px-3 py-1.5 ${TYPE_INDENT[it.type] ?? ""}`}
              >
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${STATUS_TONE[it.status] ?? "bg-slate-100 text-slate-600"}`}
                >
                  {it.status}
                </span>
                <span className="shrink-0 font-mono text-[11px] text-slate-400">{it.id}</span>
                <span
                  className={
                    "min-w-0 flex-1 truncate text-sm " +
                    (it.type === "initiative"
                      ? "font-semibold text-slate-900"
                      : it.type === "epic"
                        ? "font-medium text-slate-800"
                        : "text-slate-700")
                  }
                  title={it.title}
                >
                  {it.title}
                </span>
                <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">
                  {PHASE_LABEL[it.phase] ?? it.phase}
                </span>
                <select
                  value={it.priority}
                  onChange={(e) => onPriority(it.id, e.target.value as Priority)}
                  title={
                    it.priority_overridden
                      ? `override (markdown says ${it.markdown_priority})`
                      : "priority"
                  }
                  className={
                    "shrink-0 rounded border px-1 py-0.5 text-[11px] " +
                    (it.priority_overridden ? "border-amber-400 bg-amber-50" : "border-slate-300")
                  }
                >
                  {PRIORITIES.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}

function Rollup({
  title,
  counts,
  tones,
  labels,
}: {
  title: string;
  counts: Record<string, number>;
  tones?: Record<string, string>;
  labels?: Record<string, string>;
}) {
  return (
    <div>
      <p className="font-medium text-slate-600">{title}</p>
      <div className="mt-1 flex flex-wrap gap-1">
        {Object.entries(counts)
          .sort((a, b) => b[1] - a[1])
          .map(([k, n]) => (
            <span
              key={k}
              className={`rounded px-1.5 py-0.5 ${tones?.[k] ?? "bg-slate-100 text-slate-600"}`}
            >
              {labels?.[k] ?? k}: {n}
            </span>
          ))}
      </div>
    </div>
  );
}

// Depth-first by parent so each item is followed by its children; roots
// (initiatives / orphans) ordered by phase then id.
function orderHierarchically(items: WorkItem[]): WorkItem[] {
  const byParent = new Map<string | null, WorkItem[]>();
  for (const it of items) {
    const key = it.parent ?? null;
    if (!byParent.has(key)) byParent.set(key, []);
    byParent.get(key)!.push(it);
  }
  const ids = new Set(items.map((i) => i.id));
  const sortKey = (it: WorkItem) =>
    `${PHASE_ORDER.indexOf(it.phase).toString().padStart(2, "0")}-${it.id}`;

  const out: WorkItem[] = [];
  const visit = (it: WorkItem) => {
    out.push(it);
    (byParent.get(it.id) ?? []).sort((a, b) => (a.id < b.id ? -1 : 1)).forEach(visit);
  };
  // Roots: no parent, or parent missing from the set.
  items
    .filter((it) => !it.parent || !ids.has(it.parent))
    .sort((a, b) => (sortKey(a) < sortKey(b) ? -1 : 1))
    .forEach(visit);
  return out;
}
