// Empty dashboard placeholder — the project list + new-project flow lands in M3.

export default function Dashboard() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-3xl font-semibold text-slate-900">Impact Crater</h1>
      <p className="mt-2 text-slate-600">No projects yet.</p>
      <button
        type="button"
        disabled
        className="mt-6 cursor-not-allowed rounded bg-slate-300 px-4 py-2 text-sm font-medium text-slate-600"
        title="Project creation lands in M3 (E-2.4 UI MVP loop closed)."
      >
        New Project
      </button>
      <p className="mt-2 text-xs text-slate-400">
        Project creation lands in M3 (E-2.4 UI MVP loop closed).
      </p>
    </main>
  );
}
