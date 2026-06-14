"""FastAPI app factory.

Per ADR-0005, a single FastAPI process hosts the HTTP + WebSocket API
under `/api/...` and serves the built React frontend from `frontend_dist/`
at `/`. This module exposes `create_app()` which the CLI passes to
uvicorn; the same factory is used by the test suite via httpx.AsyncClient.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from impact_crater import __version__
from impact_crater.api import (
    effort,
    feedback,
    folder,
    jobs,
    media,
    persons,
    profile,
    projects,
    publish,
    settings,
    setup,
    snapshots,
    workplan,
    ws,
)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Per-process startup + shutdown hooks.

    M0 only runs schema migrations; M1+ will add LLM client warm-up,
    worker pool start, etc.
    """
    from impact_crater.storage import migrations

    await migrations.run_pending_migrations()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Impact Crater",
        version=__version__,
        description="AI-driven photo and video curator (self-hosted).",
        lifespan=_lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__}

    app.include_router(setup.router, prefix="/api/setup", tags=["setup"])
    app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
    app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
    app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
    app.include_router(folder.router, prefix="/api/folder", tags=["folder"])
    app.include_router(effort.router, prefix="/api", tags=["effort"])
    app.include_router(snapshots.router, prefix="/api/snapshots", tags=["snapshots"])
    app.include_router(media.router, prefix="/api/media", tags=["media"])
    app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])
    app.include_router(workplan.router, prefix="/api/workplan", tags=["workplan"])
    app.include_router(persons.router, prefix="/api/persons", tags=["persons"])
    app.include_router(publish.router, prefix="/api", tags=["publish"])
    app.include_router(profile.router, prefix="/api/profile", tags=["profile"])
    app.include_router(ws.router, prefix="/api", tags=["ws"])

    _mount_frontend(app)

    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built React frontend from `frontend_dist/` if it exists.

    The frontend is bundled into the wheel under `impact_crater/frontend_dist/`
    by `setup.cfg`'s package-data declaration; in dev mode (editable install
    pre-build), the dist may not exist yet. In that case we serve a helpful
    "frontend not built" placeholder at `/` so the failure mode is obvious.
    """
    dist_dir = _frontend_dist_dir()

    if dist_dir is None:
        @app.get("/", response_class=HTMLResponse)
        async def not_built() -> str:
            return _NOT_BUILT_HTML

        return

    app.mount(
        "/assets",
        StaticFiles(directory=dist_dir / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}", response_class=FileResponse)
    async def spa_fallback(full_path: str) -> FileResponse:
        # Static files in dist root (favicon, etc).
        candidate = dist_dir / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        # SPA fallback: every other route serves index.html so react-router takes over.
        return FileResponse(dist_dir / "index.html")


def _frontend_dist_dir() -> Path | None:
    """Locate the built frontend.

    Two locations are checked:
      1. `impact_crater/frontend_dist/`  (packaged, in the installed wheel)
      2. `<repo_root>/frontend/dist/`    (dev mode, editable install)
    Returns the first one that exists, or None if the frontend is unbuilt.
    """
    packaged = Path(__file__).resolve().parent / "frontend_dist"
    if packaged.is_dir() and (packaged / "index.html").is_file():
        return packaged

    repo_root = Path(__file__).resolve().parents[2]
    dev = repo_root / "frontend" / "dist"
    if dev.is_dir() and (dev / "index.html").is_file():
        return dev

    return None


_NOT_BUILT_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Impact Crater — frontend not built</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 640px; margin: 4em auto; padding: 0 1em; line-height: 1.5; }
  code { background: #f0f0f0; padding: 0.1em 0.3em; border-radius: 3px; }
  pre { background: #f0f0f0; padding: 1em; border-radius: 4px; overflow-x: auto; }
</style>
</head><body>
<h1>Impact Crater — frontend not built</h1>
<p>The Python backend is running, but the React frontend has not been built.
Build it with:</p>
<pre>cd frontend
npm install
npm run build</pre>
<p>Then refresh this page.</p>
<p>API endpoints are still available — see <a href="/api/docs">/api/docs</a>
or <a href="/api/health">/api/health</a>.</p>
</body></html>
"""


__all__ = ["create_app"]
