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
2. **Required on every `/api` request.** A pure-ASGI middleware returns 401 unless `Authorization: Bearer <token>` matches, compared in constant time. That covers reads too, because folder listings, project briefs and settings are personal data, and a tokenless `GET /api/folder/scan` let any web page make the server walk a disk or, on Windows, open an SMB session to a UNC path.
   - A few files that `<img>` and `<video>` tags load stay tokenless for **local** requests only: `/api/media/{hash}/thumb.jpg`, `/api/snapshots/{id}/render.mp4` and `/api/feedback/{id}/screenshot.png`, plus `/api/health` and the API docs.
   - The OpenAPI schema declares the bearer scheme, so `/api/docs` can send it.
3. **What counts as local** (`api_auth.is_local`). All three must hold: a loopback client address, a loopback Host header, and no `Forwarded` / non-loopback `X-Forwarded-For` hop.
   - The Host condition stops a DNS-rebinding page even when `--allow-remote` lifts the Host check.
   - The forwarding condition stops a tunnel or `vite --host` from passing remote callers off as 127.0.0.1. The Vite proxy sets `xfwd`, so it reports the browser's real address.
4. **Host check.** `HostGuardMiddleware` answers 400 unless the Host header names this machine (`localhost`, `127.0.0.1`, `[::1]`). `--allow-remote` lifts it, but the token and the local rule above still apply.
5. **How the page gets the token.**
   - The SPA fallback serves `index.html` with `<meta name="impact-crater-api-token">` (no-store) to local requests only.
   - Under the Vite dev server, the page reads `GET /api/session`, which answers local requests and returns 403 to everyone else.
   - There is no CORS, so a page on another origin can read neither.
   - The fallback only serves files inside the built frontend folder; `..` segments and absolute paths in the decoded URL path are refused.
6. **WebSocket.** The handshake is refused (1008) when an `Origin` is present and is neither loopback nor the server's own Host. After `accept`, the first message must be `{"type": "auth", "token": …}` within 10 s, otherwise the socket closes with 1008. Browsers cannot set headers on a WebSocket, and query strings leak into logs, so the token travels in a message.
7. **CLI.** A non-loopback `--host` exits with code 2 unless `--allow-remote` is passed. With the flag, the CLI prints a warning naming the token file and sets `IMPACT_CRATER_ALLOW_REMOTE=1` for the app factory.

## Consequences

- A remote browser gets no token automatically, so the UI is effectively loopback-only even with `--allow-remote`. Remote use means API clients that send the header. A remote UI, a signed media URL for Instagram (the tunnel in the Instagram guide is refused until then) and the hosted mode (I-5) are separate decisions.
- A forwarder that rewrites Host to `localhost` and adds no `X-Forwarded-For` is indistinguishable from a local browser. Do not put one in front of the port.
- Review: an independent pass on the first version of this change found that with `--allow-remote` the SPA fallback served any file (traversal) and `/api/session` handed the token to a rebinding page. It also found that forwarders looked local and that tokenless reads let any page trigger folder scans. All are fixed as described above, with tests.
- Anything running as the user can read the token file. That is the same position as the Fernet key and the database, and it is out of scope in `SECURITY.md`.
- Every frontend call goes through `apiFetch` (`frontend/src/api/client.ts`). A new endpoint called with a bare `fetch` gets a 401.
- Tests create clients with `base_url="http://127.0.0.1"` and `headers=api_auth.auth_header()`. `tests/test_api_auth.py` covers 401s, tokenless media, the Host check (IPv6 included), rebinding under `--allow-remote`, forwarded requests, `/api/session`, UNC folder paths, the OpenAPI scheme, dist-folder containment, the WebSocket auth and Origin checks, the CLI refusal and the meta injection.
