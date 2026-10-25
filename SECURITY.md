# Security policy

Impact Crater is a self-hosted, single-user desktop web app. This page says what that means for your exposure today, where your secrets live, and how to report a problem. It describes the code on `master` as of 2026-10-25; there is no tagged release yet, so there are no "supported versions" — the current `master` is the only version.

## Threat model and current exposure

- **The server binds to loopback by default.** `impact-crater` starts FastAPI on `127.0.0.1` and a free local port (`--host` and `--port` exist). Nothing else on your network can reach it unless you bind to a non-loopback address or tunnel the port.
- **The HTTP API and the job WebSocket have no authentication and no origin check today.** Any process running as you, and any web page open in your browser that can make requests to `127.0.0.1:<port>`, can read the folders you point the app at, change settings, start jobs that spend your API budget, and trigger a publish. Hardening — a per-install bearer token, a WebSocket origin check, and a refusal to bind a non-loopback host without an explicit `--allow-remote` — is tracked as S-3.11.3 in [`project/`](./project/BOARD.md) and lands before any tunnel is used for a real post.
- **Do not expose the port.** In particular, the Instagram setup guide's tunnel (`IC_PUBLIC_BASE_URL`) would expose the whole unauthenticated API, not just the rendered video. Treat that guide as not usable for a real post until S-3.11.3 lands.
- **Publishing is dry-run by default.** `IC_PUBLISH_DRY_RUN` is on unless you set it to `0`; nothing is posted to any platform, and every publish still requires your explicit Approve click.

## Where your secrets live

- **Provider API keys** (Anthropic, Google) are stored in the SQLite database under `~/.impact-crater/db/`, Fernet-encrypted at rest. The key file is `~/.impact-crater/db/.fernet-key`, generated on first use.
- **The key file is only as protected as your user account.** On Linux and macOS it is `chmod 0600`. On Windows the permission hardening is a no-op: the file inherits your user-profile ACL, so any process running as you (and local administrators) can read it — the same exposure as the database beside it. Backup, restore and key-loss recovery are documented in [ADR-0013 → Key management](./docs/architecture/ADR-0013-connector-layer.md#2026-10-25--key-management-s-2135).
- **Connector credentials** (YouTube, Instagram, Facebook) are read from environment variables you set in your own shell or launcher script, never from the repo. `.gitignore` excludes `.env*`, `*.key`, `.fernet-key` and the personal `start-impact-crater.*` launchers.
- **Never commit** API keys, refresh tokens or the key file. If one lands in a commit, rotate it at the provider first and then rewrite history.

## What leaves your machine

- Downscaled renditions of your photos and video scene frames, their captions and your brief go to the AI providers you configured (Anthropic and Google) over their APIs. Images are sent as re-encoded renditions, not original files; EXIF stripping is not yet applied on that path (tracked as S-3.1.4).
- A render reaches a social platform only after you approve it and only when dry-run is off.
- Nothing is sent to the project maintainer. There is no telemetry upload; `~/.impact-crater/telemetry.jsonl` is a local file.

## Reporting a vulnerability

Please do not open a public issue with exploit details.

1. **Preferred:** GitHub's private vulnerability reporting on `khoks/impact-crater` (Security tab → "Report a vulnerability"). As of 2026-10-25 this is **not yet enabled** on the repository; enabling it is on the maintainer's list.
2. **Until then:** open a GitHub issue titled "Security: request private contact" that contains **no details** of the issue. The maintainer will reply with a private channel.

You can expect an acknowledgement within seven days. Fixes land on `master` through the normal pull-request flow and are credited to the reporter unless you ask otherwise. Coordinated disclosure is appreciated; there is no bounty programme.

## Out of scope

- Issues in the third-party services the app calls (Anthropic, Google, YouTube, Meta). Report those to the provider.
- Attacks that require code already running as your user — the key file and the database are readable by design in that position (see the key-management note above).
- The behaviour of the AI models themselves (quality, bias, hallucination); those are product issues, not vulnerabilities.
