# Dev-mode launcher (Windows / PowerShell).
#
# Starts uvicorn (with --reload) and the Vite dev server in parallel.
# Vite proxies /api/* to the backend per frontend/vite.config.ts.
#
# Prerequisites: pip install -e ".[dev]"  +  cd frontend && npm install

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repo

Write-Host "Starting backend (FastAPI on :8765) + frontend (Vite on :5173)..."
Write-Host "Open http://localhost:5173 in your browser."

$backend = Start-Process -FilePath "impact-crater" `
    -ArgumentList "--no-browser","--reload","--port","8765" `
    -PassThru -NoNewWindow

try {
    Set-Location "$repo\frontend"
    npm run dev
} finally {
    if ($backend -and -not $backend.HasExited) {
        Stop-Process -Id $backend.Id -Force
    }
}
