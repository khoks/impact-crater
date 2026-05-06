// New-project flow — single form gathering name + brief + folder + audio +
// duration. On submit, calls /api/folder/scan to materialize the media list,
// stashes the draft into newProjectStore, and routes to /projects/new/effort.

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { scanFolder, type FolderScanResponse } from "../api/folder";
import { useNewProjectStore } from "../stores/newProjectStore";

type ProjectMode = "standard" | "music_video";

interface FormState {
  name: string;
  brief: string;
  folder_path: string;
  audio_path: string;
  target_duration_seconds: number;
  mode: ProjectMode;
  section_to_media_nl: string;
}

const INITIAL: FormState = {
  name: "",
  brief: "",
  folder_path: "",
  audio_path: "",
  target_duration_seconds: 60,
  mode: "standard",
  section_to_media_nl: "",
};

export default function NewProject() {
  const navigate = useNavigate();
  const setDraft = useNewProjectStore((s) => s.setDraft);
  const [form, setForm] = useState<FormState>(INITIAL);
  const [scan, setScan] = useState<FolderScanResponse | null>(null);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const canSubmit =
    form.name.trim().length > 0 &&
    form.brief.trim().length > 0 &&
    form.audio_path.trim().length > 0 &&
    scan !== null &&
    scan.photo_count + scan.video_count > 0 &&
    form.target_duration_seconds >= 5;

  async function onScan() {
    setScanError(null);
    setScan(null);
    setScanning(true);
    try {
      const result = await scanFolder(form.folder_path.trim());
      setScan(result);
    } catch (err) {
      setScanError(err instanceof Error ? err.message : String(err));
    } finally {
      setScanning(false);
    }
  }

  async function onContinue() {
    if (!scan) return;
    setSubmitError(null);
    try {
      setDraft({
        name: form.name.trim(),
        brief: form.brief.trim(),
        folder_path: form.folder_path.trim(),
        audio_path: form.audio_path.trim(),
        target_duration_seconds: form.target_duration_seconds,
        mode: form.mode,
        section_to_media_nl: form.section_to_media_nl.trim(),
        scanned_media_paths: scan.items.map((it) => it.path),
        scanned_photo_count: scan.photo_count,
        scanned_video_count: scan.video_count,
        scanned_total_bytes: scan.total_bytes,
      });
      navigate("/projects/new/effort");
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">New project</h1>
        <Link to="/dashboard" className="text-sm text-slate-500 hover:text-slate-900">
          Cancel
        </Link>
      </header>

      <div className="mt-8 space-y-6 rounded border border-slate-200 bg-white p-6">
        <Field label="Project name">
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
            placeholder="Alps trip — June"
          />
        </Field>

        <Field label="Brief (one paragraph — what kind of video?)">
          <textarea
            value={form.brief}
            onChange={(e) => setForm({ ...form, brief: e.target.value })}
            rows={4}
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
            placeholder="Highlight reel of our hike — sunrise on the summit, the kids racing along the ridge, the storm cloud rolling in. Slow start, energetic middle, quiet ending."
          />
        </Field>

        <Field label="Media folder (server-side absolute path)">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={form.folder_path}
              onChange={(e) => setForm({ ...form, folder_path: e.target.value })}
              className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none font-mono"
              placeholder="C:\\Users\\you\\Pictures\\Alps2026  or  /home/you/Pictures/Alps2026"
            />
            <button
              type="button"
              onClick={onScan}
              disabled={!form.folder_path.trim() || scanning}
              className="rounded border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {scanning ? "Scanning…" : "Scan"}
            </button>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Browsers can't expose absolute paths; paste the path here.
          </p>
          {scanError && (
            <p role="alert" className="mt-2 text-xs text-red-600">
              {scanError}
            </p>
          )}
          {scan && (
            <div className="mt-3 rounded bg-slate-50 px-3 py-2 text-xs text-slate-700">
              <p>
                <strong>{scan.photo_count}</strong> photo
                {scan.photo_count === 1 ? "" : "s"} +{" "}
                <strong>{scan.video_count}</strong> video
                {scan.video_count === 1 ? "" : "s"} ·{" "}
                {(scan.total_bytes / 1_000_000).toFixed(1)} MB
              </p>
              {scan.truncated && (
                <p className="mt-1 text-amber-700">
                  Truncated at 5000 entries — pick a smaller folder.
                </p>
              )}
            </div>
          )}
        </Field>

        <Field label="Audio file (server-side absolute path)">
          <input
            type="text"
            value={form.audio_path}
            onChange={(e) => setForm({ ...form, audio_path: e.target.value })}
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none font-mono"
            placeholder="C:\\Users\\you\\Music\\track.mp3"
          />
        </Field>

        <Field
          label={`Target duration (${form.target_duration_seconds}s)`}
        >
          <input
            type="range"
            min={5}
            max={600}
            step={5}
            value={form.target_duration_seconds}
            onChange={(e) =>
              setForm({
                ...form,
                target_duration_seconds: Number.parseInt(e.target.value, 10),
              })
            }
            className="w-full"
          />
          <div className="mt-1 flex justify-between text-xs text-slate-500">
            <span>5s</span>
            <span>10 min</span>
          </div>
        </Field>

        <Field label="Mode">
          <div className="space-y-2">
            <label className="flex items-start gap-2 text-sm">
              <input
                type="radio"
                name="mode"
                value="standard"
                checked={form.mode === "standard"}
                onChange={() => setForm({ ...form, mode: "standard" })}
                className="mt-1"
              />
              <span>
                <strong>Standard</strong> — music sits under the curated
                video. Cuts driven by the brief, not the beat.
              </span>
            </label>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="radio"
                name="mode"
                value="music_video"
                checked={form.mode === "music_video"}
                onChange={() => setForm({ ...form, mode: "music_video" })}
                className="mt-1"
              />
              <span>
                <strong>Music video</strong> — cuts snap to the beat;
                section structure of the song maps to media segments.
              </span>
            </label>
          </div>
        </Field>

        {form.mode === "music_video" && (
          <Field label="Section-to-media spec (optional)">
            <textarea
              value={form.section_to_media_nl}
              onChange={(e) =>
                setForm({ ...form, section_to_media_nl: e.target.value })
              }
              rows={3}
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
              placeholder="Intro should be slow scenic shots. Chorus is the summit attempt — the climbing footage. Bridge should be the rest stop with the kids playing. Outro is the sunset shots from the way back."
            />
            <p className="mt-1 text-xs text-slate-500">
              Free-text — the narrative judge reads this verbatim alongside
              the music's section structure.
            </p>
          </Field>
        )}
      </div>

      {submitError && (
        <p role="alert" className="mt-4 rounded bg-red-50 px-4 py-2 text-sm text-red-700">
          {submitError}
        </p>
      )}

      <div className="mt-6 flex justify-end">
        <button
          type="button"
          onClick={onContinue}
          disabled={!canSubmit}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
        >
          Continue → effort & cost
        </button>
      </div>
    </main>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700">{label}</label>
      <div className="mt-1">{children}</div>
    </div>
  );
}
