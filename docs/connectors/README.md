# Connectors — multi-platform publishing setup

Impact Crater publishes the rendered MP4 to **YouTube**, **Instagram**, and **Facebook** as of v1 (multi-platform expansion of ADR-0013). Each platform reads credentials from process env vars; nothing is stored unencrypted on disk.

## Dry-run by default

Dry-run is on until you switch it off. A dry-run publish validates the request, posts nothing, returns a synthetic `dry-run-...` external id and writes an audit row tagged `<platform> (dry-run)`. Every audit row records the SHA-256 of the render you approved.

- **Settings → Publishing** has the switch. It takes effect when you save; no restart needed.
- **`IC_PUBLISH_DRY_RUN`**, when set to a non-empty value, overrides the switch and locks it: `0` / `false` / `no` / `off` means live, anything else means dry-run. Unset or empty leaves the decision to the switch (D-060).
- What a dry-run checks differs by platform. YouTube validates without credentials. Instagram and Facebook refuse until their credentials are set, so a dry-run there is also a credential check.

Live posting is irreversible: every successful call is a real post. The publish panel shows a `DRY-RUN` badge, and the caption under Approve says which mode is active.

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
| **Common** | `IC_PUBLISH_DRY_RUN` (optional; overrides the Settings switch: `0` = live, other non-empty values = dry-run) |

## Quick start — verify your env without posting anything

1. Set the env vars for the platform(s) you've configured.
2. `start-impact-crater.bat` (or your usual launcher).
3. Open a Story Video → Approve & publish → see the platform's badge:
   - **green dot** = credentials set
   - **grey dot** = credentials not set
4. Click Publish. With dry-run on you get a `Dry-run validated.` panel showing the would-be external URL. The panel only offers the visibilities each platform accepts: YouTube private / unlisted / public, Instagram public, Facebook draft / public.

When you're ready to actually post, switch dry-run off in Settings → Publishing (or set `IC_PUBLISH_DRY_RUN=0`) and try again. Start with YouTube at `private` (the default) so the test post stays off your channel.
