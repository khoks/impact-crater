# Connectors — multi-platform publishing setup

Impact Crater publishes the rendered MP4 to **YouTube**, **Instagram**, and **Facebook** as of v1 (multi-platform expansion of ADR-0013). Each platform reads credentials from process env vars; nothing is stored unencrypted on disk.

## Dry-run by default

`IC_PUBLISH_DRY_RUN=1` (default) — every publish call validates the request, talks to nothing remote, and returns a synthetic `dry-run-...` external id. Audit-log rows are tagged `<platform> (dry-run)`.

`IC_PUBLISH_DRY_RUN=0` — live posting. **Use this only when you're sure** — every successful call is irreversible.

The publish modal shows the `DRY-RUN` badge when dry-run is on. Restart the server after toggling the env var.

## Per-platform setup

- [YouTube](./youtube-setup.md) — Google Cloud OAuth refresh token
- [Instagram](./instagram-setup.md) — Meta Graph API + IC_PUBLIC_BASE_URL (ngrok)
- [Facebook](./facebook-setup.md) — Meta Graph API Page token

## Env-var summary

| Platform | Required env vars |
|---|---|
| **YouTube** | `IC_YOUTUBE_CLIENT_ID`, `IC_YOUTUBE_CLIENT_SECRET`, `IC_YOUTUBE_REFRESH_TOKEN` |
| **Instagram** | `IC_INSTAGRAM_ACCESS_TOKEN`, `IC_INSTAGRAM_USER_ID`, `IC_PUBLIC_BASE_URL` (for real posts) |
| **Facebook** | `IC_FACEBOOK_PAGE_ACCESS_TOKEN`, `IC_FACEBOOK_PAGE_ID` |
| **Common** | `IC_PUBLISH_DRY_RUN` (default `1` = dry-run; `0` = live) |

## Quick start — verify your env without posting anything

1. Set the env vars for the platform(s) you've configured.
2. `start-impact-crater.bat` (or your usual launcher).
3. Open a Story Video → Approve & publish → see the platform's badge:
   - **green dot** = creds detected in env
   - **grey dot** = creds missing
4. Click Publish — with dry-run on, you'll get a `Dry-run validated.` panel showing the would-be external URL.

When you're ready to actually post, set `IC_PUBLISH_DRY_RUN=0`, restart, and try again — start with YouTube + `visibility=private` so the test post stays off your channel.
