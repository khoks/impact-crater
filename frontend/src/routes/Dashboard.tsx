// Dashboard — landing page after the first-time-setup wizard. M3 surfaces:
//   - "New Project" primary action → /projects/new
//   - empty project list (real CRUD lands at M4 / E-2.5)
//   - top-right link to /settings

import { Link } from "react-router-dom";

export default function Dashboard() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <header className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold text-slate-900">Impact Crater</h1>
        <Link
          to="/settings"
          className="text-sm font-medium text-slate-600 hover:text-slate-900"
        >
          Settings
        </Link>
      </header>

      <section className="mt-8">
        <p className="text-slate-600">No projects yet.</p>
        <Link
          to="/projects/new"
          className="mt-6 inline-block rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
        >
          New Project
        </Link>
        <p className="mt-2 text-xs text-slate-400">
          Drop a folder of photos + an audio file; pick an effort level; get a
          Story Video preview.
        </p>
      </section>
    </main>
  );
}
