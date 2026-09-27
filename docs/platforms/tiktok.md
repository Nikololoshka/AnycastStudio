# TikTok

What the integration does, and the constraints that shaped it.

Code: `backend/platforms/tiktok/`, `backend/publishing/publishers/tiktok.py`,
`frontend/src/platforms/tiktok/`.

---

## Setting up the app

TikTok for Developers:

1. Create an app of platform type **Desktop**. The web type requires an HTTPS
   redirect on a verified domain, and this app runs on `localhost`. The desktop
   type accepts a `localhost` redirect, uses the same authorize endpoint, and
   requires PKCE.
2. Add **Login Kit** and the **Content Posting API** with **Direct Post**.
3. Scopes: `user.info.basic`, `video.publish`.
4. Redirect URI: `http://localhost:5173/api/social/tiktok/callback`.
5. `TIKTOK_CLIENT_KEY` and `TIKTOK_CLIENT_SECRET` go in `backend/.env`.

The pair that shipped in the desktop bundle is public and must not be reused.

When the app gets a real domain, switch it to the web type and register
`<PUBLIC_ORIGIN>/api/social/tiktok/callback`. The code does not change.

### Testing a web-type app locally

A web-type app accepts only an HTTPS redirect. Put a tunnel in front of Django
and send only the OAuth redirect through it:

1. `ngrok http 8000 --domain=<name>.ngrok-free.app`
2. `backend/.env`: `PUBLIC_REDIRECT_ORIGIN=https://<name>.ngrok-free.app`,
   `PUBLIC_ORIGIN` stays `http://localhost:5173`.
3. Register `https://<name>.ngrok-free.app/api/social/tiktok/callback`.

Keep using the app on `localhost:5173`. The callback lands on the tunnel,
where the browser has no session cookie, so Django sends it on unchanged to
the same path on `PUBLIC_ORIGIN` and handles it there. The token exchange
still names the tunnel's redirect URI, as TikTok requires. The redirect origin
applies to every provider, so while it is set YouTube needs the tunnel's
callback registered in Google Cloud as well.

---

## Sign-in

- TikTok's PKCE is not RFC 7636: the challenge is the SHA-256 of the verifier
  in **lowercase hex**, not base64url. `TikTokProvider.code_challenge` does
  this; the verifier itself is generated and stored like Google's.
- The token request needs `client_secret` even with PKCE.
- TikTok **rotates the refresh token** on every refresh. Two simultaneous
  refreshes would burn each other's token, which is why a refresh claims a
  lease first (see `backend/docs/social.md`).
- The access token lives 24 hours, the refresh token a year.
- Revoking takes the **access** token, unlike Google.
- The account is identified by `open_id`. `user.info.basic` has no username;
  the one in a post link comes from `creator_info`.

---

## Audit

Until TikTok audits the app, every post is `SELF_ONLY`, and only to a private
account (`unaudited_client_can_only_post_to_private_accounts`). A sandbox
allows 10 test accounts.

The composer already follows TikTok's UX rules for the audit:

- the creator's nickname is shown, from `creator_info`;
- **who can watch** has no default and is chosen for every post; it is not
  remembered between sessions, and only the options `creator_info` offers are
  listed;
- comments, duet and stitch are shown switched off and locked when the creator
  turned them off in the TikTok app;
- the video's length is checked against `max_video_post_duration_sec`;
- commercial content is disclosed as **your brand** (`brand_organic_toggle`)
  and/or **branded content** (`brand_content_toggle`), and branded content
  cannot be private;
- the Music Usage Confirmation, and the Branded Content Policy when it applies,
  are shown next to the Publish button.

---

## Uploading

Content Posting API, Direct Post, `FILE_UPLOAD`:

1. `creator_info/query` — refuse a privacy level the creator is not offered or
   a video longer than allowed, before any byte is sent.
2. `post/publish/video/init/` — announces `video_size`, `chunk_size` and
   `total_chunk_count`; returns `publish_id` and `upload_url`.
3. `PUT upload_url` for each chunk with `Content-Range`, no bearer token. The
   intermediate chunks answer 206, the last one must answer 201.

Chunks are `PLATFORM_CHUNK_BYTES` (8 MiB). TikTok counts chunks by rounding
down, so the last chunk carries the remainder. A file smaller than a chunk goes
in one piece. TikTok accepts chunks of 5–64 MB, a last chunk of up to 128 MB,
and at most 1,000 chunks.

The caption is the title, the description and the hashtags, separated by blank
lines, at most 2,200 UTF-16 units.

**Resuming.** TikTok cannot say how much it has received, so `resume_state`
records the next chunk to send, and the upload URL with its expiry. The URL
lives an hour; we treat it as 55 minutes. A worker that restarts inside that
window continues at the next chunk. After it, the upload starts over with a new
`init`; the abandoned `publish_id` never publishes, so no post is duplicated.

---

## Publishing

Direct Post publishes by itself once TikTok has processed the file, which takes
from seconds to minutes. The target stays `processing` while
`post/publish/status/fetch/` is polled (see `backend/docs/publishing.md`).

- `PUBLISH_COMPLETE` completes the target. A public post has an id in
  `publicaly_available_post_id` — TikTok's spelling — and becomes
  `https://www.tiktok.com/@<username>/video/<id>`. A private post has no link.
- `FAILED` fails the target with TikTok's `fail_reason` in `details`.
- No answer within 30 minutes fails the target with a message to check TikTok.

There is no native scheduling. A scheduled post is uploaded at its time by the
beat sweep, and appears a few minutes later.

---

## Errors

TikTok puts `{"error": {"code", "message", "log_id"}}` in every response,
including 200s. `platforms/tiktok/api.py` treats a code other than `ok` as a
failure and keeps the code in `details`.

| `fail_reason` | Type |
| --- | --- |
| `file_format_check_failed`, `duration_check_failed`, `frame_rate_check_failed`, `picture_size_check_failed` | `file` |
| `spam_risk_text`, `privacy_level_check_failed`, `unaudited_client_can_only_post_to_private_accounts` | `validation` |
| `auth_removed` | `authentication` |
| `internal` and the rest | `platform` |

`internal` is TikTok's own failure. It is not retried automatically, like any
other failure: the person decides.

---

## Limits

- `init`: 6 requests a minute per token. `status/fetch`: 30. `creator_info`:
  20, which is why the endpoint that serves it caches for 5 minutes.
- Videos up to 4 GiB, MP4, MOV or WebM, 3 s to the creator's maximum (usually
  10 minutes, up to 60), 360–4096 px on each side.
