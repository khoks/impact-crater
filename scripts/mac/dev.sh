#!/usr/bin/env bash
# Dev-mode launcher (macOS).
#
# Starts uvicorn (with --reload) and the Vite dev server in parallel.
# Vite proxies /api/* to the backend per frontend/vite.config.ts.
#
# Prerequisites: pip install -e ".[dev]"  +  cd frontend && npm install

set -euo pipefail
repo="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$repo"

echo "Starting backend (FastAPI on :8765) + frontend (Vite on :5173)..."
echo "Open http://localhost:5173 in your browser."

impact-crater --no-browser --reload --port 8765 &
backend_pid=$!
trap 'kill $backend_pid 2>/dev/null || true' EXIT

cd "$repo/frontend"
npm run dev
