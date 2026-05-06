// Settings panel — edit API keys + spend caps post-setup-wizard.
// Privacy panel UI deferred to v1 per E-2.6 close-out (toggles are hard-coded
// to ADR-0016 defaults at MVP; the panel surfaces them read-only).

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  fetchSettingsSnapshot,
  updateSettings,
  type SettingsSnapshot,
} from "../api/settings";

export default function Settings() {
  const [snapshot, setSnapshot] = useState<SettingsSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  // Local form state — strings so we can leave fields empty (= unchanged).
  const [anthropicKey, setAnthropicKey] = useState("");
  const [googleKey, setGoogleKey] = useState("");
  const [totalCap, setTotalCap] = useState("");
  const [anthropicCap, setAnthropicCap] = useState("");
  const [googleCap, setGoogleCap] = useState("");

  async function refresh() {
    try {
      const s = await fetchSettingsSnapshot();
      setSnapshot(s);
      setTotalCap(s.spend_cap_total_usd?.toString() ?? "");
      setAnthropicCap(s.spend_cap_anthropic_usd?.toString() ?? "");
      setGoogleCap(s.spend_cap_google_usd?.toString() ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onSave() {
    setError(null);
    setSavedAt(null);
    setSaving(true);
    try {
      await updateSettings({
        anthropic_api_key: anthropicKey.trim() || null,
        google_api_key: googleKey.trim() || null,
        spend_cap_total_usd: totalCap ? Number.parseFloat(totalCap) : null,
        spend_cap_anthropic_usd: anthropicCap
          ? Number.parseFloat(anthropicCap)
          : null,
        spend_cap_google_usd: googleCap ? Number.parseFloat(googleCap) : null,
      });
      // Clear key fields so the user has to re-type to rotate again.
      setAnthropicKey("");
      setGoogleKey("");
      setSavedAt(new Date().toISOString());
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Settings</h1>
        <Link to="/dashboard" className="text-sm text-slate-500 hover:text-slate-900">
          ← Dashboard
        </Link>
      </header>

      {error && (
        <p role="alert" className="mt-4 rounded bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {snapshot === null ? (
        <p className="mt-6 text-slate-500">Loading…</p>
      ) : (
        <>
          <section className="mt-6 rounded border border-slate-200 bg-white p-6">
            <h2 className="text-sm font-semibold text-slate-700">API keys</h2>
            <p className="mt-1 text-xs text-slate-500">
              Stored Fernet-encrypted. Plaintext keys are never returned by the
              API; leave empty to keep the existing key.
            </p>

            <div className="mt-4 space-y-4">
              <KeyField
                label="Anthropic"
                placeholder={
                  snapshot.has_anthropic_key
                    ? "(set — leave empty to keep)"
                    : "sk-ant-..."
                }
                value={anthropicKey}
                onChange={setAnthropicKey}
                hasKey={snapshot.has_anthropic_key}
              />
              <KeyField
                label="Google"
                placeholder={
                  snapshot.has_google_key
                    ? "(set — leave empty to keep)"
                    : "AIza..."
                }
                value={googleKey}
                onChange={setGoogleKey}
                hasKey={snapshot.has_google_key}
              />
            </div>
          </section>

          <section className="mt-6 rounded border border-slate-200 bg-white p-6">
            <h2 className="text-sm font-semibold text-slate-700">Spend caps</h2>
            <p className="mt-1 text-xs text-slate-500">
              Today's spend: ${snapshot.today_total_spent_usd.toFixed(2)} total
            </p>
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              <CapField
                label="Total daily"
                placeholder="50.00"
                value={totalCap}
                onChange={setTotalCap}
              />
              <CapField
                label="Anthropic-only"
                placeholder="(optional)"
                value={anthropicCap}
                onChange={setAnthropicCap}
              />
              <CapField
                label="Google-only"
                placeholder="(optional)"
                value={googleCap}
                onChange={setGoogleCap}
              />
            </div>
          </section>

          <section className="mt-6 rounded border border-dashed border-slate-300 bg-slate-50 p-4 text-xs text-slate-600">
            <h2 className="text-sm font-semibold text-slate-700">Privacy posture</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              <li>Strip EXIF before sending to LLM — <strong>ON</strong></li>
              <li>Strip GPS only — <strong>ON</strong> (subset of full EXIF strip)</li>
              <li>Blur faces before sending to LLM — <strong>OFF</strong></li>
            </ul>
            <p className="mt-2">
              Locked to ADR-0016 defaults at MVP. Per-project toggles ship in
              v1 alongside the local-LLM destination (per E-2.6 close-out;
              toggling blur-faces=ON is meaningful only when a local provider
              is available to take face-data ops, otherwise jobs would degrade
              to recognized_persons=[]).
            </p>
          </section>

          <div className="mt-6 flex items-center justify-end gap-3">
            {savedAt && (
              <span className="text-xs text-emerald-700">
                Saved at {savedAt.slice(11, 19)} UTC
              </span>
            )}
            <button
              type="button"
              onClick={onSave}
              disabled={saving}
              className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {saving ? "Saving…" : "Save changes"}
            </button>
          </div>
        </>
      )}
    </main>
  );
}

function KeyField({
  label,
  placeholder,
  value,
  onChange,
  hasKey,
}: {
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  hasKey: boolean;
}) {
  return (
    <div>
      <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
        {label}
        {hasKey && (
          <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
            set
          </span>
        )}
      </label>
      <input
        type="password"
        autoComplete="new-password"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        placeholder={placeholder}
      />
    </div>
  );
}

function CapField({
  label,
  placeholder,
  value,
  onChange,
}: {
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700">{label}</label>
      <input
        type="number"
        step="0.01"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        placeholder={placeholder}
      />
    </div>
  );
}
