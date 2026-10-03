# X

What the integration does, and the constraints that shaped it.

Code: `backend/platforms/x/`, `backend/publishing/publishers/x.py`,
`frontend/src/platforms/x/`.

---

## Setting up the app

X Developer Console:

1. The developer account is on **pay-per-use**: credits are bought up front,
   and every post spends them ($0.015, or $0.20 when the text holds a URL).
   There is no free posting tier any more.
2. Create an app and, under **User authentication settings**, enable
   **OAuth 2.0** with type **Web App, Automated App or Bot** (a confidential
   client) and permissions **Read and write**.
3. Callback URI: `http://localhost:5173/api/social/x/callback`. If X refuses
   a localhost callback, set `PUBLIC_REDIRECT_ORIGIN` to a tunnel and register
   `${PUBLIC_REDIRECT_ORIGIN}/api/social/x/callback`, as in
   `docs/platforms/tiktok.md`.
4. Put the OAuth 2.0 **Client ID** and **Client Secret** in `X_CLIENT_ID` and
   `X_CLIENT_SECRET`. The desktop's pair shipped in its bundle and is
   compromised; use a new one.

---

## Authorisation

- OAuth 2 authorisation code with S256 PKCE (`pkce.s256_challenge`), at
  `https://x.com/i/oauth2/authorize`.
- Scopes: `tweet.read tweet.write users.read media.write offline.access`.
  `media.write` is what the upload endpoints require; `offline.access` is what
  issues a refresh token.
- The token endpoint takes the client credentials as HTTP Basic, the only
  provider here that does. They go through aiohttp's `auth=`, never in the
  form body.
- Access tokens last two hours. Refresh tokens are single-use: every refresh
  returns a new one, and reusing the old one fails with "Value passed for the
  token was invalid". The refresh lease on `SocialAccount` keeps two workers
  from spending the same one.
- Disconnecting revokes the refresh token, then the access token. A failure of
  one does not stop the other.
- The account is identified by the X user id; its display name is the
  `@username`.

---

## Limits

Kept from the desktop client on purpose, although X now accepts far more on a
post (8 GB and 20 minutes for a standard account):

| Limit | Value |
| --- | --- |
| Size | 512 MiB |
| Duration | 0.5 s to 140 s |
| Types | `video/mp4`, `video/quicktime` |
| Text | 280 UTF-16 units |

The text is `caption_of(title, description, hashtags)`, as on Instagram and
TikTok. It is counted in UTF-16 units on both sides so the browser and the
server agree. X's own weighted count differs (a URL counts as 23, CJK as 2),
so a text near the limit can still be refused by X.

---

## Upload

- `POST /2/media/upload/initialize` with `media_type`, `total_bytes` and
  `media_category=tweet_video`, sent once.
- `POST /2/media/upload/{id}/append`, multipart, with `segment_index` and the
  segment. Segments are `min(PLATFORM_CHUNK_BYTES, 4 MiB)`: X caps them at
  5 MB.
- `POST /2/media/upload/{id}/finalize`, sent once.

An upload is not resumed: a worker that stops leaves the target to
`StaleTargetSweeper`, and a retry initializes a new media id. A segment that met
an outage is sent again with the same index (`RetryPolicy`); re-sending a
segment index is harmless.

---

## Publishing

X has no native scheduling, so the capability is `deferredUpload`: the beat
sweep starts the upload at `publish_at`.

After the upload, the target is `processing`. Each confirmation asks
`GET /2/media/upload?command=STATUS&media_id=…`:

- `pending` or `in_progress` — ask again later;
- `failed` — the target fails with X's reason;
- `succeeded` — the post is created with `POST /2/tweets`, and the target
  completes with `https://x.com/i/web/status/<id>`.

The post is sent **once**. Before sending it, `CommitGuard` writes
`commit_started` into `confirmation_state`:

- if X refuses (a 4xx, a spent credit balance, a duplicate post) the marker is
  removed and the target fails with X's words;
- if the token is rejected the marker is removed, the token refreshed and the
  post sent once more;
- if X does not answer (a network error or a 5xx) the marker stays and the
  target fails as `unconfirmed` with "check X before publishing again". A
  confirmation delivered again finds the marker and fails the same way, so a
  dying worker never posts twice. A retry the person asks for clears the
  marker and starts over: they were told to check X first.

Options, sent only when they differ from the default: `reply_settings`,
`made_with_ai`, `paid_partnership`, `for_super_followers_only`. X refuses the
last one for an account without Super Follows.

---

## Errors

X answers with a problem body, `{title, detail, type, status}`, or with an
`errors` array. The part of `type` after `/2/problems/` decides the failure:
`usage-capped` (credits spent) is `rate_limited`; `client-forbidden` means the
app lacks access to the endpoint and is `misconfigured`.
