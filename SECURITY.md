# Security policy

Impact Crater is a self-hosted, single-user desktop web app. This page says what that means for your exposure today, where your secrets live, and how to report a problem. It describes the code on `master` as of 2026-11-03; there is no tagged release yet, so there are no "supported versions" — the current `master` is the only version.

## Threat model and current exposure

- **The server binds to loopback by default.** `impact-crater` starts FastAPI on `127.0.0.1` and a free local port. A non-loopback `--host` (for example `0.0.0.0`) is refused unless you also pass `--allow-remote`, which prints a warning.
- **Every API request goes through a per-install token.** On first start the server writes a random token to `~/.impact-crater/.api-token`. It is `0600` on Linux and macOS; on Windows it inherits your user-profile ACL, like the key file below. Every `/api/` request (reads included) and the job WebSocket must carry it, or they get a 401 or are closed. The app's own page receives it automatically when it is opened from this machine; nothing else does. The design is [ADR-0022](./docs/architecture/ADR-0022-local-api-token-and-loopback-guard.md).
- **Other web pages are kept out.** The server accepts only `localhost`, `127.0.0.1` and `[::1]` as the Host name, which stops DNS-rebinding pages. It hands out the token only to a request that is local in every sense: a loopback client, a loopback Host, and no proxy hop from elsewhere. There is no CORS, so a page on another origin cannot read responses or the token. The job WebSocket refuses a foreign `Origin` and needs the token as its first message. Folder scans refuse network (UNC) paths.
- **What the token does not protect.** Thumbnails, the rendered video and feedback screenshots load without it for a browser on this machine, because `<img>` and `<video>` tags cannot send a header. A page on another site can embed those files, but it cannot read them or anything else. Any process running as you can read the token file, just as it can read the database and the key file. A proxy on your machine that forwards other callers without an `X-Forwarded-For` header makes them look local, so do not put one in front of the port (this includes running the Vite dev server with `--host`). With `--allow-remote`, devices on your network need the token for every request, including those media files, and the browser UI does not hand it to them. Remote use is for API clients you configure yourself.
- **Tunnels are refused.** A tunnel's Host name gets a 400. With `--allow-remote`, a forwarded request counts as remote and needs the token, so the Instagram guide's `IC_PUBLIC_BASE_URL` tunnel does not work for a real post. That is deliberate: real Instagram posting waits for a single expiring signed media URL, planned with the Instagram public-URL work.
- **Publishing is dry-run by default.** `IC_PUBLISH_DRY_RUN` is on unless you set it to `0`; nothing is posted to any platform, and every publish still requires your explicit Approve click.

## Where your secrets live

- **Provider API keys** (Anthropic, Google) are stored in the SQLite database under `~/.impact-crater/db/`, Fernet-encrypted at rest. The key file is `~/.impact-crater/db/.fernet-key`, generated on first use.
- **The key file is only as protected as your user account.** On Linux and macOS it is `chmod 0600`. On Windows the permission hardening is a no-op: the file inherits your user-profile ACL, so any process running as you (and local administrators) can read it — the same exposure as the database beside it. Backup, restore and key-loss recovery are documented in [ADR-0013 → Key management](./docs/architecture/ADR-0013-connector-layer.md#2026-10-25--key-management-s-2135).
- **Connector credentials** (YouTube, Instagram, Facebook) are read from environment variables you set in your own shell or launcher script, never from the repo. `.gitignore` excludes `.env*`, `*.key`, `.fernet-key` and the personal `start-impact-crater.*` launchers.
- **Never commit** API keys, refresh tokens, `.env.test` (the file the `--integration` tests read keys from) or the key file. If one lands in a commit, rotate it at the provider first and then rewrite history.

## What leaves your machine

- Downscaled renditions of your photos and video scene frames, their captions and your brief go to the AI providers you configured (Anthropic and Google) over their APIs. Images are normally sent as downscaled, re-encoded renditions (which drop EXIF as a side effect of re-encoding, not by an asserted strip step); if a rendition is missing, Stages 2 and 3 currently fall back to sending the original file. Removing that fallback and asserting EXIF/GPS removal is S-3.1.4.
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
