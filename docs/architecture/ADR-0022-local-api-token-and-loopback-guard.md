# ADR-0022 — Local API token and loopback guard

**Status:** Accepted
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-11-03
**Phase:** mvp-hardening (restart Phase 1 item 3b, S-3.11.3)
**Amends:** [ADR-0005](./ADR-0005-process-topology-language-stack.md) (one FastAPI process serving the API and the SPA on loopback) by adding an authentication layer; the process topology is unchanged.

## Context

ADR-0005 put the whole app in one FastAPI process bound to `127.0.0.1`. Nothing checked who was calling. The 2026-10-24 restart audit (`docs/roadmap/LANDSCAPE-AND-PLAN-2026-10-24.md` §4.2) and the 2026-10-25 review of `SECURITY.md` found three gaps:

- Any web page could open the job WebSocket, which checked no Origin.
- The server did not validate the Host header, so a DNS-rebinding page could get same-origin access to every route.
- `impact-crater --host 0.0.0.0` exposed every mutating route with no warning: settings, setup, job submit, render, refine, publish, feedback, persons and workplan.

The Instagram connector needs a public media URL, and in-app YouTube OAuth (S-3.3.5) needs a loopback callback. Both would widen this exposure, so the guard comes first.

## Decision

1. **Per-install token.** On first start the server writes `secrets.token_urlsafe(32)` to `~/.impact-crater/.api-token`, hardened like the Fernet key: `0600` on POSIX, the user-profile ACL on Windows.
2. **Required on mutating requests.** A pure-ASGI middleware returns 401 unless `Authorization: Bearer <token>` matches, compared in constant time. It covers every `POST/PUT/PATCH/DELETE` under `/api/`, and every `/api/` request from a non-loopback client.
   - Loopback reads (media, thumbnails, `render.mp4`, snapshots) stay tokenless, so `<img>` and `<video>` tags keep working. They are reachable only from this machine and only under a loopback Host name.
3. **Host check.** `TrustedHostMiddleware` accepts `localhost` and `127.0.0.1` only. This is what defeats DNS rebinding. `--allow-remote` widens it to any host, and the token is still required.
4. **How the page gets the token.**
   - The SPA fallback serves `index.html` with `<meta name="impact-crater-api-token">` (no-store) to loopback clients only.
   - Under the Vite dev server, the page reads `GET /api/session`, which answers loopback clients and returns 403 to everyone else.
   - There is no CORS, so a page on another origin can read neither.
5. **WebSocket.** The handshake is refused (1008) when an `Origin` is present and is neither loopback nor the server's own Host. After `accept`, the first message must be `{"type": "auth", "token": …}` within 10 s, otherwise the socket closes with 1008. Browsers cannot set headers on a WebSocket, and query strings leak into logs, so the token travels in a message.
6. **CLI.** A non-loopback `--host` exits with code 2 unless `--allow-remote` is passed. With the flag, the CLI prints a warning naming the token file and sets `IMPACT_CRATER_ALLOW_REMOTE=1` for the app factory.

## Consequences

- A remote browser gets no token automatically, so the UI is effectively loopback-only even with `--allow-remote`. Remote use means API clients that send the header. A remote UI, a signed media URL for Instagram and the hosted mode (I-5) are separate decisions.
- Anything running as the user can read the token file. That is the same position as the Fernet key and the database, and it is out of scope in `SECURITY.md`.
- Every frontend call goes through `apiFetch` (`frontend/src/api/client.ts`). A new endpoint called with a bare `fetch` gets a 401 if it mutates.
- Tests create clients with `base_url="http://127.0.0.1"` and `headers=api_auth.auth_header()`. `tests/test_api_auth.py` covers 401s, the Host check, `/api/session`, the WebSocket auth and Origin checks, the CLI refusal and the meta injection.
