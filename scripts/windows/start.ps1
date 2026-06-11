# start.ps1 — One-shot Impact Crater dev launcher (Windows).
#
# Starts:
#   - FastAPI backend on http://127.0.0.1:8765  (uvicorn --reload)
#   - Vite dev server on http://localhost:5173  (npm run dev)
# Opens the default browser at the Vite URL once it's responding.
# Ctrl+C shuts both down cleanly (kills the whole process tree, not just the
# top-level PIDs — npm spawns node, uvicorn --reload spawns a child worker).
#
# Prereqs (one-time):
#   python -m venv .venv
#   .venv\Scripts\Activate.ps1
#   pip install -e ".[dev]"
#   cd frontend; npm install

$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repo

# --- Prereq checks --------------------------------------------------------

$venvExe = Join-Path $repo ".venv\Scripts\impact-crater.exe"
if (-not (Test-Path $venvExe)) {
    Write-Host "ERROR: impact-crater is not installed in .venv" -ForegroundColor Red
    Write-Host "From the repo root:" -ForegroundColor Red
    Write-Host "  python -m venv .venv"
    Write-Host "  .venv\Scripts\Activate.ps1"
    Write-Host "  pip install -e `".[dev]`""
    exit 1
}

$nodeModules = Join-Path $repo "frontend\node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Host "ERROR: frontend dependencies are not installed" -ForegroundColor Red
    Write-Host "Run: cd frontend; npm install" -ForegroundColor Red
    exit 1
}

$frontendUrl = "http://localhost:5173"
$backendUrl  = "http://127.0.0.1:8765"

Write-Host ""
Write-Host "Starting Impact Crater dev stack..." -ForegroundColor Cyan
Write-Host "  Backend:  $backendUrl  (FastAPI --reload)"
Write-Host "  Frontend: $frontendUrl  (Vite, proxies /api/* to backend)"
Write-Host ""

# --- Launch ---------------------------------------------------------------

$procs = @()

try {
    $backend = Start-Process -FilePath $venvExe `
        -ArgumentList "--no-browser","--reload","--port","8765" `
        -WorkingDirectory $repo `
        -PassThru -NoNewWindow
    $procs += $backend
    Write-Host ("[backend ] PID {0}" -f $backend.Id) -ForegroundColor DarkGray

    # On Windows Start-Process needs the actual executable, so npm.cmd (not npm).
    $frontend = Start-Process -FilePath "npm.cmd" `
        -ArgumentList "run","dev" `
        -WorkingDirectory (Join-Path $repo "frontend") `
        -PassThru -NoNewWindow
    $procs += $frontend
    Write-Host ("[frontend] PID {0}" -f $frontend.Id) -ForegroundColor DarkGray

    # Wait for Vite to start serving HTML, then open the browser.
    Write-Host "Waiting for Vite to come up..." -ForegroundColor DarkGray
    $deadline = (Get-Date).AddSeconds(45)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        if ($frontend.HasExited) { break }
        try {
            $resp = Invoke-WebRequest -Uri $frontendUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($resp.StatusCode -eq 200) { $ready = $true; break }
        } catch {
            Start-Sleep -Milliseconds 400
        }
    }
    if ($ready) {
        Write-Host "Vite is ready. Opening browser..." -ForegroundColor Green
        Start-Process $frontendUrl
    } else {
        Write-Host "Vite did not respond within 45s. Open $frontendUrl manually if it comes up." -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "==== Dev stack is running. Press Ctrl+C to stop. ====" -ForegroundColor Cyan
    Write-Host ""

    # Block until the user hits Ctrl+C, or one of the children dies.
    while ($true) {
        if ($backend.HasExited) {
            Write-Host ("Backend exited (code {0}); shutting down frontend." -f $backend.ExitCode) -ForegroundColor Yellow
            break
        }
        if ($frontend.HasExited) {
            Write-Host ("Frontend exited (code {0}); shutting down backend." -f $frontend.ExitCode) -ForegroundColor Yellow
            break
        }
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host ""
    Write-Host "Stopping dev stack..." -ForegroundColor Cyan
    foreach ($p in $procs) {
        if ($null -ne $p -and -not $p.HasExited) {
            # /T = kill the whole tree. npm -> node; uvicorn --reload -> worker.
            & taskkill.exe /F /T /PID $p.Id 2>$null | Out-Null
        }
    }
    Write-Host "Done." -ForegroundColor Green
}
