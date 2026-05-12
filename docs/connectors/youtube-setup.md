# YouTube connector setup

Impact Crater uses the **YouTube Data API v3** to upload rendered MP4s. The auth model is OAuth 2.0 with a long-lived refresh token. You do the consent dance **once**, get a refresh token, drop it in env, and the server uses it on every publish.

## What you need

1. A **Google Cloud project** with the YouTube Data API v3 enabled.
2. An **OAuth client ID** (type: Desktop or Web — Desktop is simpler).
3. A **refresh token** with the `youtube.upload` scope, minted against your YouTube channel.

## Step 1 — Google Cloud Console

1. Go to <https://console.cloud.google.com/>.
2. Create a new project (or pick an existing one).
3. **APIs & Services → Library** → search "YouTube Data API v3" → Enable.
4. **APIs & Services → OAuth consent screen**:
   - User type: **External**.
   - Add yourself as a test user.
   - Add the scope `https://www.googleapis.com/auth/youtube.upload`.
5. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Desktop app** (simplest).
   - Note the client ID + secret.

## Step 2 — mint a refresh token

The simplest path is a one-time helper script. Save this as `mint-yt-token.py` somewhere outside the repo:

```python
"""Mint a YouTube refresh token. Run once; save the printed token."""
from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_ID = "PASTE_CLIENT_ID.apps.googleusercontent.com"
CLIENT_SECRET = "PASTE_CLIENT_SECRET"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

flow = InstalledAppFlow.from_client_config(
    {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    },
    scopes=SCOPES,
)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
print("\nIC_YOUTUBE_REFRESH_TOKEN=", creds.refresh_token, sep="")
```

Run it from the `.venv`:

```
.venv\Scripts\python.exe mint-yt-token.py
```

Browser opens → log in to the YouTube account you want to publish to → grant access → terminal prints `IC_YOUTUBE_REFRESH_TOKEN=...`.

## Step 3 — set the env vars

Set in your shell (or your launcher's env block — `start-impact-crater.bat` inherits process env):

```
set IC_YOUTUBE_CLIENT_ID=PASTE_CLIENT_ID.apps.googleusercontent.com
set IC_YOUTUBE_CLIENT_SECRET=PASTE_CLIENT_SECRET
set IC_YOUTUBE_REFRESH_TOKEN=PASTE_REFRESH_TOKEN
```

Restart the server. The Approve & publish modal should now show a green dot next to YouTube.

## Step 4 — test with `visibility=private`

**Start with private**. Private uploads land in your channel's manager but are not visible to anyone but you. Once you're satisfied, you can change to `unlisted` or `public`.

1. Approve & publish → pick YouTube → visibility = `private` → Publish.
2. The result shows `external_url: https://www.youtube.com/watch?v=...` — open it in a fresh tab while logged into the right YouTube account.

## Troubleshooting

- **`invalid_grant`** — refresh token expired or was revoked (e.g. you changed Google password). Re-run the mint script.
- **403 `quotaExceeded`** — YouTube Data API has a default daily quota of 10,000 units. A single upload is 1,600 units (~6 uploads/day). Request a quota increase in Cloud Console or wait until UTC midnight.
- **400 `mediaContentType`** — render isn't a valid MP4. Investigate Stage 7.
