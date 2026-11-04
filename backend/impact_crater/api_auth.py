"""Per-install API token and the loopback guards around the local API (S-3.11.3, ADR-0022).

The app is a single-user server on the owner's machine. A random token, created on
first start at `~/.impact-crater/.api-token`, must accompany every `/api` request (bar a
few media files that `<img>` / `<video>` tags load) and the job WebSocket, so another
page open in the browser, or another device on the network, cannot read folders, change
settings, spend the API budget or publish. A *local* request — loopback client, loopback
Host, no forwarding proxy in between — receives the token in a meta tag on the served
page; the Vite dev server's page reads it from `GET /api/session`, which answers local
requests only.
"""

from __future__ import annotations

import hmac
import ipaddress
import os
import re
import secrets
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from impact_crater import paths

LOOPBACK_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})
TOKEN_META_NAME = "impact-crater-api-token"
SESSION_PATH = "/api/session"
ALLOW_REMOTE_ENV = "IMPACT_CRATER_ALLOW_REMOTE"
_READ_METHODS = frozenset({"GET", "HEAD"})
# What the page loads through tags that cannot carry a header, plus health and the API docs.
_TOKENLESS_LOCAL_READS = re.compile(
    r"^/api/(health|docs|openapi\.json"
    r"|media/[^/]+/thumb\.jpg"
    r"|snapshots/[^/]+/render\.mp4"
    r"|feedback/[^/]+/screenshot\.png)$"
)


def get_or_create_token() -> str:
    path = paths.api_token_path()
    if path.is_file():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            paths.harden_secret_file(path)
            return token
    token = secrets.token_urlsafe(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token + "\n")
    paths.harden_secret_file(path)
    return token


def auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_or_create_token()}"}


def is_loopback(host: str | None) -> bool:
    """A loopback name or IP literal (IPv4-mapped IPv6 included)."""
    if host is None:
        return False
    if host.lower() in LOOPBACK_NAMES:
        return True
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped.is_loopback
    return ip.is_loopback


def host_name(host_header: str | None) -> str | None:
    """The name in a Host header without its port (`[::1]:8765` → `::1`)."""
    if not host_header:
        return None
    try:
        return urlsplit(f"//{host_header}").hostname
    except ValueError:
        return None


def is_local(scope: Scope) -> bool:
    """A request from a browser or tool on this machine: loopback client, loopback Host
    (a DNS-rebinding page carries its own name), and no proxy hop from elsewhere — a
    tunnel or `vite --host` forwards remote callers from 127.0.0.1."""
    client = scope.get("client")
    if client is None or not is_loopback(client[0]):
        return False
    headers = Headers(scope=scope)
    if not is_loopback(host_name(headers.get("host"))):
        return False
    if "forwarded" in headers:
        return False
    forwarded_for = headers.get("x-forwarded-for")
    if forwarded_for is None:
        return True
    return all(is_loopback(hop.strip()) for hop in forwarded_for.split(","))


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
    if is_loopback(parts.hostname):
        return True
    return host_header is not None and parts.netloc == host_header


class HostGuardMiddleware:
    """400 unless the Host header names this machine (`localhost`, `127.0.0.1`, `[::1]`),
    which is what stops a DNS-rebinding page. `--allow-remote` lifts it; the token and
    `is_local` still decide what a request may do."""

    def __init__(self, app: ASGIApp, *, allow_remote: bool) -> None:
        self.app = app
        self.allow_remote = allow_remote

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] in ("http", "websocket")
            and not self.allow_remote
            and not is_loopback(host_name(Headers(scope=scope).get("host")))
        ):
            await PlainTextResponse("Invalid host header", status_code=400)(scope, receive, send)
            return
        await self.app(scope, receive, send)


class ApiTokenMiddleware:
    """401 unless an `/api` request carries the install's bearer token. Exempt: the
    `/api/session` bootstrap (it checks `is_local` itself) and, for local GET / HEAD only,
    the media files tags load. WebSockets authenticate in their first message instead
    (browsers cannot set the header there)."""

    def __init__(self, app: ASGIApp, *, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not path.startswith("/api/") or path == SESSION_PATH:
            await self.app(scope, receive, send)
            return
        if (
            scope["method"] in _READ_METHODS
            and _TOKENLESS_LOCAL_READS.match(path)
            and is_local(scope)
        ):
            await self.app(scope, receive, send)
            return
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
