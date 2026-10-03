# Instagram

What the integration does, and the constraints that shaped it.

Code: `backend/platforms/instagram/`, `backend/publishing/publishers/instagram.py`,
`frontend/src/platforms/instagram/`.

---

## Setting up the app

Meta for Developers:

1. Use an app of type **Business** with **Facebook Login for Business** and
   the **Instagram Graph API**. The app the desktop broker used is fine: its
   secret never left the broker's server.
2. The Instagram account must be a **professional** account (Business or
   Creator) **linked to a Facebook Page**.
3. Scopes: `instagram_basic`, `instagram_content_publish`, `pages_show_list`,
   `pages_read_engagement`.
4. In Development mode, the people who publish are added as app testers. App
   Review is not needed for a closed circle.
5. `INSTAGRAM_CLIENT_ID` (the app id) and `INSTAGRAM_CLIENT_SECRET` go in
   `backend/.env`.

Facebook accepts only an HTTPS redirect. Use the tunnel described in
`docs/platforms/tiktok.md`:

1. `ngrok http 8000 --domain=<name>.ngrok-free.app`
2. `backend/.env`: `PUBLIC_REDIRECT_ORIGIN=https://<name>.ngrok-free.app`
3. Add `https://<name>.ngrok-free.app/api/social/instagram/callback` to
   **Valid OAuth Redirect URIs**.

---

## Sign-in

Facebook Login, no PKCE, Graph API `v25.0` (`GRAPH_VERSION` in `api.py`).

1. The code is exchanged for a short-lived user token, then for a long-lived
   one with `fb_exchange_token`. Facebook documents both as `GET`, so the app
   secret travels in the query string; only the class of a network exception
   is ever reported, and `urllib3` logs at WARNING.
2. `me/accounts` lists the Pages with their tokens. A Page in a business
   portfolio that was granted one by one is missing from it; then the granted
   ids come from `debug_token` (`granular_scopes[].target_ids`, every scope)
   and each is read by id. Those ids include Instagram accounts and
   businesses, which answer `(#100) Tried accessing nonexisting field
   (access_token)`; they are skipped.
3. The first Page with an `instagram_business_account` is used. None is a
   refusal: "No Instagram professional account is linked to a Facebook Page
   that was shared".
4. The **Page token** is stored. Taken from a long-lived user token it does not
   expire, so the account has no expiry and no refresh token. It stops working
   when the person removes the app, changes their password or loses the Page;
   then Meta answers `190`, the refresh fails, and the account asks to be
   reconnected.
5. The account is identified by the Instagram user id; the Page id is kept in
   `extra`.

Revoking asks `debug_token` whose token it is, then deletes that user's
permissions (`DELETE /{user-id}/permissions`), both with the app token
`app_id|app_secret`.

Tokens go in the `Authorization: OAuth <token>` header, never in a URL.

---

## Uploading

A Reels container with a resumable upload; no public URL is needed.

1. `POST /{ig-user-id}/media` with `media_type=REELS`, `upload_type=resumable`,
   `caption`, `share_to_feed` and `thumb_offset` (milliseconds; the composer
   shows seconds). Returns the container id. Sent once, never retried, so no
   stray container is created.
2. `POST https://rupload.facebook.com/ig-api-upload/v25.0/{container-id}` for
   each chunk, with the headers `offset` and `file_size`. Each answers
   `{"success": true}`.

Chunks are `PLATFORM_CHUNK_BYTES` (8 MiB); Meta sets no size.

The caption is the title, the description and the hashtags, separated by blank
lines, as for TikTok.

**No resuming.** An upload is not resumed: a worker that stops leaves the
target to `StaleTargetSweeper`, and a retry creates a new container. Meta
expires an unused container after 24 hours, so the abandoned one never
publishes. A piece that met an outage is sent again at the same offset
(`RetryPolicy`).

---

## Publishing

A container cannot be published until Meta has processed it. The target stays
`processing` while `confirm` polls `status_code`:

- `IN_PROGRESS` — ask again later.
- `FINISHED` — `media_publish` with `creation_id`, then `permalink` for the
  link, which is best effort.
- `ERROR` — fails as `file`, with Meta's `status` text in `details`.
- `EXPIRED` — fails as `platform`.
- `PUBLISHED` — completes without a link: an earlier `media_publish` got
  through but its answer was lost.

`media_publish` is sent once. A network failure or a 5xx asks again at the next
poll, which sees `PUBLISHED` if it went through, so a reel is never posted
twice. Any other refusal fails the target.

No answer within 30 minutes fails the target with a message to check
Instagram. There is no native scheduling: a scheduled reel is uploaded at its
time by the beat sweep.

---

## Errors

Meta answers `{"error": {"message", "code", "error_subcode", ...}}`, usually
with a 400, sometimes with a 200; rupload answers `{"debug_info": {...}}`.
`platforms/instagram/api.py` checks both on every response and keeps
`code/subcode` in `details`.

| `code` | Type |
| --- | --- |
| `190`, `102` | `authentication` — the account must be reconnected |
| `10`, `200`–`299` | `authorization` |
| `4`, `17`, `32`, `613` | `rate_limit`, not retried |
| the rest | from the HTTP status |

---

## Limits

Checked before any call, in `capabilities.py` and in the composer:

- MP4 or MOV, up to 300 MB, 3 seconds to 15 minutes;
- caption up to 2,200 characters and 30 hashtags.

Meta also allows 20 @-mentions per caption and 50 published posts a day per
account; those are left to Meta to refuse.
