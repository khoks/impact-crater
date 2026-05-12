# Instagram connector setup

Impact Crater posts videos to Instagram as **Reels** via the Meta Graph API.

## Hard prerequisites — read these first

- **Personal Instagram accounts cannot post via the API.** Only **Business** or **Creator** accounts can.
- The Business/Creator account must be **linked to a Facebook Page** (the same kind of linkage used for ads + insights).
- The Graph API cannot accept video bytes inline. It requires a **publicly fetchable HTTPS URL** that Meta's servers can pull the MP4 from. For dev, this means exposing your local Impact Crater server (port 8765) through an ngrok-style tunnel.

If those don't apply to your account, switch to a different platform.

## Step 1 — convert your IG account to Business/Creator

In the Instagram app → Settings → Account → switch to a Business or Creator account. Link it to a Facebook Page if you don't already have one.

## Step 2 — Meta for Developers app

1. Go to <https://developers.facebook.com/apps>.
2. Create a new app → use case: **Other** → type: **Business**.
3. **Add Product → Instagram Graph API**.
4. **App Roles → Roles**: add yourself as a tester.
5. **App Review → Permissions and Features**:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_show_list`
   - `pages_read_engagement`

   For dev these don't need to be App-Review-approved — they work in development mode against accounts you've added as testers.

## Step 3 — get the Instagram Business Account ID

In **Graph API Explorer** (<https://developers.facebook.com/tools/explorer/>):

1. Select your app from the dropdown.
2. Generate a User Access Token with all four scopes above.
3. Query `me/accounts` → find your Page → note its `id`.
4. Query `{page_id}?fields=instagram_business_account` → note the returned `id`. **This is `IC_INSTAGRAM_USER_ID`.**

## Step 4 — mint a long-lived access token

User tokens last about an hour. Long-lived tokens last about 60 days. To convert:

```
curl "https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id={APP_ID}&client_secret={APP_SECRET}&fb_exchange_token={SHORT_TOKEN}"
```

The `access_token` in the response is `IC_INSTAGRAM_ACCESS_TOKEN`. Refresh it every ~50 days.

## Step 5 — expose your server via ngrok (for real posting)

```
ngrok http 8765
```

Note the `https://abcd-12-34-56.ngrok-free.app` URL. Set:

```
set IC_PUBLIC_BASE_URL=https://abcd-12-34-56.ngrok-free.app
```

Restart Impact Crater. Meta's servers will fetch the rendered MP4 from `https://abcd-.../api/snapshots/{id}/render.mp4`.

`IC_PUBLIC_BASE_URL` is **not** required in dry-run mode — the connector validates the request without building the URL.

## Step 6 — set the env vars

```
set IC_INSTAGRAM_ACCESS_TOKEN=PASTE_LONG_LIVED_TOKEN
set IC_INSTAGRAM_USER_ID=PASTE_IG_BUSINESS_ACCOUNT_ID
set IC_PUBLIC_BASE_URL=https://your-ngrok-tunnel.ngrok-free.app
```

## Caveats

- **Visibility is fixed**. Reels are always public — Impact Crater's connector rejects `visibility=private/unlisted` up front.
- **Reel duration cap is 90 seconds**. The connector validates this against the render before posting.
- **Caption is title + description + hashtags concatenated**. The Graph API has a single 2200-char caption field, not separate title/description.
- **Permalink takes a few seconds to become available** after `media_publish`. The connector polls.

## Troubleshooting

- **`The video URL is not accessible`** — Meta couldn't fetch from `IC_PUBLIC_BASE_URL`. Check the tunnel is alive (`curl https://your-tunnel/api/setup/status`).
- **`status_code=ERROR`** during container polling — usually codec/container incompatibility. Re-encode in H.264 baseline (Stage 7 already does this).
- **`The Instagram User is restricted`** — your IG account is in a restricted state. Check IG app for warnings.
