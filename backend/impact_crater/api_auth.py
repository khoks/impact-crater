"""Per-install API token and the loopback guards around the local API (S-3.11.3, ADR-0022).

The app is a single-user server on the owner's machine. A random token, created on
first start at `~/.impact-crater/.api-token`, must accompany every mutating `/api`
request and the job WebSocket, so another page open in the browser, or another device
on the network, cannot change settings, spend the API budget or publish. Loopback
clients receive the token in a meta tag on the served page; the Vite dev server's page
reads it from `GET /api/session`, which answers loopback clients only.
"""

from __future__ import annotations

import hmac
import secrets
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from impact_crater import paths

LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
TOKEN_META_NAME = "impact-crater-api-token"
SESSION_PATH = "/api/session"
ALLOW_REMOTE_ENV = "IMPACT_CRATER_ALLOW_REMOTE"
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def get_or_create_token() -> str:
    path = paths.api_token_path()
    if path.is_file():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(32)
    path.write_text(token + "\n", encoding="utf-8")
    paths.harden_secret_file(path)
    return token


def auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_or_create_token()}"}


def is_loopback(host: str | None) -> bool:
    return host in LOOPBACK_HOSTS


def token_matches(presented: object, expected: str) -> bool:
    return isinstance(presented, str) and hmac.compare_digest(
        presented.encode("utf-8"), expected.encode("utf-8")
    )


def origin_allowed(origin: str | None, host_header: str | None) -> bool:
    """A browser WebSocket may come from this server's own page or from a loopback page
    (the Vite dev server proxies with a rewritten Host). Non-browser clients send no Origin."""
    if not origin:
        return True
    parts = urlsplit(origin)
    if parts.hostname in LOOPBACK_HOSTS:
        return True
    return host_header is not None and parts.netloc == host_header


class ApiTokenMiddleware:
    """401 unless the request carries the install's bearer token: on every mutating `/api`
    request, and on every `/api` request from a non-loopback client. WebSockets
    authenticate in their first message instead (browsers cannot set the header there)."""

    def __init__(self, app: ASGIApp, *, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not path.startswith("/api/") or path == SESSION_PATH:
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        loopback = client is not None and is_loopback(client[0])
        if scope["method"] in _MUTATING_METHODS or not loopback:
            scheme, _, presented = Headers(scope=scope).get("authorization", "").partition(" ")
            if scheme.lower() != "bearer" or not token_matches(presented, self.token):
                response = JSONResponse(
                    {
                        "detail": "Missing or wrong API token. Reload the app page; from "
                        "another device, send the token from ~/.impact-crater/.api-token "
                        "as 'Authorization: Bearer <token>'."
                    },
                    status_code=401,
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
