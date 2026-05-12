# Facebook connector setup

Impact Crater posts videos to a **Facebook Page** via the Graph API. Personal-profile posting was deprecated; only Pages can post via the API.

Unlike Instagram, the Page Videos endpoint accepts inline multipart binary, so **no public URL / ngrok required**.

## Step 1 — make sure you have a Page

You need at least one Facebook **Page** you can post to. Personal timeline doesn't qualify. <https://www.facebook.com/pages/create> if you don't have one.

## Step 2 — Meta for Developers app

Same app as the Instagram setup ([instagram-setup.md](./instagram-setup.md)). If you've already done that, skip to Step 3.

Otherwise:

1. <https://developers.facebook.com/apps> → New app → Business → use case: Other.
2. **Add Product → Facebook Login for Business** (or just "Facebook Login").
3. **App Review → Permissions**:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`

   These work in dev mode for accounts you've added as testers.

## Step 3 — get a Page access token

In **Graph API Explorer** (<https://developers.facebook.com/tools/explorer/>):

1. Generate a User Access Token with all three scopes above.
2. Query `me/accounts` → find the Page → note its `id` (= `IC_FACEBOOK_PAGE_ID`) and its `access_token` (this is a **Page** access token — different from the user token; it's what you want).

User-to-Page-token exchange gives you a Page token that lasts about an hour. To get a **long-lived Page token** (no expiry for some Pages):

```
# 1. Get long-lived USER token
curl "https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id={APP_ID}&client_secret={APP_SECRET}&fb_exchange_token={SHORT_USER_TOKEN}"

# 2. Use the long-lived user token to get a long-lived PAGE token
curl "https://graph.facebook.com/v21.0/me/accounts?access_token={LONG_USER_TOKEN}"
```

The `access_token` in the second response is `IC_FACEBOOK_PAGE_ACCESS_TOKEN`.

## Step 4 — set the env vars

```
set IC_FACEBOOK_PAGE_ACCESS_TOKEN=PASTE_PAGE_TOKEN
set IC_FACEBOOK_PAGE_ID=PASTE_PAGE_ID
```

Restart the server. The Approve & publish modal should now show a green dot next to Facebook.

## Visibility mapping

| Impact Crater visibility | Facebook behavior |
|---|---|
| `public` | `published=true` — visible on the Page wall |
| `unlisted` | `published=false`, `unpublished_content_type=DRAFT` — saved as a Draft in the Page's drafts inbox |
| `private` | **rejected** — no such mode on the Page Videos API; use YouTube for true-private posts |

## Step 5 — test with `visibility=unlisted` (Draft)

Drafts are the safest test path on Facebook — they sit in the Page's drafts inbox and aren't visible on the wall. Once you confirm the upload + audit-log + permalink fields work, switch to `public`.

## Caveats

- **Limit: 10 GB per upload**. Stage 7 renders are nowhere near.
- **Posting cadence**: aggressive automated posting can flag the Page. Keep test runs sparse.
- **Permalink fetch is best-effort**. The video is posted regardless; if the permalink fetch fails, the connector falls back to a deterministic `facebook.com/{page_id}/videos/{video_id}` URL in the audit row.

## Troubleshooting

- **400 `Invalid OAuth access token`** — token expired (Page tokens can expire after 90 days). Re-mint via Step 3.
- **400 `(#100) Tried accessing nonexisting field`** — wrong Page ID, or the token's scopes are wrong.
- **400 `(#10) Application does not have permission`** — your app's `pages_manage_posts` was rejected at App Review (only matters in production mode; dev mode is fine for tester accounts).
