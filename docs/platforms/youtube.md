# YouTube

What the integration does, and the constraints that shaped it.

Code: `backend/platforms/youtube/`.

---

## Setting up the app

Google Cloud console:

1. Enable the **YouTube Data API v3**.
2. Create an OAuth client of type **Web application**. Not Desktop — the
   desktop client used a loopback redirect, and a web client uses ours.
3. Authorised redirect URI: `http://localhost:5173/api/social/youtube/callback`
   in development, or `<PUBLIC_ORIGIN>/api/social/youtube/callback`.
4. `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET` go in `backend/.env`.

Scopes requested:

- `https://www.googleapis.com/auth/youtube.upload`
- `https://www.googleapis.com/auth/youtube`

---

## Quota — the real limit

The Data API gives a project about **10,000 units a day**. `videos.insert`
costs roughly **1,600**. That is about **six uploads a day for the whole
project**, not per person.

Consequences that are already in the code:

- `Quota.max_publications_per_day` refuses with a reason before Google refuses
  without one;
- a failed publication is **never** retried automatically — a person decides;
- a retry after the bytes already landed does not upload again; it picks up
  from `uploaded_media_id`.

Raising the limit requires a quota extension from Google, which requires an
audit.

---

## Authorising

Standard OAuth 2.0 with PKCE. Two details decide whether the connection
survives the first hour:

- `access_type=offline` **and** `prompt=consent` — without both, Google issues
  no refresh token at all;
- Google does **not** return the refresh token when refreshing, so the stored
  one must be carried forward. `TokenBundle.merged_with` does that; dropping it
  would turn a long-lived connection into a one-hour one.

Tokens are refreshed under a row lock, and shortly before they expire, so a
publication rarely waits for a token round-trip.

Every OAuth call (token, channel, revoke) goes through the same retry policy as
the upload, with three attempts instead of five: a network blip or a Google 5xx
during a refresh must not cost the person their connection. Only a real refusal
(`invalid_grant`, 400/401) marks the account for reconnecting. Three attempts
keep the callback view, which exchanges the code while the browser waits,
within a few seconds.

---

## Uploading

Google's resumable protocol, ported from the Rust command the desktop client
used:

1. `POST .../upload/youtube/v3/videos?uploadType=resumable` with the snippet
   and status, plus `X-Upload-Content-Type` and `X-Upload-Content-Length`. Keep
   the `Location` header — that is the session URI.
2. `PUT` each chunk to the session URI with
   `Content-Range: bytes <from>-<to>/<total>`.
3. `308` means "still going". **Take the offset from that reply's `Range`
   header**, not from your own arithmetic: Google may have kept less than was
   sent. A `308` **without** `Range` means Google kept nothing; the next chunk
   starts at byte 0.
4. `200` or `201` carries the video id.
5. To learn where a session stands, `PUT` to the session URI with no body and
   `Content-Range: bytes */<total>`. The answer is a `308` with `Range`, or the
   `200`/`201` with the video id if Google already has the whole file.

The chunk size is `PLATFORM_CHUNK_BYTES` (8 MiB). The desktop client used 1 MiB
for a responsive progress bar in a window; on a server that is eight times the
request overhead for no benefit.

The protocol is driven by `google-api-python-client` (`videos.insert` with a
resumable `MediaUpload` over the stored file), run in a thread so the event
loop keeps serving. The client retries a chunk that met a 5xx inside the same
session, up to `UPLOAD_RETRY_ATTEMPTS`; the bytes Google already kept are not
sent again. Progress reaches the pipeline after every chunk and is written on
whole percents.

Nothing about the session is stored. A worker that is killed mid-upload leaves
the target to `StaleTargetSweeper`, and a retry uploads the file again
(`docs/adr/0003-async-platforms.md`).

A `401` mid-upload is `token_rejected`: the token is refreshed once and the
upload starts again with it.

---

## Publishing and scheduling

`PUT .../youtube/v3/videos?part=status` sets the final visibility.

For a scheduled video, `status.publishAt` is sent **together with**
`privacyStatus: private`. YouTube ignores `publishAt` otherwise — and the video
is uploaded private in the first place for the same reason. Nothing of ours
runs at the scheduled moment; YouTube publishes it.

---

## Settings

`backend/platforms/youtube/video_options.py` mirrors
`frontend/src/platforms/youtube/settings.ts`. The frontend's copy lets the
composer render before asking the server; the backend's decides. A contract
test fails if the defaults drift apart, because otherwise a person sees one
thing and gets another.

| Setting | Default | Notes |
| --- | --- | --- |
| `privacyStatus` | `private` | Forced to `private` at upload when scheduled |
| `categoryId` | `22` | People & Blogs |
| `license` | `youtube` | |
| `madeForKids` | `false` | Sent as `selfDeclaredMadeForKids` |
| `notifySubscribers` | `true` | Query parameter, not part of the body |
| `containsSyntheticMedia` | `false` | |
| `embeddable` | `true` | |
| `publicStatsViewable` | `true` | |
| `hashtagsInDescription` | `true` | Appends up to 15 tags to the description |

Limits enforced before anything is sent: title 100 characters, description
5,000, file 128 GiB, and a MIME type from the supported list.

---

## Failure modes

| Response | Meaning | What happens |
| --- | --- | --- |
| 401 | Access token expired | `token_rejected`: refreshed once, the upload starts again |
| 403 `insufficientPermissions` | Scope revoked | `scope_missing`: the account asks to be reconnected |
| 403 `quotaExceeded` / 429 | Quota exhausted or rate limited | `rate_limited`; not retried by the pipeline |
| 400 `invalid*` | The metadata was rejected | `invalid`; not retried |
| 400 / 404 / 422 otherwise | The request was refused | `refused`; not retried |
| 5xx / 408 | Google is having trouble | `network`; the chunk is retried inside the session |
| network error | No answer at all | `network`; only the exception class is reported |

Backoff is exponential from one second to thirty, with jitter, so retries do
not arrive in lockstep. Anything the platform *decided* (401, 403, 4xx) is never
repeated: each attempt spends quota that cannot be recovered. A network error
is reported by its class only, because the exception text contains the URL
and the token request body carries `client_secret`.
