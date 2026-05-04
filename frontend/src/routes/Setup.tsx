// First-time-setup wizard. Skeleton in S-2.1.4; the 6-step flow with
// react-hook-form + zod validation + /api/setup/* calls lands in S-2.1.5.

export default function Setup() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-3xl font-semibold text-slate-900">Welcome to Impact Crater</h1>
      <p className="mt-2 text-slate-600">
        First-time setup wizard. Full 6-step flow lands in S-2.1.5.
      </p>
      <div className="mt-8 rounded border border-slate-200 bg-white p-6 text-sm text-slate-600">
        <p>This wizard will walk you through:</p>
        <ol className="mt-3 list-decimal space-y-1 pl-5">
          <li>Anthropic API key</li>
          <li>Google API key</li>
          <li>Daily spend cap (total + per-provider)</li>
          <li>Storage location override (optional)</li>
          <li>Privacy posture preview</li>
          <li>Confirm & finish</li>
        </ol>
      </div>
    </main>
  );
}
