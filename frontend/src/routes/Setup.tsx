// First-time-setup wizard — 6-step flow per ADR-0015 + the user-accepted
// M0 plan. The user lands here on first run; on Finish the API persists
// settings, generates the Fernet key, and the React shell routes to the
// dashboard.

import { useState } from "react";
import { useForm } from "react-hook-form";
import type { UseFormReturn } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "react-router-dom";

import { completeSetup, testKey, type Provider, type TestKeyResult } from "../api/setup";
import { useSetupStore } from "../stores/setupStore";

// -- Schema --------------------------------------------------------------

const FormSchema = z
  .object({
    anthropic_api_key: z.string().min(1, "Required"),
    google_api_key: z.string().min(1, "Required"),
    spend_cap_total_usd: z.coerce
      .number({ invalid_type_error: "Enter a number" })
      .min(1, "Minimum $1")
      .max(100_000, "Maximum $100,000"),
    spend_cap_anthropic_usd: z
      .union([z.literal(""), z.coerce.number().min(0).max(100_000)])
      .optional(),
    spend_cap_google_usd: z
      .union([z.literal(""), z.coerce.number().min(0).max(100_000)])
      .optional(),
    impact_crater_home_override: z.string().optional(),
  })
  .superRefine((v, ctx) => {
    const total = v.spend_cap_total_usd;
    if (typeof v.spend_cap_anthropic_usd === "number" && v.spend_cap_anthropic_usd > total) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["spend_cap_anthropic_usd"],
        message: `Cannot exceed total cap ($${total})`,
      });
    }
    if (typeof v.spend_cap_google_usd === "number" && v.spend_cap_google_usd > total) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["spend_cap_google_usd"],
        message: `Cannot exceed total cap ($${total})`,
      });
    }
  });

type FormValues = z.infer<typeof FormSchema>;
type Form = UseFormReturn<FormValues>;

// -- Component -----------------------------------------------------------

const STEP_TITLES = [
  "Welcome",
  "Anthropic API key",
  "Google API key",
  "Daily spend cap",
  "Storage location",
  "Confirm",
];

export default function Setup() {
  const [step, setStep] = useState(0);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const setStatus = useSetupStore((s) => s.setStatus);
  const navigate = useNavigate();

  const form = useForm<FormValues>({
    resolver: zodResolver(FormSchema),
    mode: "onChange",
    defaultValues: {
      anthropic_api_key: "",
      google_api_key: "",
      spend_cap_total_usd: 50 as unknown as number,
      spend_cap_anthropic_usd: "",
      spend_cap_google_usd: "",
      impact_crater_home_override: "",
    },
  });

  const values = form.watch();

  async function onFinish() {
    setSubmitError(null);
    try {
      await completeSetup({
        anthropic_api_key: values.anthropic_api_key,
        google_api_key: values.google_api_key,
        spend_cap_total_usd: values.spend_cap_total_usd,
        spend_cap_anthropic_usd:
          typeof values.spend_cap_anthropic_usd === "number"
            ? values.spend_cap_anthropic_usd
            : null,
        spend_cap_google_usd:
          typeof values.spend_cap_google_usd === "number"
            ? values.spend_cap_google_usd
            : null,
        impact_crater_home_override: values.impact_crater_home_override?.trim()
          ? values.impact_crater_home_override
          : null,
      });
      setStatus("complete");
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    }
  }

  const canAdvance = stepIsValid(step, form);

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-3xl font-semibold text-slate-900">Welcome to Impact Crater</h1>
      <p className="mt-1 text-sm text-slate-500">
        Step {step + 1} of {STEP_TITLES.length} — {STEP_TITLES[step]}
      </p>

      <div className="mt-6 rounded border border-slate-200 bg-white p-6">
        {step === 0 && <StepWelcome />}
        {step === 1 && <StepKey provider="anthropic" form={form} />}
        {step === 2 && <StepKey provider="google" form={form} />}
        {step === 3 && <StepCaps form={form} />}
        {step === 4 && <StepStorage form={form} />}
        {step === 5 && <StepConfirm values={values} />}
      </div>

      {submitError && (
        <p role="alert" className="mt-4 rounded bg-red-50 px-4 py-2 text-sm text-red-700">
          {submitError}
        </p>
      )}

      <div className="mt-6 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0}
          className="rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Back
        </button>
        {step < STEP_TITLES.length - 1 ? (
          <button
            type="button"
            onClick={() => setStep((s) => s + 1)}
            disabled={!canAdvance}
            className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            Next
          </button>
        ) : (
          <button
            type="button"
            onClick={onFinish}
            disabled={!form.formState.isValid}
            className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            Finish
          </button>
        )}
      </div>
    </main>
  );
}

// -- Step components -----------------------------------------------------

function StepWelcome() {
  return (
    <div className="space-y-3 text-sm text-slate-700">
      <p>
        Impact Crater needs a few things before it can curate your media: API keys for the
        LLM providers it'll call, and a daily spend cap to protect against runaway jobs.
      </p>
      <p>You can change everything later in Settings.</p>
    </div>
  );
}

function StepKey({ provider, form }: { provider: Provider; form: Form }) {
  const fieldName = provider === "anthropic" ? "anthropic_api_key" : "google_api_key";
  const inputId = `field-${fieldName}`;
  const error = form.formState.errors[fieldName];
  const [testResult, setTestResult] = useState<TestKeyResult | null>(null);
  const [testing, setTesting] = useState(false);

  async function onTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testKey(provider, form.getValues(fieldName));
      setTestResult(result);
    } finally {
      setTesting(false);
    }
  }

  return (
    <div className="space-y-3">
      <label htmlFor={inputId} className="block text-sm font-medium text-slate-700">
        {provider === "anthropic" ? "Anthropic" : "Google"} API key
      </label>
      <input
        id={inputId}
        type="password"
        autoComplete="new-password"
        {...form.register(fieldName)}
        className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        placeholder={provider === "anthropic" ? "sk-ant-..." : "AIza..."}
      />
      {error && <p className="text-xs text-red-600">{error.message as string}</p>}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onTest}
          disabled={testing || !form.getValues(fieldName)}
          className="rounded border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {testing ? "Testing…" : "Test"}
        </button>
        {testResult && (
          <p
            className={
              testResult.success
                ? "text-xs text-emerald-700"
                : "text-xs text-red-700"
            }
          >
            {testResult.message}
          </p>
        )}
      </div>
    </div>
  );
}

function StepCaps({ form }: { form: Form }) {
  return (
    <div className="space-y-4 text-sm">
      <div>
        <label className="block font-medium text-slate-700">
          Total daily cap (USD, required, ≥ $1)
        </label>
        <input
          type="number"
          step="0.01"
          {...form.register("spend_cap_total_usd")}
          className="mt-1 w-40 rounded border border-slate-300 px-3 py-2 focus:border-slate-500 focus:outline-none"
        />
        {form.formState.errors.spend_cap_total_usd && (
          <p className="mt-1 text-xs text-red-600">
            {form.formState.errors.spend_cap_total_usd.message as string}
          </p>
        )}
      </div>
      <div>
        <label className="block font-medium text-slate-700">
          Anthropic-only cap (optional, ≤ total)
        </label>
        <input
          type="number"
          step="0.01"
          {...form.register("spend_cap_anthropic_usd")}
          className="mt-1 w-40 rounded border border-slate-300 px-3 py-2 focus:border-slate-500 focus:outline-none"
        />
        {form.formState.errors.spend_cap_anthropic_usd && (
          <p className="mt-1 text-xs text-red-600">
            {form.formState.errors.spend_cap_anthropic_usd.message as string}
          </p>
        )}
      </div>
      <div>
        <label className="block font-medium text-slate-700">
          Google-only cap (optional, ≤ total)
        </label>
        <input
          type="number"
          step="0.01"
          {...form.register("spend_cap_google_usd")}
          className="mt-1 w-40 rounded border border-slate-300 px-3 py-2 focus:border-slate-500 focus:outline-none"
        />
        {form.formState.errors.spend_cap_google_usd && (
          <p className="mt-1 text-xs text-red-600">
            {form.formState.errors.spend_cap_google_usd.message as string}
          </p>
        )}
      </div>
      <p className="text-xs text-slate-500">
        Per ADR-0015, a job is allowed only if it stays under both the total cap and any
        per-provider cap. Caps are enforced before each LLM call; mid-job approach triggers a
        pause-and-prompt.
      </p>
    </div>
  );
}

function StepStorage({ form }: { form: Form }) {
  return (
    <div className="space-y-4 text-sm">
      <div>
        <label className="block font-medium text-slate-700">
          Custom data directory (optional)
        </label>
        <input
          type="text"
          {...form.register("impact_crater_home_override")}
          className="mt-1 w-full rounded border border-slate-300 px-3 py-2 focus:border-slate-500 focus:outline-none"
          placeholder="Leave blank to use ~/.impact-crater/"
        />
        <p className="mt-1 text-xs text-slate-500">
          To take effect, set the <code className="rounded bg-slate-100 px-1">IMPACT_CRATER_HOME</code>{" "}
          environment variable to this path before running <code className="rounded bg-slate-100 px-1">impact-crater</code>.
        </p>
      </div>
      <div className="rounded border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
        <p className="font-medium text-slate-700">Privacy posture defaults</p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>Strip EXIF before sending to LLM: ON</li>
          <li>Strip GPS only: ON (subset of full EXIF strip)</li>
          <li>Blur faces before sending to LLM: OFF</li>
        </ul>
        <p className="mt-2">
          Locked to these defaults at MVP. Per-project toggles ship in v1.
          See <code className="rounded bg-slate-100 px-1">ADR-0016</code> for
          the toggle interaction matrix.
        </p>
      </div>
    </div>
  );
}

function StepConfirm({ values }: { values: FormValues }) {
  return (
    <div className="space-y-2 text-sm text-slate-700">
      <p className="font-medium">Ready to finish? Here's what we'll save:</p>
      <ul className="list-disc space-y-1 pl-5">
        <li>Anthropic API key: {mask(values.anthropic_api_key)}</li>
        <li>Google API key: {mask(values.google_api_key)}</li>
        <li>Total daily spend cap: ${values.spend_cap_total_usd}</li>
        <li>
          Anthropic-only cap:{" "}
          {typeof values.spend_cap_anthropic_usd === "number"
            ? `$${values.spend_cap_anthropic_usd}`
            : "(no per-provider cap)"}
        </li>
        <li>
          Google-only cap:{" "}
          {typeof values.spend_cap_google_usd === "number"
            ? `$${values.spend_cap_google_usd}`
            : "(no per-provider cap)"}
        </li>
        <li>
          Custom data directory:{" "}
          {values.impact_crater_home_override?.trim() || "(default ~/.impact-crater/)"}
        </li>
      </ul>
      <p className="pt-2 text-xs text-slate-500">
        API keys are encrypted at rest with a Fernet key generated on first save (per
        ADR-0013). The key file lives at{" "}
        <code className="rounded bg-slate-100 px-1">~/.impact-crater/db/.fernet-key</code>{" "}
        — back it up if you want to move credentials to another machine.
      </p>
    </div>
  );
}

// -- Helpers -------------------------------------------------------------

function mask(s: string): string {
  if (!s) return "(empty)";
  if (s.length <= 8) return "*".repeat(s.length);
  return `${s.slice(0, 4)}…${s.slice(-2)}`;
}

function stepIsValid(step: number, form: Form): boolean {
  // Walk per-step required fields. Step 0 (Welcome), 4 (Storage) and 5
  // (Confirm) have no per-step required input beyond the running form-valid
  // state. The Finish button itself uses form.formState.isValid.
  if (step === 0 || step >= 4) {
    return true;
  }
  const v = form.getValues();
  if (step === 1) return Boolean(v.anthropic_api_key);
  if (step === 2) return Boolean(v.google_api_key);
  if (step === 3) {
    const total = v.spend_cap_total_usd;
    if (!total || total < 1) return false;
    return !form.formState.errors.spend_cap_total_usd;
  }
  return true;
}
