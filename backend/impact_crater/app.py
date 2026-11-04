"""FastAPI app factory.

Per ADR-0005, a single FastAPI process hosts the HTTP + WebSocket API
under `/api/...` and serves the built React frontend from `frontend_dist/`
at `/`. This module exposes `create_app()` which the CLI passes to
uvicorn; the same factory is used by the test suite via httpx.AsyncClient.
"""

from __future__ import annotations

import html
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from impact_crater import __version__, api_auth
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
)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Per-process startup: run the pending schema migrations, load the dry-run toggle."""
    from impact_crater.connectors import dry_run
    from impact_crater.storage import migrations
    from impact_crater.storage import settings as settings_store

    await migrations.run_pending_migrations()
    stored = await settings_store.get_value(settings_store.KEY_PUBLISH_DRY_RUN)
    dry_run.set_settings_dry_run(None if stored is None else stored == "true")
    yield


def create_app(*, allow_remote: bool | None = None) -> FastAPI:
    """`allow_remote` (default: the `IMPACT_CRATER_ALLOW_REMOTE` env var the CLI sets for
    `--allow-remote`) accepts Host headers other than this machine's; the token is
    required either way, and only local requests are handed it (ADR-0022)."""
    if allow_remote is None:
        allow_remote = os.environ.get(api_auth.ALLOW_REMOTE_ENV) == "1"
    token = api_auth.get_or_create_token()
    app = FastAPI(
        title="Impact Crater",
        version=__version__,
        description="One-click media-to-video creator (self-hosted): drop photos and videos, describe the video you want, preview, approve.",
        lifespan=_lifespan,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    app.state.api_token = token
    app.add_middleware(api_auth.ApiTokenMiddleware, token=token)
    # Added last so it runs first.
    app.add_middleware(api_auth.HostGuardMiddleware, allow_remote=allow_remote)
    _declare_bearer_auth(app)

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__}

    @app.get(api_auth.SESSION_PATH)
    async def session(request: Request) -> dict[str, str]:
        if not api_auth.is_local(request.scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The API token is only handed to a browser on this machine.",
            )
        return {"token": token}

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

    _mount_frontend(app, token)

    return app


def _declare_bearer_auth(app: FastAPI) -> None:
    """Advertise the bearer token in the OpenAPI schema so /api/docs can send it."""

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
            schema.setdefault("components", {})["securitySchemes"] = {
                "bearerAuth": {"type": "http", "scheme": "bearer"}
            }
            schema["security"] = [{"bearerAuth": []}]
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]


def _mount_frontend(app: FastAPI, token: str) -> None:
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

    @app.get("/{full_path:path}", response_model=None)
    async def spa_fallback(full_path: str, request: Request) -> Response:
        candidate = _dist_file(dist_dir, full_path)
        if candidate is not None:
            return FileResponse(candidate)
        # SPA fallback: every other route serves index.html so react-router takes over.
        return _index_html(dist_dir, token, request)


def _dist_file(dist_dir: Path, full_path: str) -> Path | None:
    """A static file in the dist root (favicon etc.), never anything outside it: the path
    arrives percent-decoded, so `..` segments and absolute paths must not escape."""
    if not full_path:
        return None
    root = dist_dir.resolve()
    candidate = (root / full_path).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    return None if candidate.name == "index.html" else candidate


def _index_html(dist_dir: Path, token: str, request: Request) -> HTMLResponse:
    """index.html, carrying the API token in a meta tag for a browser on this machine."""
    page = (dist_dir / "index.html").read_text(encoding="utf-8")
    if api_auth.is_local(request.scope):
        meta = f'<meta name="{api_auth.TOKEN_META_NAME}" content="{html.escape(token)}">'
        page = page.replace("</head>", f"{meta}</head>", 1)
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})


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
