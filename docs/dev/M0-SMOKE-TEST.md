# M0 smoke test — what to walk through after the M0 PR merges

This is the manual verification checklist for M0 (E-2.1 Scaffolding). It exists because per [`CLAUDE.md`](../../CLAUDE.md) hard rules, dependency installation (`pip install`, `npm install`) is not run automatically by Claude — the user runs it post-merge to verify the M0 install path on their own machine.

If anything in this list fails, the failure is in scope for an M0 hot-fix sub-task (E-2.1 stays open until the user can walk through cleanly).

## Prerequisites

- Python 3.11+ (`python --version`)
- Node 20+ (`node --version`)
- npm 10+ (bundled with Node)

## Cross-OS expectation

The same steps work on Windows 11 (PowerShell), macOS (zsh / bash), and Linux. The dev launchers under `scripts/{windows,mac,linux}/dev.*` are the only OS-specific files; everything else is portable.

## The 10-step walkthrough

### 1. Fresh virtualenv

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# macOS / Linux
python -m venv .venv
source .venv/bin/activate
```

### 2. Install the Python package

```bash
pip install -e ".[dev]"
```

Expected: completes without errors. The `impact-crater` console script becomes available.

### 3. Run the Python test suite

```bash
pytest -v
```

Expected: green. ~20 tests covering smoke, app, storage, crypto, api/setup. Coverage report mentions `backend/impact_crater`.

### 4. Confirm the CLI is wired

```bash
impact-crater --version
```

Expected: prints `impact-crater 0.0.1`.

### 5. Install the frontend deps + build it

```bash
cd frontend
npm install
npm run build
cd ..
```

Expected: `npm install` completes, `npm run build` produces `frontend/dist/index.html` + `frontend/dist/assets/*.js,css`.

### 6. Run the frontend test suite

```bash
cd frontend
npm test
cd ..
```

Expected: green. ~6 tests covering App routing branches and the Setup wizard navigation.

### 7. First-run launch (production mode)

```bash
impact-crater
```

Expected:
- CLI prints `impact-crater 0.0.1 starting on http://127.0.0.1:8765`.
- Default browser opens to `http://127.0.0.1:8765`.
- React shell loads.
- Wizard appears at Step 1 of 6 (Welcome).

### 8. Walk the wizard

Click through all 6 steps:

1. Welcome — click Next.
2. Anthropic API key — paste any string (M0 doesn't yet ping the real API per S-2.1.5 → M1). Click Test → see "Anthropic key accepted." in green. Click Next.
3. Google API key — same pattern.
4. Daily spend cap — total cap defaults to $50; leave per-provider caps blank. Click Next.
5. Storage location — leave the override blank. Click Next.
6. Confirm — verify the masked summary. Click Finish.

Expected: the URL changes to `/dashboard`; the dashboard shows "No projects yet" with a disabled "New Project" button.

### 9. Restart and confirm wizard is skipped

Stop the server (`Ctrl+C`). Re-run:

```bash
impact-crater
```

Expected: browser opens; React shell loads; the wizard is **not** shown — the dashboard appears directly.

### 10. Confirm the on-disk artifacts

```bash
# Windows
dir %USERPROFILE%\.impact-crater\db
# macOS / Linux
ls -la ~/.impact-crater/db/
```

Expected:
- `impact-crater.sqlite` exists (SQLite database file)
- `.fernet-key` exists (the encryption key, file-mode 0600 on POSIX)

```bash
# Quick schema check
sqlite3 ~/.impact-crater/db/impact-crater.sqlite ".tables"
```

Expected: lists the 12 tables (`audit`, `cache_index`, `connector_credentials`, `media`, `person_face_photos`, `persons`, `project_media`, `projects`, `quota_state`, `schema_migrations`, `settings`, `snapshots`).

```bash
# Confirm the API key is stored encrypted (NOT plaintext)
sqlite3 ~/.impact-crater/db/impact-crater.sqlite \
  "SELECT key, encrypted, length(value) FROM settings WHERE encrypted = 1"
```

Expected: rows for `anthropic_api_key` and `google_api_key`, both with `encrypted = 1` and a value-length much larger than the original key (Fernet ciphertext is ~140+ chars even for short plaintexts).

## Dev-mode launcher (optional)

For frontend hot-reload (Vite dev server) + backend auto-reload together:

```bash
# Windows
scripts/windows/dev.ps1

# macOS
scripts/mac/dev.sh

# Linux
scripts/linux/dev.sh
```

Open `http://localhost:5173` in your browser. Vite proxies `/api/*` to the backend on `:8765`.

## What M0 explicitly does NOT do

Per `MVP.md` §"Milestones", M0 is the empty bootable shell. The following land in later milestones and are expected to be missing right now:

- Real provider pings (test-key just accepts non-empty input) — **M1 / E-2.2**
- Curation pipeline / Stage 5 narrative judgment / ArcJudgment output — **M1 / E-2.2**
- Render / ffmpeg / Story Video output — **M2 / E-2.3**
- Project creation + media drop + brief input UI — **M3 / E-2.4**
- Music-video mode + Madmom + section-to-media NL — **M4 / E-2.5**
- Person library + face recognition + privacy panel — **M5 / E-2.6**
- Agentic refinement + orchestrator second-guess — **M6 / E-2.7**
- YouTube publish + audit log writer — **M7 / E-2.8**
- Cross-project user profile — **M8 / E-2.9**

If any of those *do* appear to work in M0, that's a bug — flag it.

## If something fails

Most M0 failures fall into three buckets:

1. **`pip install` errors** — usually missing system dependencies. On Windows: ensure Python 3.11+ is on PATH (not the Microsoft Store stub). On macOS: ensure Xcode CLI tools are installed (`xcode-select --install`). On Linux: ensure `python3-dev` is installed.
2. **`npm install` errors** — usually a Node version mismatch. The frontend targets Node 20+; older Node versions hit dep-resolution issues.
3. **Browser doesn't open** — the CLI uses Python's `webbrowser` module which respects `BROWSER` env var on Linux. If the browser doesn't open, navigate to the URL the CLI printed manually.

For anything else, file a bug under `E-2.1` (open it as a new Story under the epic if it warrants its own work item; otherwise add it to the Activity log).
