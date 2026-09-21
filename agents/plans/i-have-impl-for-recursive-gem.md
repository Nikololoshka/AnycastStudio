# X (Twitter) Video Upload — Implementation Plan

## Context

YouTube and TikTok upload are already implemented end-to-end (adapter + auth + Rust
upload-loop command). `src/platforms/x/` currently only has stub files
(`XAdapter.ts` throws `not implemented`, `XSettingsPanel.tsx` is empty, no
`XAuth.ts` exists, `auth.ts` maps `x` to `notImplemented('x')`). This plan brings
X to parity with the other two platforms, reusing the same architecture:
PKCE OAuth in TS, a chunked-upload Rust command for the network-bound loop, and
a TS adapter that composes tweet text and calls the publish REST endpoint.

Decisions confirmed with the user (see grilling session):
1. OAuth 2.0 PKCE, **confidential client** — `VITE_X_CLIENT_ID` +
   `VITE_X_CLIENT_SECRET` in `.env.local`, same shape as `YouTubeAuth`/`TikTokAuth`.
2. Chunked media upload (INIT → APPEND → FINALIZE) lives in a new Rust command
   `x_upload.rs`, mirroring `tiktok_upload.rs`'s retry/backoff/progress-channel
   pattern. FINALIZE processing is polled from TS, mirroring TikTok's
   `pollPublishStatus`. Posting the tweet (`publish()`) is a plain TS `fetch`,
   mirroring `YouTubeAdapter.publish()`.
3. Tweet text = `description` + hashtags appended as `#tag` (title stays unused;
   capabilities already declare `title: false`).
4. Text over 280 chars fails in `validate()` — no silent truncation.
5. `XSettingsPanel` stays empty for this pass.

## Files to add / change

### Rust (`src-tauri/src/commands/`)

- **New `x_upload.rs`**, modeled on `tiktok_upload.rs`:
  - `UploadCancellations`-style state (`XUploadCancellations`), same
    cancel/cancellation-flag helpers.
  - `#[tauri::command] upload_video_x(params, state, on_progress) -> Result<UploadOutcome, UploadError>`
    doing INIT → chunked APPEND loop (reuse `file_size`/`read_chunk` from
    `filesystem.rs`) → FINALIZE, reporting progress via `Channel` same as
    TikTok/YouTube. Returns `{ media_id }`.
  - `#[tauri::command] cancel_x_upload(upload_id, state)`.
  - X media upload endpoints (v2): `POST https://api.x.com/2/media/upload`
    with `command=INIT|APPEND|FINALIZE` (multipart for APPEND, chunk bytes as
    `media` field, `segment_index` incrementing). Same `with_retry`/`classify`/
    `jitter_ms` shape as the other two commands — copy, don't abstract (adapters
    stay independent per CLAUDE.md).
- **`mod.rs`**: add `pub mod x_upload;`
- **`lib.rs`**: `.manage(commands::x_upload::XUploadCancellations::default())`
  and add `upload_video_x`, `cancel_x_upload` to `generate_handler!`.

### TypeScript — auth (`src/platforms/x/`)

- **New `XAuth.ts`**, modeled on `TikTokAuth.ts`/`YouTubeAuth.ts`:
  - `AUTH_ENDPOINT = 'https://x.com/i/oauth2/authorize'`,
    `TOKEN_ENDPOINT = 'https://api.x.com/2/oauth2/token'`,
    `REVOKE_ENDPOINT = 'https://api.x.com/2/oauth2/revoke'`,
    `USER_INFO_ENDPOINT = 'https://api.x.com/2/users/me'`.
  - `SCOPES = 'tweet.read tweet.write users.read media.write offline.access'`.
  - Standard PKCE (reuse `generateCodeVerifier`/`generateCodeChallenge` from
    `services/auth/pkce.ts` as-is — X follows RFC 7636, no TikTok-style hex
    quirk needed).
  - `clientId()`/`clientSecret()` reading `VITE_X_CLIENT_ID`/`VITE_X_CLIENT_SECRET`.
  - Basic-auth the token/refresh/revoke requests with `client_id:client_secret`
    (X's confidential-client convention — Authorization header, not body params).
  - `connect()`: loopback server → build authorize URL → `openUrl` → await
    callback → exchange code → fetch `/2/users/me` → store credential → return
    `ConnectedAccount` (`id: \`x:${data.id}\``, `displayName: data.username`).
  - `disconnect()`: best-effort revoke, then `deleteCredential`.
  - `getValidAccessToken()`: same expiry-check-then-refresh shape as the other two.

### TypeScript — upload command (`src/platforms/x/`)

- **New `xUploadCommand.ts`**, modeled on `tiktokUploadCommand.ts`:
  - `invokeUpload(...)` wraps `invoke('upload_video_x', ...)` with a progress
    `Channel`.
  - `uploadVideoToX(...)`: get token → invoke, retry once on `authentication`
    error with a refreshed token (same pattern as TikTok/YouTube).
  - After FINALIZE succeeds, poll `GET https://api.x.com/2/media/upload?command=STATUS&media_id=...`
    until `processing_info.state` is `succeeded` (or `failed` → throw a
    `PublicationError` of type `platform`), same polling-interval/timeout
    constants as TikTok's `pollPublishStatus`.
  - `cancelXUpload(uploadId)`.

### TypeScript — adapter (`src/platforms/x/XAdapter.ts`)

- `getCapabilities()`: keep existing shape, no changes needed.
- `validate()`:
  - file size / mime type checks (copy TikTok's pattern).
  - compose tweet text (`description` + `' ' + hashtags.map(h => `#${h}`).join(' ')`)
    and push an error if it exceeds 280 characters.
- `upload()`: call `uploadVideoToX`, return `{ success: true, videoId: result.mediaId }`
  (media id stored as `videoId` per the shared `UploadResult` shape, matching
  how TikTok stores its `publishId` there).
- `publish()`: `POST https://api.x.com/2/tweets` with
  `{ text: composedText, media: { media_ids: [publication.uploadedVideoId] } }`,
  bearer-authed via `this.auth.getValidAccessToken(publication.accountId)`.
  Return `{ success: true, publishedUrl: \`https://x.com/i/web/status/${data.id}\` }`
  on success, `{ success: false, error: { type: 'platform', message } }`
  otherwise (same shape as `YouTubeAdapter.publish()`).
- No `schedule()` method — `capabilities.scheduling` stays `'unsupported'`,
  and `UploadManager.runPublicationTask` only calls `adapter.schedule` when
  it exists.

### Wiring

- **`src/platforms/auth.ts`**: replace `x: notImplemented('x')` with `x: new XAuth()`.
- **`src/platforms/x/index.ts`**: add `export * from './XAuth';`.
- **`.env.local`** (not committed): document `VITE_X_CLIENT_ID` /
  `VITE_X_CLIENT_SECRET` requirement in setup notes if there's a
  `.env.local.example` — none exists currently, so no file change needed there,
  just mention it in the PR description.

## Out of scope (per grilling decisions)

- `XSettingsPanel.tsx` stays as-is ("No settings yet.").
- No local/app-side scheduling for X.
- No thread/reply-chain support.

## Verification

1. `npx tsc --noEmit` and `npm run lint` — must pass with the new files.
2. `cd src-tauri && cargo check` — Rust command compiles and registers cleanly.
3. `npm run tauri dev` — manually connect an X account (requires a real X
   Developer confidential OAuth 2.0 app with the scopes above and
   `http://127.0.0.1:<port>/callback` allowed as a redirect URI), then run a
   full publish of a short test video end-to-end and confirm:
   - progress events update the UI during upload;
   - a tweet appears on the connected X account with the video attached and
     the composed text;
   - an over-280-character description is rejected by validation before
     upload starts;
   - disconnecting the account revokes/removes the stored credential.
